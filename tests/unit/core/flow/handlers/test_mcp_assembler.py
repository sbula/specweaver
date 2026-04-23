# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for MCP Pre-Fetch Context Assembler utility."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from specweaver.assurance.graph.topology import TopologyContext
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.mcp_assembler import evaluate_and_fetch_mcp_context
from specweaver.core.loom.atoms.base import AtomResult, AtomStatus

if TYPE_CHECKING:
    from pathlib import Path

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


@pytest.mark.asyncio
async def test_invalid_mcp_uri_format(mock_run_context: RunContext, tmp_path: Path) -> None:
    """If URI does not start with mcp://, it appends an inline error."""
    mock_run_context.topology = TopologyContext(
        name="test_module",
        purpose="Testing.",
        archetype="pure-logic",
        relationship="self",
        mcp_servers={"localdb": {"command": "docker", "args": ["run"]}},
        consumes_resources=["http://localdb/users"],
    )
    result = await evaluate_and_fetch_mcp_context(mock_run_context)
    assert "ERROR: Invalid MCP URI format" in result


@pytest.mark.asyncio
async def test_missing_mcp_server_config(mock_run_context: RunContext, tmp_path: Path) -> None:
    """If server parsed from mcp URI is absent in topology, it appends an inline error."""
    mock_run_context.topology = TopologyContext(
        name="test_module",
        purpose="Testing.",
        archetype="pure-logic",
        relationship="self",
        mcp_servers={"localdb": {"command": "docker", "args": ["run"]}},
        consumes_resources=["mcp://unknown_db/users"],
    )
    result = await evaluate_and_fetch_mcp_context(mock_run_context)
    assert "ERROR: Server 'unknown_db' not found in topology bounds" in result


@pytest.mark.asyncio
async def test_init_intent_failure(mock_run_context: RunContext) -> None:
    """Verify that if initialization intent fails, it aborts the read intent and returns error message natively."""

    def mock_atom_run_init_fail(inputs: dict[str, Any]) -> AtomResult:
        return AtomResult(status=AtomStatus.FAILED, message="Timeout waiting for Stdio", exports={})

    with patch(
        "specweaver.core.loom.atoms.mcp.atom.MCPAtom.run", side_effect=mock_atom_run_init_fail
    ) as m_atom:
        result = await evaluate_and_fetch_mcp_context(mock_run_context)

        # initialization fails instantly
        assert m_atom.call_count == 2
        assert "ERROR init resource: Timeout waiting for Stdio" in result


@pytest.mark.asyncio
async def test_empty_contents_payload(mock_run_context: RunContext) -> None:
    """Verify that if the read_resource returns successful status but empty content list, it handles cleanly."""

    def mock_atom_run_empty(inputs: dict[str, Any]) -> AtomResult:
        if inputs.get("intent") == "initialize":
            return AtomResult(status=AtomStatus.SUCCESS, message="Init OK", exports={})
        # Empty exports
        return AtomResult(status=AtomStatus.SUCCESS, message="OK", exports={})

    with patch("specweaver.core.loom.atoms.mcp.atom.MCPAtom.run", side_effect=mock_atom_run_empty):
        result = await evaluate_and_fetch_mcp_context(mock_run_context)

        assert "No resource data returned for mcp://localdb/users" in result


@pytest.mark.asyncio
async def test_multiple_mcp_servers_integration(mock_run_context: RunContext) -> None:
    """Verify that evaluate_and_fetch_mcp_context retrieves strings across multiple distinct MCP servers simultaneously."""
    mock_run_context.topology = TopologyContext(
        name="test_module",
        purpose="Testing.",
        archetype="pure-logic",
        relationship="self",
        mcp_servers={
            "db_server": {"command": "docker", "args": ["run"]},
            "api_server": {"command": "docker", "args": ["run_api"]},
        },
        consumes_resources=["mcp://db_server/users", "mcp://api_server/schema"],
    )

    def mock_atom_run_multi(inputs: dict[str, Any]) -> AtomResult:
        intent = inputs.get("intent")
        if intent == "initialize":
            return AtomResult(status=AtomStatus.SUCCESS, message="Init OK", exports={})

        uri = inputs.get("params", {}).get("uri", "")
        if "db_server/users" in uri:
            return AtomResult(
                status=AtomStatus.SUCCESS,
                message="OK",
                exports={"contents": [{"uri": uri, "mimeType": "text/plain", "text": "user_data"}]},
            )
        elif "api_server/schema" in uri:
            return AtomResult(
                status=AtomStatus.SUCCESS,
                message="OK",
                exports={
                    "contents": [{"uri": uri, "mimeType": "text/plain", "text": "api_schema"}]
                },
            )
        return AtomResult(status=AtomStatus.FAILED, message="Not found", exports={})

    with patch(
        "specweaver.core.loom.atoms.mcp.atom.MCPAtom.run", side_effect=mock_atom_run_multi
    ) as m_atom:
        result = await evaluate_and_fetch_mcp_context(mock_run_context)

        assert m_atom.call_count == 4
        assert "mcp://db_server/users:" in result
        assert "user_data" in result
        assert "mcp://api_server/schema:" in result
        assert "api_schema" in result
