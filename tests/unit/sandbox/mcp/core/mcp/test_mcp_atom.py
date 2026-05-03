from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from specweaver.sandbox.base import AtomStatus
from specweaver.sandbox.mcp.core.atom import MCPAtom
from specweaver.sandbox.mcp.core.executor import MCPExecutorError


class TestMCPAtomIntents:
    @patch("specweaver.sandbox.mcp.core.atom.MCPExecutor")
    def test_unknown_intent(self, mock_executor_class: MagicMock) -> None:
        atom = MCPAtom([sys.executable])
        result = atom.run({"intent": "does_not_exist"})
        assert result.status == AtomStatus.FAILED
        assert "Unknown intent" in result.message

    @patch("specweaver.sandbox.mcp.core.atom.MCPExecutor")
    def test_missing_intent(self, mock_executor_class: MagicMock) -> None:
        atom = MCPAtom([sys.executable])
        result = atom.run({})
        assert result.status == AtomStatus.FAILED
        assert "Missing 'intent'" in result.message

    @patch("specweaver.sandbox.mcp.core.atom.MCPExecutor")
    def test_intent_initialize_success(self, mock_executor_class: MagicMock) -> None:
        mock_executor = MagicMock()
        # Mock the underlying MCPExecutor returned by the class
        mock_executor_class.return_value = mock_executor

        # When initialize is called it parses 'capabilities'
        mock_executor.call_rpc.side_effect = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"capabilities": {"logging": {}}},
            },  # Method initialize
            {"jsonrpc": "2.0", "id": 2, "result": {}},  # Method notifications/initialized
        ]

        atom = MCPAtom([sys.executable])

        context = {
            "intent": "initialize",
            "params": {"capabilities": {"roots": {"listChanged": True}}},
        }

        result = atom.run(context)

        assert result.status == AtomStatus.SUCCESS
        assert result.exports == {"capabilities": {"logging": {}}}

        # Verify the two RPC calls were dispatched correctly
        assert mock_executor.call_rpc.call_count == 2
        calls = mock_executor.call_rpc.call_args_list
        assert calls[0].kwargs["method"] == "initialize"
        assert "capabilities" in calls[0].kwargs["params"]
        assert calls[0].kwargs["params"]["capabilities"]["roots"]["listChanged"] is True

        assert calls[1].kwargs["method"] == "notifications/initialized"

    @patch("specweaver.sandbox.mcp.core.atom.MCPExecutor")
    def test_intent_read_resource_success(self, mock_executor_class: MagicMock) -> None:
        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        mock_executor.call_rpc.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "contents": [
                    {
                        "uri": "postgres://schema",
                        "mimeType": "text/plain",
                        "text": "CREATE TABLE...",
                    }
                ]
            },
        }

        atom = MCPAtom([sys.executable])

        context = {"intent": "read_resource", "params": {"uri": "postgres://schema"}}

        result = atom.run(context)

        assert result.status == AtomStatus.SUCCESS
        assert result.exports["contents"][0]["text"] == "CREATE TABLE..."

    @patch("specweaver.sandbox.mcp.core.atom.MCPExecutor")
    def test_intent_read_resource_missing_uri(self, mock_executor_class: MagicMock) -> None:
        atom = MCPAtom([sys.executable])

        context = {
            "intent": "read_resource",
            "params": {},  # Missing URI payload
        }

        result = atom.run(context)

        assert result.status == AtomStatus.FAILED
        assert "Missing 'uri'" in result.message

    @patch("specweaver.sandbox.mcp.core.atom.MCPExecutor")
    def test_executor_error_handling(self, mock_executor_class: MagicMock) -> None:
        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        mock_executor.call_rpc.side_effect = MCPExecutorError("Connection refused by binary")

        atom = MCPAtom([sys.executable])
        result = atom.run({"intent": "read_resource", "params": {"uri": "test://test"}})

        assert result.status == AtomStatus.FAILED
        assert "Connection refused" in result.message

    @patch("specweaver.sandbox.mcp.core.atom.MCPExecutor")
    def test_close_teardown(self, mock_executor_class: MagicMock) -> None:
        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        atom = MCPAtom([sys.executable])

        # Ensure it boots
        atom._ensure_started()
        assert atom._executor is not None

        # Tear down
        atom.close()

        mock_executor.close.assert_called_once()
        assert atom._executor is None

    def test_nfr2_command_violation_guard(self) -> None:
        """Test that MCPAtom enforces strict Docker/Podman isolation rules."""
        import pytest

        with pytest.raises(ValueError, match="NFR-2 Boundary Violation"):
            MCPAtom(["node", "index.js"])

        with pytest.raises(ValueError, match="Configuration Error"):
            MCPAtom([])

    def test_known_intents(self) -> None:
        """Test that reflection accurately maps initialize and read_resource targets."""
        atom = MCPAtom([sys.executable])
        intents = atom._known_intents()
        assert "initialize" in intents
        assert "read_resource" in intents

    def test_intent_initialize_uninitialized_executor(self) -> None:
        """Test internal initialize method bails seamlessly when executor is entirely uninitialized."""
        atom = MCPAtom([sys.executable])
        # Force a bypass of run() mapped _ensure_started()
        result = atom._intent_initialize({})
        assert result.status == AtomStatus.FAILED
        assert "Executor not initialized" in result.message

    def test_intent_read_resource_uninitialized_executor(self) -> None:
        """Test internal read_resource method bails when executor is entirely uninitialized."""
        atom = MCPAtom([sys.executable])
        # Force bypass
        result = atom._intent_read_resource({})
        assert result.status == AtomStatus.FAILED
        assert "Executor not initialized" in result.message

    @patch("specweaver.sandbox.mcp.core.atom.MCPExecutor")
    def test_telemetry_scrubbing_removes_vault_secrets(
        self, mock_executor_class: MagicMock
    ) -> None:
        """Test that vault.env secrets tracked in `_env` are replaced with ***RESTRICTED*** in returned exports."""
        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        mock_executor.call_rpc.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "db_uri": "postgres://supersecret@host.docker.internal/db",
                "nested": {"password": "supersecret"},
            },
        }

        # Initialize with simulated vault vault.env bound via CLI dispatch
        env_vars = {"POSTGRES_PASSWORD": "supersecret", "TINY": "ok"}
        atom = MCPAtom([sys.executable], env=env_vars)

        context = {"intent": "read_resource", "params": {"uri": "postgres://schema"}}
        result = atom.run(context)

        assert result.status == AtomStatus.SUCCESS
        assert "supersecret" not in result.exports["db_uri"]
        assert "***RESTRICTED***" in result.exports["db_uri"]
        assert result.exports["nested"]["password"] == "***RESTRICTED***"

    @patch("specweaver.sandbox.mcp.core.atom.MCPExecutor")
    def test_telemetry_scrubbing_ignores_short_strings(
        self, mock_executor_class: MagicMock
    ) -> None:
        """Test that short strings (< 8 chars) or whitespace are not scrubbed to prevent false positive log corruption."""
        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        mock_executor.call_rpc.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"status": "ok", "empty": " "},
        }

        # TINY is short, should be ignored
        env_vars = {"TINY": "ok", "SPACE": " "}
        atom = MCPAtom([sys.executable], env=env_vars)

        context = {"intent": "read_resource", "params": {"uri": "postgres://schema"}}
        result = atom.run(context)

        assert result.status == AtomStatus.SUCCESS
        assert result.exports["status"] == "ok"  # 'ok' isn't scrubbed because len < 8
        assert result.exports["empty"] == " "

    @patch("specweaver.sandbox.mcp.core.atom.MCPExecutor")
    def test_telemetry_scrubbing_removes_vault_secrets_from_lists(
        self, mock_executor_class: MagicMock
    ) -> None:
        """Test that vault.env secrets nested deeply in JSON arrays are recursively masked."""
        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        mock_executor.call_rpc.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "connections": [
                    "safe-string",
                    "postgres://supersecret@host",
                    {"sub": ["nested", "supersecret"]},
                ]
            },
        }

        env_vars = {"POSTGRES_PASSWORD": "supersecret"}
        atom = MCPAtom([sys.executable], env=env_vars)

        context = {"intent": "read_resource", "params": {"uri": "postgres://schema"}}
        result = atom.run(context)

        assert result.status == AtomStatus.SUCCESS
        connections = result.exports["connections"]
        assert connections[0] == "safe-string"
        assert "***RESTRICTED***" in connections[1]
        assert "supersecret" not in connections[1]
        assert connections[2]["sub"][1] == "***RESTRICTED***"
