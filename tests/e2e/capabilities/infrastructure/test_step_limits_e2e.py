# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw run`: a step that has spent what similar steps usually cost asks before more (US-04 L1, L2).

Proves: B-FLOW-07 FR-4, B-FLOW-07 FR-5, B-FLOW-07 FR-6

| Bucket | Case |
|---|---|
| Happy | not applicable — a step within its limit is proven by the integration test |
| Boundary | a group with 10 passed steps → the step's retry, after it spent its limit, asks first |
| Degradation | a group with 9 passed steps → no step limit, the call is sent without a question |
| Hostile | not applicable — the history is written by SpecWeaver, never by input |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import httpx2
import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.fake_http import fake_httpx2

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.config.database import Database

runner = CliRunner()
pytestmark = pytest.mark.e2e

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2

[roles]
default = { model = "qwen3-coder-next@gb10", max_output_tokens = 1000 }

[brake]
hosted_spend_per_run = 100
tokens_per_run = 100000000
agent_turns = 10

[step_limits]
percentile = 90
min_steps = 10
"""

_ONE_REVIEW = """\
name: one_review
version: "1.0"
steps:
  - name: review_spec
    action: review
    target: spec
    gate:
      type: auto
      condition: all_passed
      on_fail: retry
      max_retries: 1
"""

_REPLY = {
    "id": "c1",
    "object": "chat.completion",
    "created": 1,
    "model": "m",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "VERDICT: DENIED\n- missing tests"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
}


def _history(db: Database, steps: int) -> None:
    with db.connect() as conn:
        for n in range(steps):
            run = f"old-{n}"
            conn.execute(
                "INSERT INTO llm_usage_log (timestamp, project_name, task_type, model, provider, "
                "prompt_tokens, completion_tokens, total_tokens, estimated_cost, duration_ms, "
                "run_id, server, dal_level, step_name) VALUES (?, 'p', 'review', "
                "'qwen3-coder-next', 'x', 0, 0, 15, NULL, 1, ?, 'gb10', 'DAL_C', 'review_spec')",
                (f"2026-10-01T10:{n:02d}:00+00:00", run),
            )
            conn.execute("INSERT INTO llm_step_outcome VALUES (?, 'review_spec', 'passed')", (run,))


def _run(tmp_path: Path, isolate_env: Path, db: Database, steps: int):
    (isolate_env / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    _history(db, steps)
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "steps-demo", "--path", str(project)]).exit_code == 0
    assert runner.invoke(app, ["use", "steps-demo"]).exit_code == 0
    spec = project / "specs" / "a_spec.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# A\n## 1. Purpose\nDoes A.\n", encoding="utf-8")
    pipeline = tmp_path / "one_review.yaml"
    pipeline.write_text(_ONE_REVIEW, encoding="utf-8")
    with (
        patch("specweaver.interfaces.cli._core.stdin_is_interactive", return_value=True),
        patch("rich.prompt.Prompt.ask", return_value="y") as asked,
        fake_httpx2(lambda _request: httpx2.Response(200, json=_REPLY)) as seen,
    ):
        runner.invoke(app, ["run", str(pipeline), str(spec), "--project", str(project)])
    return [str(call.args[0]) for call in asked.call_args_list], seen


def test_a_step_that_would_cost_more_than_usual_asks_first(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    questions, seen = _run(tmp_path, _isolate_env, _mock_db, steps=10)

    assert any("step_limits.review.review_spec" in q for q in questions), questions
    assert len(seen) == 2, "the user said yes, but the retry's call was never sent"


def test_too_little_history_sets_no_step_limit(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    questions, seen = _run(tmp_path, _isolate_env, _mock_db, steps=9)

    assert not any("step_limits" in q for q in questions), questions
    assert len(seen) == 2
