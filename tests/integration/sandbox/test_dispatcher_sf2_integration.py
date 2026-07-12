# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests for TECH-002 SF-2 Sandbox Domain Alignment edge cases."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from specweaver.sandbox.base import BaseTool
from specweaver.sandbox.dispatcher import ToolDispatcher
from specweaver.sandbox.security import WorkspaceBoundary


@pytest.mark.integration
def test_dispatcher_builds_fully_compliant_basetool_set(tmp_path) -> None:
    """
    [Edge Case] Integration:
    Ensures that when ToolDispatcher builds a complete standard set of tools,
    every single instantiated interface successfully inherits from BaseTool
    and returns a valid string for its role property.
    This proves that the SF-2 alignment contract holds at the boundary
    where tools enter the LLM Flow engine.
    """
    boundary = WorkspaceBoundary(roots=[tmp_path])
    mock_topology = MagicMock()
    mock_topology.mcp_servers = {"test_server": {}}

    dispatcher = ToolDispatcher.create_standard_set(
        boundary=boundary,
        role="implementer",
        allowed_tools=["fs", "git", "web", "ast", "qa", "protocol"],
        topology=mock_topology,
    )

    # We can inspect the internal loaded interfaces
    # (these are what gets exposed to the LLM orchestrator)
    # The dispatcher stores them in self._registry which maps intents -> bound methods.
    # We can fetch the unique tools by looking at the bound methods' __self__.
    unique_tools = {method.__self__ for method in dispatcher._registry.values()}

    assert len(unique_tools) > 0, "Dispatcher failed to load any tools."

    for tool in unique_tools:
        # 1. Structural verification at the integration boundary
        assert isinstance(tool, BaseTool), (
            f"Tool {type(tool).__name__} does not inherit from BaseTool."
        )

        # 2. Runtime property verification
        role_val = tool.role
        assert isinstance(role_val, str), f"Tool {type(tool).__name__}.role must return a string."


@pytest.mark.integration
def test_dispatcher_handles_no_role_sentinel_transparently(tmp_path) -> None:
    """
    [Edge Case] Integration:
    Verifies that the ToolRegistry correctly instantiates non-RBAC tools (like ProtocolTool)
    which utilize the BaseTool.NO_ROLE sentinel without crashing or polluting
    role-gated validation logic downstream.
    """
    from specweaver.sandbox.registry import get_standard_registry

    registry = get_standard_registry()
    tools = registry.create_tools(allowed_tools=["protocol"])

    assert len(tools) == 1
    protocol_tool = tools[0]

    # Assert it correctly uses the NO_ROLE sentinel
    assert isinstance(protocol_tool, BaseTool)
    assert protocol_tool.role == BaseTool.NO_ROLE
    assert protocol_tool.role == "no_role"


@pytest.mark.integration
def test_dispatcher_passes_topology_directly_to_mcp_explorer(tmp_path) -> None:
    """
    [Edge Case] Integration:
    Verifies the AD-6 refactor: When 'architect' role requests 'mcp', the Dispatcher
    must successfully pass the raw topology object directly to the MCPExplorerTool
    without using the deprecated DummyContext wrapper.
    """
    boundary = WorkspaceBoundary(roots=[tmp_path])
    mock_topology = MagicMock()
    mock_topology.mcp_servers = {"integration_server": {"command": "echo"}}

    dispatcher = ToolDispatcher.create_standard_set(
        boundary=boundary,
        role="architect",
        allowed_tools=["mcp"],
        topology=mock_topology,
    )

    unique_tools = {method.__self__ for method in dispatcher._registry.values()}
    assert len(unique_tools) == 1

    mcp_facade = unique_tools.pop()

    # Verify it is the facade
    from specweaver.sandbox.mcp.interfaces.facades import ArchitectMCPInterface

    assert isinstance(mcp_facade, ArchitectMCPInterface)

    # Assert it correctly uses the NO_ROLE sentinel via delegation
    assert mcp_facade.role == BaseTool.NO_ROLE

    # Verify the inner MCPExplorerTool received the topology correctly
    inner_tool = mcp_facade._tool
    assert inner_tool._topology is mock_topology
    assert getattr(inner_tool, "context", "NOT_FOUND") == "NOT_FOUND", (
        "Deprecated context attribute still exists."
    )
