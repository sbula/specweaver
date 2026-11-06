# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The API refuses a project whose root does not decide its language, before any run starts.

Proves: TECH-079 FR-8

A real app, database and project folder; the refusal is 400 `PROJECT_UNDECIDED` with the message.

| Bucket | Case |
|---|---|
| Happy | with `[implement] language` set, the same mixed root starts a pipeline run |
| Boundary | `POST /pipelines/{name}/run` and a resume refuse like `POST /implement` (Q2 [agreed 2026-11-06]); with session isolation on, any API door refuses |
| Degradation | not applicable — the refusal is the degraded path; no dependency is involved |
| Hostile | pyproject.toml beside package.json and tsconfig.json: 400, the message names the setting, no step runs |
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from tests.api_token import AUTH, TEST_TOKEN
from tests.scripted_llm import doubled_llm

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.integration

_GATED = """name: gated
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
_PIPELINE = """name: one_step
version: "1.0"
steps:
  - name: only
    action: bash
    target: script
    params: {script: s.sh, args: ["ran"]}
"""


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, Path]]:
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database
    from specweaver.interfaces.api.app import create_app

    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    (data / "settings.toml").write_text("[serve]\nmax_runs = 3\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    bootstrap_database(str(data / "specweaver.db"))
    project = tmp_path / "proj"
    own = project / ".specweaver" / "pipelines"
    own.mkdir(parents=True)
    (own / "one_step.yaml").write_text(_PIPELINE, encoding="utf-8")
    (own / "gated.yaml").write_text(_GATED, encoding="utf-8")
    (project / "specs").mkdir()
    (project / "specs" / "a_spec.md").write_text("# A\n## 1. Purpose\nA.\n", encoding="utf-8")
    scripts = project / ".specweaver" / "scripts"
    scripts.mkdir()
    (scripts / "s.sh").write_text('#!/usr/bin/env bash\necho "$1" >> steps.log\n', encoding="utf-8")
    for name, text in {
        "pyproject.toml": "[project]\nname = 'x'\n",
        "package.json": "{}",
        "tsconfig.json": "{}",
    }.items():
        (project / name).write_text(text, encoding="utf-8")
    with TestClient(
        create_app(token=TEST_TOKEN, db=Database(data / "specweaver.db")), headers=AUTH
    ) as client:
        client.post(
            "/api/v1/projects", json={"name": "rest", "path": str(project), "scaffold": False}
        )
        yield client, project


def _start(client: TestClient) -> Any:
    return client.post(
        "/api/v1/pipelines/one_step/run", json={"project": "rest", "spec": "specs/a_spec.md"}
    )


def _refused(answer: Any) -> None:
    assert answer.status_code == 400, answer.json()
    assert answer.json()["error_code"] == "PROJECT_UNDECIDED"
    assert "set [implement] language in specweaver.toml" in answer.json()["detail"]


def test_implement_refuses_a_mixed_root(world: tuple[TestClient, Path]) -> None:
    client, _project = world

    with (
        doubled_llm(MagicMock()),
        patch("specweaver.core.flow.engine.runner.PipelineRunner") as runner_class,
    ):
        answer = client.post(
            "/api/v1/implement", json={"project": "rest", "file": "specs/a_spec.md"}
        )

    _refused(answer)
    assert not runner_class.called


def test_a_pipeline_run_refuses_a_mixed_root(world: tuple[TestClient, Path]) -> None:
    client, project = world

    _refused(_start(client))
    assert not (project / "steps.log").exists()


def test_the_language_setting_lets_the_run_start(world: tuple[TestClient, Path]) -> None:
    client, project = world
    (project / "specweaver.toml").write_text('[implement]\nlanguage = "python"\n')

    with patch("specweaver.core.flow.engine.runner.PipelineRunner") as runner_class:
        runner_class.return_value.run = AsyncMock()
        answer = _start(client)

    assert answer.status_code == 200, answer.json()
    assert runner_class.call_args.args[1].isolation.profile.language == "python"


def test_a_resume_of_a_project_that_became_undecided_is_refused(
    world: tuple[TestClient, Path],
) -> None:
    client, project = world
    (project / "specweaver.toml").write_text('[implement]\nlanguage = "python"\n')
    answer = client.post(
        "/api/v1/pipelines/gated/run", json={"project": "rest", "spec": "specs/a_spec.md"}
    )
    assert answer.status_code == 200, answer.json()
    run_id = answer.json()["run_id"]
    for _ in range(100):
        if client.get(f"/api/v1/runs/{run_id}").json().get("status") in {"parked", "failed"}:
            break
        time.sleep(0.05)
    (project / "specweaver.toml").write_text("")

    _refused(client.post(f"/api/v1/runs/{run_id}/gate", json={"action": "approve"}))
    assert (project / "steps.log").read_text(encoding="utf-8").split() == ["one"]


def test_any_api_door_refuses_when_session_isolation_needs_the_language(
    world: tuple[TestClient, Path],
) -> None:
    """Q1 [agreed 2026-11-06]: a door that does not need the language still never runs unisolated."""
    from specweaver.core.config.database import Database
    from specweaver.core.flow.engine.parser import load_pipeline
    from specweaver.interfaces.api.errors import SpecWeaverAPIError
    from specweaver.interfaces.api.v1.run_doors import build_api_run

    _client, project = world
    (project / "specweaver.toml").write_text("[sandbox]\nenforce_session_isolation = true\n")
    pipeline = load_pipeline(project / ".specweaver" / "pipelines" / "one_step.yaml")
    db = Database(project.parent / "data" / "specweaver.db")

    with pytest.raises(SpecWeaverAPIError) as caught:
        asyncio.run(
            build_api_run(project, project / "specs" / "a_spec.md", pipeline, project="rest", db=db)
        )

    assert (caught.value.status_code, caught.value.error_code) == (400, "PROJECT_UNDECIDED")
