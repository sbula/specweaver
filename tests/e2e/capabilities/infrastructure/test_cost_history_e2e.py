# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A finished command leaves a cost history: each call with its server, DAL, step and outcome.

Proves: B-FLOW-07 FR-2, B-FLOW-07 FR-3, B-FLOW-07 FR-11

US-04 paths L3 and L4. `sw implement` on a GB10 model, only HTTP faked.

| Bucket | Case |
|---|---|
| Happy | every call of the run is stored with server, DAL, step and the step's outcome `passed` |
| Boundary | a project with no DAL in any `context.yaml` → the rows say `DAL_C` (L4) |
| Degradation | not applicable — failed and parked steps are proven by the runner integration test |
| Hostile | the same model on two servers is shown once per server by `sw costs` |
"""

from __future__ import annotations

import re
import sqlite3
from typing import TYPE_CHECKING

import httpx2
import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.fake_http import fake_httpx2

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.e2e

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2

[servers.spare]
kind = "openai-compatible"
base_url = "http://spare:8000/v1"
private = true
max_parallel = 2

[roles]
default = { model = "qwen3-coder-next@gb10", max_output_tokens = 1000 }
draft = { model = "qwen3-coder-next@spare", max_output_tokens = 1000 }

[brake]
hosted_spend_per_run = 100
tokens_per_run = 100000000
agent_turns = 10
"""

_REPLY = {
    "id": "c1",
    "object": "chat.completion",
    "created": 1,
    "model": "m",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "def greet():\n    pass\n"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
}


@pytest.mark.usefixtures("_mock_db", "stub_implement_qa")
def test_a_finished_run_leaves_its_cost_history(tmp_path: Path, _isolate_env: Path) -> None:
    (_isolate_env / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "history-demo", "--path", str(project)]).exit_code == 0
    spec = project / "specs" / "greeter_spec.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# Greeter\n## 1. Purpose\nGreets.\n", encoding="utf-8")

    with fake_httpx2(lambda _request: httpx2.Response(200, json=_REPLY)):
        done = runner.invoke(app, ["implement", str(spec), "--project", str(project)])
    costs = runner.invoke(app, ["costs"])

    assert done.exit_code == 0, done.output
    with sqlite3.connect(_isolate_env / "specweaver.db") as conn:
        rows = conn.execute(
            "SELECT l.server, l.dal_level, l.step_name, o.outcome FROM llm_usage_log l "
            "LEFT JOIN llm_step_outcome o USING (run_id, step_name)"
        ).fetchall()
    assert rows
    assert {(server, dal, outcome) for server, dal, _step, outcome in rows} == {
        ("gb10", "DAL_C", "passed")
    }
    shown = " ".join(costs.output.split())
    gb10 = shown.split("qwen3-coder-next@gb10")[1].split("qwen3-coder-next@spare")[0]
    spare = shown.split("qwen3-coder-next@spare")[1]
    assert re.search(r"this month \S+ \S+ \+ \d+ unknown", gb10), gb10
    assert re.search(r"this month \S+ \S+$", spare.strip()), spare


@pytest.mark.usefixtures("_mock_db")
def test_spend_recorded_before_servers_were_stored_is_still_shown(
    tmp_path: Path, _isolate_env: Path
) -> None:
    from datetime import UTC, datetime

    (_isolate_env / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "old-rows", "--path", str(project)]).exit_code == 0
    assert runner.invoke(app, ["use", "old-rows"]).exit_code == 0
    with sqlite3.connect(_isolate_env / "specweaver.db") as conn:
        conn.execute(
            "INSERT INTO llm_usage_log (timestamp, project_name, task_type, model, provider, "
            "prompt_tokens, completion_tokens, total_tokens, estimated_cost, duration_ms, run_id) "
            "VALUES (?, 'old-rows', 'draft', 'qwen3-coder-next', 'x', 1, 1, 2, NULL, 1, 'r')",
            (datetime.now(UTC).isoformat(),),
        )

    costs = runner.invoke(app, ["costs"])

    shown = " ".join(costs.output.split())
    assert re.search(
        r"qwen3-coder-next, server not recorded: this month \S+ \S+ \+ 1 unknown", shown
    ), shown
