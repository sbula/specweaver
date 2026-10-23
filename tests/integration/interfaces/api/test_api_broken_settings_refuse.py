# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An API run on a project with a broken setting starts nothing and names the setting.

Proves: TECH-076 FR-4, TECH-076 NFR-1, TECH-076 NFR-3

The real app, settings files and project; the pipeline's run is replaced by one that records it was
started, so "no run" is observed, not inferred.

| Bucket | Case |
|---|---|
| Happy | a valid project starts its run (200) |
| Boundary | resuming a parked run on a project broken after it parked is refused the same way |
| Degradation | not applicable — other lookup failures keep their best effort (design decision 5) |
| Hostile | a broken `[sandbox]`, `[standards]` or DAL file → 500 `SANDBOX_SETTINGS` / `STANDARDS_SETTINGS` / `DAL_DEFINITIONS`, the message names file, key and line, no run started |
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest
from starlette.testclient import TestClient

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.interfaces.api.app import create_app
from tests.api_token import AUTH, TEST_TOKEN

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.integration

_PIPELINE = """\
name: one_check
version: "1.0"
steps:
  - name: check_spec
    action: validate
    target: spec
"""


@pytest.fixture()
def world(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, Path, list[str]]]:
    data = tmp_path / "data"
    data.mkdir()
    (data / "settings.toml").write_text("[serve]\nmax_runs = 2\n", encoding="utf-8")
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    monkeypatch.chdir(tmp_path)
    project = tmp_path / "proj"
    (project / ".specweaver" / "pipelines").mkdir(parents=True)
    (project / ".specweaver" / "pipelines" / "one_check.yaml").write_text(_PIPELINE)
    (project / "specs").mkdir()
    (project / "specs" / "a_spec.md").write_text("# A\n## 1. Purpose\nDoes A.\n")
    started: list[str] = []

    async def _records(_self: PipelineRunner, *_args: object, **kwargs: object) -> None:
        started.append(str(kwargs.get("run_id", "")))

    monkeypatch.setattr(PipelineRunner, "run", _records)
    monkeypatch.setattr(PipelineRunner, "resume", _records, raising=False)
    path = data / "specweaver.db"
    bootstrap_database(str(path))
    with TestClient(create_app(token=TEST_TOKEN, db=Database(path)), headers=AUTH) as client:
        client.post(
            "/api/v1/projects", json={"name": "rest", "path": str(project), "scaffold": False}
        )
        yield client, project, started


def _run(client: TestClient):
    return client.post(
        "/api/v1/pipelines/one_check/run", json={"project": "rest", "spec": "specs/a_spec.md"}
    )


def test_a_valid_project_starts_its_run(world: tuple[TestClient, Path, list[str]]) -> None:
    client, project, started = world
    (project / "specweaver.toml").write_text('[sandbox]\nexecution_mode = "host"\n')

    answer = _run(client)

    assert answer.status_code == 200, answer.text
    # The run starts in a background task, after the answer: wait for it, briefly.
    deadline = time.monotonic() + 5
    while not started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert started == [answer.json()["run_id"]]


@pytest.mark.parametrize(
    ("file", "text", "code", "where"),
    [
        (
            "specweaver.toml",
            '[sandbox]\n\nexecution_mod = "container"\n',
            "SANDBOX_SETTINGS",
            "specweaver.toml:3: sandbox.execution_mod",
        ),
        (
            "specweaver.toml",
            "[sandbox]\nenforce_session_isolation = 3\n",
            "SANDBOX_SETTINGS",
            "specweaver.toml:2: sandbox.enforce_session_isolation",
        ),
        (
            "specweaver.toml",
            '[standards]\nmod = "best_practice"\n',
            "STANDARDS_SETTINGS",
            "specweaver.toml:2: standards.mod",
        ),
        (
            ".specweaver/dal_definitions.yaml",
            "matrx:\n  DAL_E: {}\n",
            "DAL_DEFINITIONS",
            "dal_definitions.yaml:1: matrx",
        ),
    ],
)
def test_a_broken_setting_starts_no_run(
    world: tuple[TestClient, Path, list[str]], file: str, text: str, code: str, where: str
) -> None:
    client, project, started = world
    (project / file).write_text(text, encoding="utf-8")

    answer = _run(client)

    assert answer.status_code == 500, answer.text
    assert answer.json()["error_code"] == code
    assert where in answer.json()["detail"]
    assert started == []


def test_a_parked_run_does_not_resume_on_a_broken_setting(
    world: tuple[TestClient, Path, list[str]],
) -> None:
    from specweaver.core.config.paths import state_db_path
    from specweaver.core.flow.engine.state import PipelineRun, RunStatus
    from specweaver.core.flow.engine.store import StateStore

    client, project, started = world
    StateStore(state_db_path()).save_run(
        PipelineRun(
            run_id="r-parked",
            pipeline_name="one_check",
            project_name="rest",
            spec_path=str(project / "specs" / "a_spec.md"),
            status=RunStatus.PARKED,
            started_at="2026-10-23T00:00:00",
            updated_at="2026-10-23T00:00:00",
        )
    )
    (project / "specweaver.toml").write_text('[sandbox]\nexecution_mod = "container"\n')

    refused = client.post("/api/v1/runs/r-parked/resume")

    assert refused.status_code == 500, refused.text
    assert refused.json()["error_code"] == "SANDBOX_SETTINGS"
    assert started == []
