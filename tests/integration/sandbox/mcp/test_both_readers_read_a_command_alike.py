# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The MCP pre-fetch and the MCP explorer read a server's `command` the same way, and never write it.

Proves: TECH-088 FR-14

Both read a boundary loaded from a real `context.yaml`. The boundary is frozen, so a reader that
wrote into its config would raise; before the freeze, the pre-fetch wrote into it silently and a
second resource from one server started with its `args` twice.

| Bucket | Case |
|---|---|
| Happy | a list `command` starts the same command from both readers |
| Boundary | two resources from one server: the same command both times, and the stored config unchanged |
| Degradation | a spaced string `command` starts no process; each reader reports the list form to use |
| Hostile | the spaced string is never split into a command, by either reader (the user, 2026-11-08) |
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from specweaver.core.flow.handlers import mcp_assembler
from specweaver.core.flow.handlers.mcp_assembler import evaluate_and_fetch_mcp_context
from specweaver.core.flow.run_state.run_context import GraphContext, RunContext
from specweaver.graph.topology.loader import load_topology
from specweaver.sandbox.mcp.interfaces.tool import MCPExplorerTool

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.graph.topology.topology import TopologyNode

pytestmark = pytest.mark.integration

_EXECUTOR = "specweaver.sandbox.mcp.interfaces.tool.MCPExecutor"
SERVER = """import json, sys

while True:
    line = sys.stdin.readline()
    if not line:
        break
    request = json.loads(line)
    method, msg_id = request.get("method"), request.get("id", 1)
    if method == "resources/read":
        uri = request.get("params", {}).get("uri", "")
        result = {"contents": [{"uri": uri, "mimeType": "text/plain", "text": "answered"}]}
    else:
        result = {}
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result}) + "\\n")
    sys.stdout.flush()
"""


@pytest.fixture(autouse=True)
def _allow_interpreter_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """The declared server is a Python script; see `test_mcp_servers_from_context_yaml.py`."""
    monkeypatch.setattr("specweaver.sandbox.mcp.core.atom._ALLOW_INTERPRETER", True)


def _boundary(tmp_path: Path, command_lines: str, resources: tuple[str, ...]) -> TopologyNode:
    module = tmp_path / "src"
    module.mkdir()
    listed = "".join(f"  - {uri}\n" for uri in resources)
    (module / "context.yaml").write_text(
        "name: demo\npurpose: Declares a server.\narchetype: adapter\n"
        f"mcp_servers:\n  declared:\n{command_lines}consumes_resources:\n{listed}",
        encoding="utf-8",
    )
    graph = load_topology(tmp_path)
    assert graph is not None
    return graph.nodes["demo"]


def _listed(tmp_path: Path) -> tuple[str, str]:
    server = tmp_path / "server.py"
    server.write_text(SERVER, encoding="utf-8")
    return sys.executable, str(server)


async def _prefetch(
    tmp_path: Path, boundary: TopologyNode, monkeypatch: pytest.MonkeyPatch
) -> tuple[str | None, list[list[str]]]:
    started: list[list[str]] = []
    real = mcp_assembler._sync_fetch

    def recording(command: list[str], env: dict[str, str], uri: str) -> str:
        started.append(list(command))
        return real(command, env, uri)

    monkeypatch.setattr(mcp_assembler, "_sync_fetch", recording)
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
    context.graph = GraphContext(target_boundary=boundary)
    return await evaluate_and_fetch_mcp_context(context), started


def _explore(boundary: TopologyNode) -> tuple[Any, MagicMock]:
    with patch(_EXECUTOR) as executor_class:
        instance = MagicMock()
        instance.call_rpc.side_effect = [{"result": {}}, None, {"result": {"resources": []}}]
        executor_class.return_value = instance
        result = MCPExplorerTool(topology=boundary)._intent_list_resources(
            {"server_name": "declared"}
        )
    return result, executor_class


async def test_both_readers_start_the_same_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    python, server = _listed(tmp_path)
    boundary = _boundary(
        tmp_path, f"    command: [{python!r}]\n    args: [{server!r}]\n", ("mcp://declared/a",)
    )

    fetched, started = await _prefetch(tmp_path, boundary, monkeypatch)
    result, executor_class = _explore(boundary)

    assert fetched is not None and "answered" in fetched
    assert result.status == "success", result.message
    assert started == [[python, server]]
    assert executor_class.call_args.kwargs["command"] == [python, server]


async def test_two_resources_from_one_server_start_it_the_same_way(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    python, server = _listed(tmp_path)
    boundary = _boundary(
        tmp_path,
        f"    command: [{python!r}]\n    args: [{server!r}]\n",
        ("mcp://declared/a", "mcp://declared/b"),
    )

    _, started = await _prefetch(tmp_path, boundary, monkeypatch)

    assert started == [[python, server], [python, server]]
    assert list(boundary.mcp_servers["declared"]["command"]) == [python]
    assert list(boundary.mcp_servers["declared"]["args"]) == [server]


async def test_a_spaced_string_command_starts_nothing_in_either_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    python, server = _listed(tmp_path)
    boundary = _boundary(tmp_path, f"    command: '{python} {server}'\n", ("mcp://declared/a",))
    fix = f"use command: [{python}, {server}]"

    fetched, started = await _prefetch(tmp_path, boundary, monkeypatch)
    result, executor_class = _explore(boundary)

    assert started == []
    assert fetched is not None and fix in fetched
    assert result.status == "error"
    assert fix in result.message
    executor_class.assert_not_called()
