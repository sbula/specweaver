# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A registered project with two modules: `billing` consumes `payments`.

`billing` declares an MCP server and the resource it consumes; `payments` declares neither unless
asked. Runs are built from it with the real run setup, so a test sees the slot shapes a user's run
gets, never ones the test chose.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.flow.engine.models import PipelineDefinition, StepAction, StepTarget
from specweaver.infrastructure.database import Database
from specweaver.interfaces.run_setup.builder import RunRequest
from tests.fixtures.db_utils import register_test_project

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

RESOURCE = "mcp://invoices/invoices_table"
PAYLOAD = "declared_by_billing"

MACHINE_SETTINGS = """schema_version = 1

[servers.local]
kind = "openai-compatible"
base_url = "http://localhost:8000/v1"
private = true
max_parallel = 1

[roles]
default = { model = "local-model@local", max_output_tokens = 4096 }
"""

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


def _servers_block(server: Path) -> str:
    return (
        "mcp_servers:\n"
        "  invoices:\n"
        f"    command: [{sys.executable!r}]\n"
        f"    args: [{str(server)!r}]\n"
        "consumes_resources:\n"
        f"  - {RESOURCE}\n"
    )


def module_graph_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    servers_on: str = "billing",
    manifests: bool = True,
) -> tuple[Database, Path]:
    """The database and the project root; `servers_on` names the module declaring the server."""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    (data / "settings.toml").write_text(MACHINE_SETTINGS, encoding="utf-8")
    bootstrap_database(str(data / "specweaver.db"))
    db = Database(data / "specweaver.db")

    root = tmp_path / "proj"
    (root / "specs").mkdir(parents=True)
    for name in ("billing", "payments", "orphan", "solo"):
        (root / "specs" / f"{name}_spec.md").write_text(f"# {name}\n", encoding="utf-8")
    server = tmp_path / "server.py"
    server.write_text(SERVER, encoding="utf-8")

    if manifests:
        manifests_of = {
            "billing": "name: billing\npurpose: Bills customers.\narchetype: pure-logic\n"
            "consumes:\n  - payments\n",
            "payments": "name: payments\npurpose: Moves money.\narchetype: adapter\n",
            "solo": "name: solo\npurpose: Stands alone.\narchetype: pure-logic\n",
        }
        for name, text in manifests_of.items():
            (root / name).mkdir()
            if name == servers_on:
                text += _servers_block(server)
            (root / name / "context.yaml").write_text(text, encoding="utf-8")

    register_test_project(db, "proj", str(root))
    return db, root


def run_request(
    db: Database, root: Path, module: str = "billing", action: StepAction = StepAction.VALIDATE
) -> RunRequest:
    """A one-step run on `specs/<module>_spec.md`."""
    pipeline = PipelineDefinition.create_single_step("one", action, StepTarget.SPEC)
    return RunRequest(
        project_root=root,
        spec_path=root / "specs" / f"{module}_spec.md",
        pipeline=pipeline,
        project="proj",
        db=db,
    )
