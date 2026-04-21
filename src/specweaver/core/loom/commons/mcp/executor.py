from __future__ import annotations

import logging
import queue
import subprocess
import threading
from typing import Any, cast

from specweaver.commons import json

logger = logging.getLogger(__name__)


class MCPExecutorError(Exception):
    """Raised when an MCP operation fails or times out."""


class MCPExecutor:
    """Synchronous JSON-RPC executor over stdio for MCP."""

    def __init__(self, command: list[str], env: dict[str, str] | None = None) -> None:
        """Initialize the MCP subprocess securely."""
        self._command = command

        try:
            self._process = subprocess.Popen(
                self._command,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
            )
        except OSError as e:
            raise MCPExecutorError(f"Failed to start MCP server process: {e}") from e

        self._queue: queue.Queue[str] = queue.Queue()
        self._request_id: int = 1
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()

    def _read_loop(self) -> None:
        """Background thread reading from subprocess stdout."""
        if not self._process.stdout:
            return

        try:
            for line in iter(self._process.stdout.readline, ""):
                if not line:
                    break
                self._queue.put(line)
        except (ValueError, OSError):
            # Happens during shutdown if file closed
            pass

    def is_alive(self) -> bool:
        """Return True if the subprocess is still running."""
        return self._process.poll() is None

    def close(self) -> None:
        """Terminate process and close streams."""
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self._process.kill()

        if self._process.stdin:
            self._process.stdin.close()
        if self._process.stdout:
            self._process.stdout.close()

    def call_rpc(self, method: str, params: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
        """Call an MCP JSON-RPC method synchronously.

        Args:
            method: The method name to execute (e.g., 'resources/list').
            params: Parameters dictionary.
            timeout: Maximum wait time in seconds.
        """
        if not self.is_alive():
            raise MCPExecutorError("Cannot call RPC, MCP process is dead.")

        expected_id = self._request_id
        self._request_id += 1

        payload = {
            "jsonrpc": "2.0",
            "id": expected_id,
            "method": method,
            "params": params,
        }

        request_str = json.dumps(payload)

        try:
            if self._process.stdin:
                self._process.stdin.write(request_str + "\n")
                self._process.stdin.flush()
        except OSError as e:
            raise MCPExecutorError(f"Failed to write to MCP stdin: {e}") from e

        # We need to wait up to timeout seconds
        try:
            while True:
                line = self._queue.get(timeout=timeout)
                try:
                    response_payload = json.loads(line)
                    if "jsonrpc" in response_payload and response_payload.get("id") == expected_id:
                        return cast("dict[str, Any]", response_payload)
                except json.JSONDecodeError:
                    # Ignore non-JSON lines (e.g. Docker startup logs)
                    continue
        except queue.Empty as e:
            raise MCPExecutorError(f"Operation timed out after {timeout}s waiting for JSON-RPC response.") from e
