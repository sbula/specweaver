# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A project's MCP settings cannot hand the container runtime a library to load.

Proves: TECH-072 FR-8

`LD_PRELOAD` and its kin make the `docker`/`podman` client load code of the project's choosing, on the
host, outside any container. Both MCP paths refuse them before any process starts.

| Bucket | Case |
|---|---|
| Happy | an ordinary variable passes and the server starts |
| Boundary | `DYLD_*` is refused by its prefix, whatever follows it |
| Degradation | not applicable — nothing is started, so nothing can fail mid-way |
| Hostile | `LD_PRELOAD`, `LD_LIBRARY_PATH`, `LD_AUDIT`, `DYLD_INSERT_LIBRARIES`, in either case, refused by both paths |
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from specweaver.sandbox.mcp.core.atom import MCPAtom
from specweaver.sandbox.mcp.interfaces.tool import MCPExplorerTool

_LOADERS = ["LD_PRELOAD", "LD_LIBRARY_PATH", "LD_AUDIT", "DYLD_INSERT_LIBRARIES", "ld_preload"]
_COMMAND = ["docker", "run", "-i", "image"]


def _explore(env: dict[str, str]) -> tuple[object, MagicMock]:
    topology = MagicMock()
    topology.mcp_servers = {"db": {"command": "docker", "args": ["run", "-i", "image"], "env": env}}
    with (
        patch("specweaver.sandbox.mcp.interfaces.tool.MCPExecutor") as executor,
        patch("shutil.which", return_value="/usr/bin/docker"),
    ):
        instance = MagicMock()
        instance.call_rpc.side_effect = [{"result": {}}, None, {"result": {}}]
        executor.return_value = instance
        result = MCPExplorerTool(topology=topology)._intent_list_resources({"server_name": "db"})
    return result, executor


@pytest.mark.parametrize("name", _LOADERS)
def test_the_explorer_refuses_a_loader_variable(name: str) -> None:
    result, executor = _explore({name: "/tmp/evil.so"})

    assert result.status == "error"
    assert name in result.message
    executor.assert_not_called()


@pytest.mark.parametrize("name", _LOADERS)
def test_the_atom_refuses_a_loader_variable(name: str) -> None:
    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        pytest.raises(ValueError, match=name),
    ):
        MCPAtom(_COMMAND, env={name: "/tmp/evil.so"})


def test_an_ordinary_variable_passes() -> None:
    result, executor = _explore({"DATABASE_URL": "sqlite:///x.db"})

    assert result.status == "success"
    executor.assert_called_once()
