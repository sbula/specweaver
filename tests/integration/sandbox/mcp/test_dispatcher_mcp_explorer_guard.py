# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The MCP explorer the dispatcher mounts for an agent refuses an unguarded command.

Proves: TECH-072 FR-2

The unit tests build the tool by hand; this drives it through `ToolDispatcher`, the path an agent's
tool call takes, so the registry's wiring is under test too.

| Bucket | Case |
|---|---|
| Happy | a docker command reaches the executor with the runtime resolved from this process |
| Hostile | a bare interpreter from the project's config is refused and never started |
| Boundary / Degradation | covered by the unit tests of the tool itself |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from specweaver.sandbox.dispatcher import ToolDispatcher
from specweaver.sandbox.security import WorkspaceBoundary

if TYPE_CHECKING:
    from pathlib import Path


def _architect(project: Path, command: str, args: list[str]) -> ToolDispatcher:
    topology = MagicMock()
    topology.mcp_servers = {"db": {"command": command, "args": args, "env": {}}}
    return ToolDispatcher.create_standard_set(
        WorkspaceBoundary(roots=[project]),
        role="architect",
        allowed_tools=["mcp"],
        topology=topology,
    )


async def test_an_interpreter_command_is_refused_before_it_starts(tmp_path: Path) -> None:
    dispatcher = _architect(tmp_path, "python", ["-c", "import os"])

    with patch("specweaver.sandbox.mcp.interfaces.tool.MCPExecutor") as executor_class:
        result = await dispatcher.execute("list_resources", {"server_name": "db"})

    assert "error" in result
    executor_class.assert_not_called()


async def test_a_docker_command_starts_with_the_trusted_runtime(tmp_path: Path) -> None:
    dispatcher = _architect(tmp_path, "docker", ["run", "-i", "image"])

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("specweaver.sandbox.mcp.interfaces.tool.MCPExecutor") as executor_class,
    ):
        executor_class.return_value.call_rpc.side_effect = [{}, None, {"result": {"resources": []}}]
        result = await dispatcher.execute("list_resources", {"server_name": "db"})

    assert "error" not in result, result
    assert executor_class.call_args.kwargs["command"][0] == "/usr/bin/docker"
