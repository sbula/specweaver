# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A run started over REST parks at a human gate, and approving the gate finishes it.

Proves: D-UI-01 FR-4

The run names its project by the name it is registered under. It used to store the project's
folder name, so `POST /runs/{id}/gate` answered "Project 'proj' not found" for every project whose
name was not its folder's, and the run stayed parked.

| Bucket | Case |
|---|---|
| Happy | approve: the second step runs and the run completes |
| Boundary | the run id the start returns is the stored run's id |
| Degradation | not applicable — an unknown run is a 404, proven by the endpoint tests |
| Hostile | not applicable — the request names only a project, a spec and a pipeline |
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import pytest
from starlette.testclient import TestClient

from tests.api_token import AUTH, TEST_TOKEN

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.e2e

_PIPELINE = """name: two_steps
version: "1.0"
steps:
  - name: first
    action: bash
    target: script
    params: {script: s.sh, args: ["one"]}
    gate: {type: hitl, condition: completed}
  - name: second
    action: bash
    target: script
    params: {script: s.sh, args: ["two"]}
"""


def _wait(client: TestClient, run_id: str, wanted: set[str]) -> dict[str, Any]:
    for _ in range(100):
        state = client.get(f"/api/v1/runs/{run_id}").json()
        if state.get("status") in wanted:
            return state
        time.sleep(0.05)
    return client.get(f"/api/v1/runs/{run_id}").json()


def test_approving_the_gate_finishes_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database
    from specweaver.interfaces.api.app import create_app

    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    (data / "settings.toml").write_text("[serve]\nmax_runs = 3\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    own = tmp_path / "proj" / ".specweaver" / "pipelines"
    own.mkdir(parents=True)
    (own / "two_steps.yaml").write_text(_PIPELINE, encoding="utf-8")
    bootstrap_database(str(data / "specweaver.db"))
    project = tmp_path / "proj"
    (project / "specs").mkdir(parents=True)
    (project / "specs" / "a_spec.md").write_text("# A\n", encoding="utf-8")
    scripts = project / ".specweaver" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "s.sh").write_text('#!/usr/bin/env bash\necho "$1" >> steps.log\n', encoding="utf-8")

    with TestClient(
        create_app(token=TEST_TOKEN, db=Database(data / "specweaver.db")), headers=AUTH
    ) as client:
        client.post(
            "/api/v1/projects", json={"name": "rest", "path": str(project), "scaffold": False}
        )
        started = client.post(
            "/api/v1/pipelines/two_steps/run",
            json={"project": "rest", "spec": "specs/a_spec.md"},
        ).json()
        run_id = started["run_id"]
        parked = _wait(client, run_id, {"parked", "failed"})
        assert parked["status"] == "parked", parked
        assert parked["run_id"] == run_id

        answer = client.post(f"/api/v1/runs/{run_id}/gate", json={"action": "approve"})
        assert answer.status_code == 200, answer.json()
        done = _wait(client, run_id, {"completed", "failed"})

    assert done["status"] == "completed", done
    assert (project / "steps.log").read_text(encoding="utf-8").split() == ["one", "two"]


def test_sw_resume_finds_a_parked_run_of_a_project_named_unlike_its_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`sw resume` with no run id looks runs up by the registered name, which the run now stores."""
    from typer.testing import CliRunner

    from specweaver.interfaces.cli.main import app

    runner = CliRunner()
    project = tmp_path / "folder"
    project.mkdir()
    assert runner.invoke(app, ["init", "named", "--path", str(project)]).exit_code == 0
    (project / "specs" / "a_spec.md").write_text("# A\n", encoding="utf-8")
    script = project / ".specweaver" / "scripts" / "s.sh"
    script.write_text('#!/usr/bin/env bash\necho "$1" >> steps.log\n', encoding="utf-8")
    (project / "two_steps.yaml").write_text(_PIPELINE, encoding="utf-8")
    monkeypatch.chdir(project)

    runner.invoke(app, ["run", "two_steps.yaml", "specs/a_spec.md", "--project", str(project)])
    resumed = runner.invoke(app, ["resume"], input="y\n")

    assert "No resumable runs" not in resumed.output, resumed.output
