from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from specweaver.sandbox.mcp.core.executor import MCPExecutor, MCPExecutorError


class MockProcess:
    def __init__(self, stdout_lines=None, exit_code=None):
        self.stdout_lines = stdout_lines or []
        self.exit_code = exit_code
        self.stdin = MagicMock()
        self.stdout = MagicMock()

        # Configure stdout.readline to yield lines or block
        def mock_readline():
            if self.stdout_lines:
                return self.stdout_lines.pop(0)
            # simulate blocking forever if no lines left
            import time

            time.sleep(10)
            return ""

        self.stdout.readline.side_effect = mock_readline
        self.returncode = exit_code

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        pass


@patch("subprocess.Popen")
def test_executor_initialization(mock_popen):
    mock_popen.return_value = MockProcess()
    cmd = ["docker", "run", "-i", "--rm", "mcp/postgres"]
    executor = MCPExecutor(cmd)

    mock_popen.assert_called_once()
    args, kwargs = mock_popen.call_args
    assert args[0] == cmd
    assert kwargs["stdin"] == subprocess.PIPE
    assert kwargs["stdout"] == subprocess.PIPE
    assert kwargs["text"] is True

    assert executor.is_alive()
    executor.close()


@patch("subprocess.Popen")
def test_call_rpc_success(mock_popen):
    # Setup process with out-of-order logs, then the valid JSON-RPC
    valid_response = '{"jsonrpc": "2.0", "id": 1, "result": {"resources": []}}\n'
    mock_process = MockProcess(stdout_lines=["Some docker log line ignoring\n", valid_response])
    mock_popen.return_value = mock_process

    executor = MCPExecutor(["test"])

    # We call standard initialization format
    response = executor.call_rpc(method="resources/list", params={})

    # Assert result ignores the junk line and parses json
    assert response["result"] == {"resources": []}

    # Assert stdin wrote the correct request
    assert mock_process.stdin.write.called
    written = mock_process.stdin.write.call_args[0][0]
    import json as stdjson

    payload = stdjson.loads(written)
    assert payload["jsonrpc"] == "2.0"
    assert payload["method"] == "resources/list"
    assert payload["id"] == 1

    executor.close()


@patch("subprocess.Popen")
def test_call_rpc_timeout(mock_popen):
    # Process yields nothing, causing readline to block forever
    mock_process = MockProcess(stdout_lines=[])
    mock_popen.return_value = mock_process

    executor = MCPExecutor(["test"])

    with pytest.raises(MCPExecutorError, match="timed out"):
        # We specify a tiny timeout just for the test
        executor.call_rpc(method="init", params={}, timeout=0.1)

    executor.close()


@patch("subprocess.Popen")
def test_executor_init_os_error(mock_popen):
    mock_popen.side_effect = OSError("No such file or directory")
    with pytest.raises(MCPExecutorError, match="Failed to start"):
        MCPExecutor(["not_real_binary"])


@patch("subprocess.Popen")
def test_executor_call_rpc_dead_process(mock_popen):
    mock_process = MockProcess(exit_code=1)
    mock_popen.return_value = mock_process
    executor = MCPExecutor(["test"])

    with pytest.raises(MCPExecutorError, match="dead"):
        executor.call_rpc(method="resources/list", params={})


@patch("subprocess.Popen")
def test_executor_call_rpc_write_os_error(mock_popen):
    mock_process = MockProcess()
    # Making stdin.write throw an OSError
    mock_process.stdin.write.side_effect = OSError("Broken pipe")
    mock_popen.return_value = mock_process

    executor = MCPExecutor(["test"])
    with pytest.raises(MCPExecutorError, match="Failed to write"):
        executor.call_rpc(method="resources/list", params={})


@patch("subprocess.Popen")
def test_executor_close_kill_fallback(mock_popen):
    mock_process = MockProcess()
    # Making wait timeout so kill is invoked
    mock_process.wait = MagicMock(side_effect=subprocess.TimeoutExpired(cmd="test", timeout=2))
    mock_process.kill = MagicMock()
    mock_popen.return_value = mock_process

    executor = MCPExecutor(["test"])
    executor.close()


@patch("subprocess.Popen")
def test_executor_call_rpc_stale_queue_discard(mock_popen):
    # Simulate a stale message from a PREVIOUS timeout arriving late, then the real one
    stale_response = '{"jsonrpc": "2.0", "id": 1, "result": {"stale": true}}\n'
    valid_response = '{"jsonrpc": "2.0", "id": 2, "result": {"fresh": true}}\n'

    mock_process = MockProcess(stdout_lines=[stale_response, valid_response])
    mock_popen.return_value = mock_process

    executor = MCPExecutor(["test"])

    # Force the internal request ID to start near 2 for the test,
    # or just do two calls. We'll do two calls, one timeout, one success.

    # First call times out internally if we patched it, but instead of patching timeout
    # let's just make the executor's ID = 2 and simulate.
    executor._request_id = 2

    response = executor.call_rpc(method="resources/list", params={})

    # Should skip the stale_response (id=1) and correctly return valid_response (id=2)
    assert response["result"] == {"fresh": True}

    # Also verify that the next call bumps ID to 3
    assert executor._request_id == 3
