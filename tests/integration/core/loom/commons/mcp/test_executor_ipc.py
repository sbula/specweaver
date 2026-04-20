from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from specweaver.core.loom.commons.mcp.executor import MCPExecutor

if TYPE_CHECKING:
    import pathlib


def test_executor_ipc_real_subprocess(tmp_path: pathlib.Path) -> None:
    # Create the mock server script
    # It reads one line from stdin (the JSON request), writes some stderr/stdout noise, then responding
    script_content = """
import sys
import time

def main():
    # Write some garbage startup noise
    sys.stdout.write("Booting MCP fake server...\\n")
    sys.stdout.flush()

    # Block on stdin like a real MCP server
    req = sys.stdin.readline()
    if not req:
        return

    # Simulate work
    time.sleep(0.5)

    # Output standard out noise
    sys.stdout.write("Processing...\\n")
    sys.stdout.write('{"invalid json": true\\n') # broken json
    sys.stdout.flush()

    # Assuming internal expected structure, the request sent by MCPExecutor has "id": 1 originally.
    # But since it sends `id: <request_id>`, we must parse the request and return its ID.
    import json
    req_json = json.loads(req)
    req_id = req_json.get("id", 1)

    # Output valid response
    resp = {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {"status": "ok"}
    }

    sys.stdout.write(json.dumps(resp) + "\\n")
    sys.stdout.flush()

if __name__ == "__main__":
    main()
"""
    script_path = tmp_path / "mock_mcp_server.py"
    script_path.write_text(script_content)

    # Boot executor with real sys.executable targeting the script
    executor = MCPExecutor([sys.executable, str(script_path)])

    assert executor.is_alive()

    # Call it! It should seamlessly idle 0.5s, ignore the garbage, and return the result.
    response = executor.call_rpc(method="resources/list", params={"test": True})

    assert response["result"] == {"status": "ok"}

    executor.close()
    assert not executor.is_alive()
