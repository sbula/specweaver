from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from specweaver.core.loom.atoms.base import AtomStatus
from specweaver.core.loom.atoms.mcp.atom import MCPAtom

if TYPE_CHECKING:
    import pathlib

@pytest.mark.integration
def test_atom_ipc_lifecycle(tmp_path: pathlib.Path) -> None:
    # We must mock the sequence of _intent_initialize and _intent_read_resource.
    # The atom's _intent_initialize makes 2 calls: "initialize" and then "notifications/initialized".
    # Then we make a "resources/read" call.
    script_content = """
import sys
import json
import time

def read_request():
    req = sys.stdin.readline()
    if not req:
        return None
    return json.loads(req)

def write_response(resp):
    sys.stdout.write(json.dumps(resp) + "\\n")
    sys.stdout.flush()

def main():
    while True:
        req = read_request()
        if not req:
            break

        method = req.get("method")
        req_id = req.get("id")

        if method == "initialize":
            write_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"capabilities": {"logging": {}}}
            })
        elif method == "notifications/initialized":
            # Notifications do not require an explicit ID/Response back to the thread pump block,
            # wait, the Executor call_rpc currently expects an ID unless it's a blind send?
            # Actually, call_rpc uses `yield`, so it ALWAYS expects a response ID back right now!
            # If the Atom sends a notification via call_rpc, our test script must return one to unlock it.
            write_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {}
            })
        elif method == "resources/read":
            write_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "contents": [{"uri": "test://", "text": "Mock IPC Body"}]
                }
            })

if __name__ == "__main__":
    main()
"""
    script_path = tmp_path / "mock_mcp_atom_server.py"
    script_path.write_text(script_content)

    # Initialize Atom directly mapped using the standard sys.executable IPC bridge
    atom = MCPAtom([sys.executable, str(script_path)])

    # Actually boot the subprocess target manually since we bypassed .run()
    atom._ensure_started()

    # Handshake Phase
    init_result = atom._intent_initialize({
        "intent": "initialize",
        "params": {"capabilities": {}}
    })

    assert init_result.status == AtomStatus.SUCCESS
    assert init_result.exports == {"capabilities": {"logging": {}}}

    # Read Resource Phase
    read_result = atom._intent_read_resource({
        "intent": "read_resource",
        "params": {"uri": "test://"}
    })

    assert read_result.status == AtomStatus.SUCCESS
    assert read_result.exports["contents"][0]["text"] == "Mock IPC Body"

    atom.close()
