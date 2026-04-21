# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for MCP Pre-Fetch Context Assembler utility."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from specweaver.assurance.graph.topology import TopologyContext
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.mcp_assembler import evaluate_and_fetch_mcp_context
from specweaver.core.loom.atoms.base import AtomResult, AtomStatus

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def mock_run_context(tmp_path: Path) -> RunContext:
    """Fixture providing a mock RunContext with loaded topology variables."""
    topology = TopologyContext(
        name="test_module",
        purpose="Testing.",
        archetype="pure-logic",
        relationship="self",
        mcp_servers={
            "localdb": {"command": "docker", "args": ["run", "sqlite-mcp"]},
        },
        consumes_resources=["mcp://localdb/users", "mcp://localdb/orders"],
    )
    return RunContext(
        project_path=tmp_path,
        spec_path=tmp_path / "test_spec.md",
        topology=topology,
    )


# ==============================================================================
# Execution Mapping Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_no_mcp_servers(mock_run_context: RunContext) -> None:
    """If no MCP servers are defined in the topology, returns None instantly."""
    mock_run_context.topology.mcp_servers.clear()
    result = await evaluate_and_fetch_mcp_context(mock_run_context)
    assert result is None


@pytest.mark.asyncio
async def test_no_consumes_resources(mock_run_context: RunContext) -> None:
    """If mcp_servers exist but no specific resources are requested, returns None."""
    mock_run_context.topology.consumes_resources.clear()
    result = await evaluate_and_fetch_mcp_context(mock_run_context)
    assert result is None


@pytest.mark.asyncio
async def test_fetches_and_strips_json_rpc(mock_run_context: RunContext) -> None:
    """Verify that evaluate_and_fetch_mcp_context spawns Atom synchronously in thread and extracts contents."""

    mock_init = AtomResult(status=AtomStatus.SUCCESS, message="Init OK", exports={})

    mock_result_users = AtomResult(
        status=AtomStatus.SUCCESS,
        message="OK",
        exports={
            "contents": [
                {"uri": "mcp://localdb/users", "mimeType": "text/plain", "text": "user1, user2"}
            ],
        },
    )
    mock_result_orders = AtomResult(
        status=AtomStatus.SUCCESS,
        message="OK",
        exports={
            "contents": [
                {
                    "uri": "mcp://localdb/orders",
                    "mimeType": "application/json",
                    "text": '{"order": 1}',
                }
            ],
        },
    )

    call_count = 0

    def mock_atom_run(inputs: dict[str, Any]) -> AtomResult:
        nonlocal call_count
        intent = inputs.get("intent")
        if intent == "initialize":
            return mock_init

        call_count += 1
        uri = inputs.get("params", {}).get("uri", "")
        if "users" in uri:
            return mock_result_users
        return mock_result_orders

    with patch(
        "specweaver.core.loom.atoms.mcp.atom.MCPAtom.run", side_effect=mock_atom_run
    ) as m_atom:
        result = await evaluate_and_fetch_mcp_context(mock_run_context)

        # Called initialization and read twice
        assert m_atom.call_count == 4

        # Assert format matches the markdown context wrapper pattern for prompt builders
        assert "mcp://localdb/users:" in result
        assert "user1, user2" in result
        assert "mcp://localdb/orders:" in result
        assert '{"order": 1}' in result


@pytest.mark.asyncio
async def test_handles_atom_failure_gracefully(mock_run_context: RunContext) -> None:
    """Verify that if MCPAtom throws an exception, it formats an error string natively."""

    def mock_atom_run_fail(inputs: dict[str, Any]) -> AtomResult:
        raise ValueError("Docker socket closed")

    with patch("specweaver.core.loom.atoms.mcp.atom.MCPAtom.run", side_effect=mock_atom_run_fail):
        result = await evaluate_and_fetch_mcp_context(mock_run_context)

        assert "mcp://localdb/users:" in result
        assert "ERROR fetching resource" in result
        assert "Docker socket closed" in result
