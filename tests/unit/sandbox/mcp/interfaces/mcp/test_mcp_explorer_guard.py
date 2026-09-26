# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The MCP explorer runs a project's MCP command only through the guard `MCPAtom` uses.

Proves: TECH-072 FR-2, FR-3, FR-4

The command comes from the analysed project's own configuration, so it is untrusted input.

| Bucket | Case |
|---|---|
| Happy | a plain `docker run -i image` starts, with `argv[0]` resolved from THIS process's PATH |
| Boundary | a secret shorter than 8 characters is not scrubbed (it would match everywhere) |
| Degradation | the runtime is not installed → refused, nothing started |
| Hostile | a bare interpreter, `--privileged`, `--network=host`, `-v /:/host` → refused, nothing started; a secret in the reply comes back redacted |
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from specweaver.sandbox.mcp.interfaces.tool import MCPExplorerTool

_EXECUTOR = "specweaver.sandbox.mcp.interfaces.tool.MCPExecutor"
_WHICH = "shutil.which"


def _topology(command: str, args: list[str], env: dict[str, str] | None = None) -> MagicMock:
    topo = MagicMock()
    topo.mcp_servers = {"db": {"command": command, "args": args, "env": env or {}}}
    return topo


def _replying(executor_class: MagicMock, reply: dict) -> MagicMock:
    instance = MagicMock()
    instance.call_rpc.side_effect = [{"result": {}}, None, {"result": reply}]
    executor_class.return_value = instance
    return instance


class TestTheExplorerRefusesWhatTheAtomRefuses:
    @pytest.mark.parametrize(
        ("command", "args"),
        [
            ("python", ["-c", "print(1)"]),
            ("/bin/sh", ["-c", "id"]),
            ("docker", ["run", "--privileged", "image"]),
            ("docker", ["run", "--network=host", "image"]),
            ("docker", ["run", "-v", "/:/host", "image"]),
        ],
    )
    def test_an_unguarded_command_never_starts(self, command: str, args: list[str]) -> None:
        with patch(_EXECUTOR) as executor_class, patch(_WHICH, return_value="/usr/bin/docker"):
            result = MCPExplorerTool(topology=_topology(command, args))._intent_list_resources(
                {"server_name": "db"}
            )

        assert result.status == "error"
        executor_class.assert_not_called()

    def test_a_missing_runtime_is_refused(self) -> None:
        with patch(_EXECUTOR) as executor_class, patch(_WHICH, return_value=None):
            result = MCPExplorerTool(
                topology=_topology("docker", ["run", "-i", "image"])
            )._intent_list_resources({"server_name": "db"})

        assert result.status == "error"
        executor_class.assert_not_called()

    def test_a_guarded_command_starts_with_the_trusted_runtime_path(self) -> None:
        with patch(_EXECUTOR) as executor_class, patch(_WHICH, return_value="/usr/bin/docker"):
            _replying(executor_class, {"resources": []})
            result = MCPExplorerTool(
                topology=_topology("docker", ["run", "-i", "image"], {"PATH": "/evil"})
            )._intent_list_resources({"server_name": "db"})

        assert result.status == "success", result.message
        started = executor_class.call_args.kwargs.get("command") or executor_class.call_args.args[0]
        assert started == ["/usr/bin/docker", "run", "-i", "image"]


class TestTheExplorerScrubsSecrets:
    def test_a_configured_secret_is_redacted_in_the_reply(self) -> None:
        secret = "s3cr3t-token-value"
        with patch(_EXECUTOR) as executor_class, patch(_WHICH, return_value="/usr/bin/docker"):
            _replying(executor_class, {"contents": [{"text": f"dsn=postgres://u:{secret}@db"}]})
            result = MCPExplorerTool(
                topology=_topology("docker", ["run", "-i", "image"], {"DB_PASSWORD": secret})
            )._intent_read_resource({"server_name": "db", "uri": "db://schema"})

        assert result.status == "success", result.message
        assert secret not in result.data
        assert "***RESTRICTED***" in json.loads(result.data)["contents"][0]["text"]

    def test_a_secret_is_redacted_in_a_resource_listing_too(self) -> None:
        secret = "another-long-secret"
        with patch(_EXECUTOR) as executor_class, patch(_WHICH, return_value="/usr/bin/docker"):
            _replying(executor_class, {"resources": [{"uri": f"db://{secret}/t"}]})
            result = MCPExplorerTool(
                topology=_topology("docker", ["run", "-i", "image"], {"TOKEN": secret})
            )._intent_list_resources({"server_name": "db"})

        assert result.status == "success", result.message
        assert secret not in result.data

    def test_a_short_value_is_not_treated_as_a_secret(self) -> None:
        with patch(_EXECUTOR) as executor_class, patch(_WHICH, return_value="/usr/bin/docker"):
            _replying(executor_class, {"contents": [{"text": "port=5432 ok"}]})
            result = MCPExplorerTool(
                topology=_topology("docker", ["run", "-i", "image"], {"PORT": "5432"})
            )._intent_read_resource({"server_name": "db", "uri": "db://schema"})

        assert "port=5432 ok" in result.data


class TestBothMcpPathsShareOneGuard:
    """FR-4: the explorer and `MCPAtom` must accept and refuse exactly the same commands."""

    @pytest.mark.parametrize(
        "command",
        [
            ["docker", "run", "-i", "image"],
            ["podman", "run", "-i", "image"],
            ["python", "-c", "1"],
            ["docker", "run", "--cap-add=SYS_ADMIN", "image"],
            ["docker", "run", "--mount", "/var/run/docker.sock:/s", "image"],
        ],
    )
    def test_the_two_paths_agree(self, command: list[str]) -> None:
        from specweaver.sandbox.mcp.core.atom import MCPAtom

        with patch(_WHICH, return_value="/usr/bin/runtime"):
            try:
                MCPAtom(command=command)
                atom_accepts = True
            except ValueError:
                atom_accepts = False

            with patch(_EXECUTOR) as executor_class:
                _replying(executor_class, {"resources": []})
                result = MCPExplorerTool(
                    topology=_topology(command[0], command[1:])
                )._intent_list_resources({"server_name": "db"})

        assert (result.status == "success") is atom_accepts
