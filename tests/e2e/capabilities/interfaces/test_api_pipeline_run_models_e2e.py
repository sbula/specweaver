# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`POST /pipelines/{name}/run` runs a step that needs a model, and leaves its cost history.

Proves: B-FLOW-07 FR-1, B-FLOW-07 FR-2, B-FLOW-07 FR-3

Settings file → REST → runner → a real adapter. Only HTTP is faked.

| Bucket | Case |
|---|---|
| Happy | a one-step review pipeline calls the model and completes |
| Boundary | not applicable — pipelines without a model step are proven by the pipeline API tests |
| Degradation | not applicable — a settings error is proven by the endpoint tests |
| Hostile | not applicable — the request names only a project, a spec and a pipeline |
"""

from __future__ import annotations

import sqlite3
import time
from typing import TYPE_CHECKING

import httpx2
import pytest
from starlette.testclient import TestClient

from tests.api_token import AUTH, TEST_TOKEN
from tests.fake_http import fake_httpx2

if TYPE_CHECKING:
    from pathlib import Path

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
hosted_spend_per_run = 10
tokens_per_run = 1000000
agent_turns = 5
"""

_ONE_REVIEW = """\
name: one_review
version: "1.0"
steps:
  - name: review_spec
    action: review
    target: spec
"""

_REPLY = {
    "id": "c1",
    "object": "chat.completion",
    "created": 1,
    "model": "m",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "VERDICT: ACCEPTED\nFine."},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
}


def test_a_rest_pipeline_run_calls_the_model_and_records_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database
    from specweaver.interfaces.api.app import create_app

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "one_review.yaml").write_text(_ONE_REVIEW, encoding="utf-8")
    db_path = data_dir / "specweaver.db"
    bootstrap_database(str(db_path))
    project = tmp_path / "proj"
    (project / "specs").mkdir(parents=True)
    (project / "specs" / "a_spec.md").write_text("# A\n## 1. Purpose\nDoes A.\n")

    with (
        TestClient(create_app(token=TEST_TOKEN, db=Database(db_path)), headers=AUTH) as client,
        fake_httpx2(lambda _request: httpx2.Response(200, json=_REPLY)) as seen,
    ):
        client.post(
            "/api/v1/projects", json={"name": "rest", "path": str(project), "scaffold": False}
        )
        started = client.post(
            "/api/v1/pipelines/one_review.yaml/run",
            json={"project": "rest", "spec": "specs/a_spec.md"},
        )
        assert started.status_code == 200, started.text
        run_id = started.json()["run_id"]
        for _ in range(100):
            status = client.get(f"/api/v1/runs/{run_id}").json().get("status")
            if status not in (None, "pending", "running", "not_started"):
                break
            time.sleep(0.05)
        # The usage is written as the run ends, a moment after its status reads completed.
        for _ in range(100):
            rows = _usage(db_path)
            if rows:
                break
            time.sleep(0.05)

    assert status == "completed", status
    assert seen
    assert rows == [("review_spec", "DAL_C", "passed")]


def _usage(db_path: Path) -> list[tuple[str, str, str]]:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT l.step_name, l.dal_level, o.outcome FROM llm_usage_log l "
            "JOIN llm_step_outcome o USING (run_id, step_name)"
        ).fetchall()
