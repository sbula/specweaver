# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An `mcp_servers` block written in a real `context.yaml` reaches a real server.

Proves: C-INTL-02 FR-1

FR-1 is *"read the `mcp_servers` block from `context.yaml`"*, and it was the one link of this
capability nobody drove from a file. `test_mcp_flow_e2e.py` proves boot, fetch and inject — but it
hands the assembler a `TopologyContext` object it constructed itself, so the parse step is skipped
and FR-1 rested on a unit test asserting a dict came out of a dict.

That matters more here than elsewhere: `mcp_servers` is how an analysed project names a command this
tool will execute. The declaration and the execution are the two ends of the security boundary
`TECH-063` hardened, and until now nothing joined them.

Nothing is mocked. A `context.yaml` on disk, the real topology loader, the real assembler, and a real
JSON-RPC server answering over stdio.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from specweaver.assurance.graph.loader import load_topology
from specweaver.core.flow.handlers.mcp_assembler import evaluate_and_fetch_mcp_context
from specweaver.core.flow.handlers.run_context import GraphContext, RunContext

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

#: The resource the declared server answers for, asserted by URI so a reply for a DIFFERENT resource
#: cannot satisfy the test.
RESOURCE = "mcp://declared/users_table"
PAYLOAD = "declared_via_context_yaml"

SERVER = f'''import json, sys

while True:
    line = sys.stdin.readline()
    if not line:
        break
    request = json.loads(line)
    method, msg_id = request.get("method"), request.get("id", 1)
    if method == "initialize":
        result = {{"protocolVersion": "1.0", "capabilities": {{}}}}
    elif method == "resources/read":
        uri = request.get("params", {{}}).get("uri", "")
        result = {{"contents": [{{"uri": uri, "mimeType": "text/plain", "text": "{PAYLOAD}"}}]}}
    else:
        result = {{}}
    sys.stdout.write(json.dumps({{"jsonrpc": "2.0", "id": msg_id, "result": result}}) + "\\n")
    sys.stdout.flush()
'''


@pytest.fixture(autouse=True)
def _allow_interpreter_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """The declared command is a Python script, and the boundary refuses a bare interpreter.

    That refusal is `TECH-063`'s fix for a real bypass. The seam is opened in test scope, which takes
    in-process code execution to reach — exactly what a `context.yaml` does not have. A container
    would need an image, a registry and a network to prove the same parse.
    """
    monkeypatch.setattr("specweaver.sandbox.mcp.core.atom._ALLOW_INTERPRETER", True)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project whose `context.yaml` declares an MCP server and the resource it consumes."""
    server = tmp_path / "server.py"
    server.write_text(SERVER, encoding="utf-8")

    module = tmp_path / "src"
    module.mkdir()
    (module / "context.yaml").write_text(
        "name: demo\n"
        "purpose: Declares an MCP server.\n"
        "archetype: adapter\n"
        "mcp_servers:\n"
        "  declared:\n"
        f"    command: [{sys.executable!r}]\n"
        f"    args: [{str(server)!r}]\n"
        "consumes_resources:\n"
        f"  - {RESOURCE}\n",
        encoding="utf-8",
    )
    return tmp_path


async def test_a_declared_server_is_booted_and_answers(project: Path) -> None:
    """The whole link: a block in a file becomes a running process whose reply reaches the caller."""
    topology = load_topology(project)
    assert topology is not None, "the loader found no context.yaml at all"
    node = topology.nodes["demo"]

    context = RunContext(project_path=project, spec_path=project / "spec.md")
    context.graph = GraphContext(topology=node)

    fetched = await evaluate_and_fetch_mcp_context(context)

    assert fetched is not None, "the declared server was never consulted"
    assert PAYLOAD in fetched
    assert RESOURCE in fetched, f"a reply arrived for the wrong resource:\n{fetched}"


def test_the_declaration_survives_the_parse(project: Path) -> None:
    """The premise, separated on purpose.

    If the loader dropped `mcp_servers`, the test above would fail with "never consulted" and read as
    a fetch problem. This says which end broke.
    """
    node = load_topology(project).nodes["demo"]

    assert "declared" in node.mcp_servers, node.mcp_servers
    assert node.consumes_resources == [RESOURCE]


async def test_a_project_declaring_no_server_fetches_nothing(tmp_path: Path) -> None:
    """The control. A fetch that ran unconditionally would pass the test above without reading YAML."""
    module = tmp_path / "src"
    module.mkdir()
    (module / "context.yaml").write_text(
        "name: bare\npurpose: Declares nothing.\narchetype: pure-logic\n", encoding="utf-8"
    )
    node = load_topology(tmp_path).nodes["bare"]

    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
    context.graph = GraphContext(topology=node)

    assert await evaluate_and_fetch_mcp_context(context) is None
