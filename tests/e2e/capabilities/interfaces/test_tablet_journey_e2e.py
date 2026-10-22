# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The tablet journey: a run waiting for a human is finished from a browser, through `sw serve`.

Proves: D-UI-01 FR-8

The served app as a browser meets it: no header, only the address `sw serve` prints and the cookie
it gets there. A program starts the run; the browser lists runs, opens the parked one and approves
its gate in the dashboard; the run's second step runs.

| Bucket | Case |
|---|---|
| Happy | open the printed address, see the parked run, approve it, the run completes |
| Boundary | the run detail page shows the gate before the answer |
| Degradation | not applicable — a failed step is the gate tests' case |
| Hostile | the same approve posted by a page without the cookie is refused, and the run stays parked |
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


def _app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Path]:
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
    return create_app(token=TEST_TOKEN, db=Database(data / "specweaver.db")), project


def _park(client: TestClient, project: Path) -> str:
    """A program, with the header, registers the project and starts a run that parks at its gate."""
    client.post(
        "/api/v1/projects",
        json={"name": "rest", "path": str(project), "scaffold": False},
        headers=AUTH,
    )
    run_id = client.post(
        "/api/v1/pipelines/two_steps/run",
        json={"project": "rest", "spec": "specs/a_spec.md"},
        headers=AUTH,
    ).json()["run_id"]
    assert _status(client, run_id, {"parked", "failed"}) == "parked"
    return run_id


def _status(client: TestClient, run_id: str, wanted: set[str]) -> str:
    for _ in range(100):
        status = client.get(f"/api/v1/runs/{run_id}", headers=AUTH).json().get("status")
        if status in wanted:
            return status
        time.sleep(0.05)
    return client.get(f"/api/v1/runs/{run_id}", headers=AUTH).json().get("status")


def test_a_parked_run_is_finished_from_a_browser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, project = _app(tmp_path, monkeypatch)

    with TestClient(app) as browser:
        run_id = _park(browser, project)
        assert browser.get(f"/dashboard?token={TEST_TOKEN}").status_code == 200
        assert run_id in browser.get("/dashboard/runs").text
        assert "approve" in browser.get(f"/dashboard/runs/{run_id}").text.lower()
        answered = browser.post(f"/dashboard/runs/{run_id}/gate", data={"action": "approve"})
        assert answered.status_code == 200, answered.text
        assert _status(browser, run_id, {"completed", "failed"}) == "completed"

    assert (project / "steps.log").read_text(encoding="utf-8").split() == ["one", "two"]


def test_a_page_without_the_cookie_cannot_answer_the_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, project = _app(tmp_path, monkeypatch)

    with TestClient(app) as other_page:
        run_id = _park(other_page, project)
        refused = other_page.post(f"/dashboard/runs/{run_id}/gate", data={"action": "approve"})
        status = _status(other_page, run_id, {"parked"})

    assert refused.status_code == 401
    assert status == "parked"
