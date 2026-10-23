# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every API door hands its run the same parts the CLI does, from the request's project.

Proves: TECH-077 FR-12, TECH-077 FR-3
Proves: TECH-013 FR-1, TECH-013 FR-2

A real app, database and project (rule file, `[docs]`, stored standards, DAL_B, git, per-step
policy). The runner's `run`/`resume` are replaced only to capture the context a door built.

| Bucket | Case |
|---|---|
| Happy | a run, a resume and a gate approval each get the rule file, standards, sections and per-step policy |
| Boundary | a high-DAL run gets the per-run worktree |
| Degradation | a background run whose worktree cannot start is recorded failed, naming it |
| Hostile | a broken `[docs]`, `[autonomy]`, `[sandbox]`, `[standards]` or `settings.toml` answers 500 with its own code; no run starts |
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

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

_REAL_RUN = PipelineRunner.run

_PIPELINE = """\
name: one_check
version: "1.0"
steps:
  - name: check_spec
    action: validate
    target: spec
"""

_SETTINGS = """[[docs.rule]]
paths = ["docs/**"]
access = "open"

[sandbox]
enforce_worktree_isolation = true
"""


def _project(tmp_path: Path, db: Database) -> tuple[Path, Any]:
    from specweaver.workspace.store import WorkspaceRepository

    root = tmp_path / "proj"
    (root / ".specweaver" / "pipelines").mkdir(parents=True)
    (root / ".specweaver" / "pipelines" / "one_check.yaml").write_text(_PIPELINE)
    (root / "specs").mkdir()
    (root / "specs" / "orders_spec.md").write_text("# Orders\n## 1. Purpose\nOrders.\n")
    (root / "CONSTITUTION.md").write_text("# Rules\nApi rule.\n", encoding="utf-8")
    (root / "specweaver.toml").write_text(_SETTINGS, encoding="utf-8")
    (root / "context.yaml").write_text(
        "name: orders\narchetype: pure-logic\noperational:\n  dal_level: DAL_B\n", encoding="utf-8"
    )
    (root / ".git").mkdir()

    async def _save() -> None:
        async with db.async_session_scope() as session:
            await WorkspaceRepository(session).save_standard(
                "rest", ".", "python", "naming", {"style": "api_case"}, 0.9
            )

    return root, _save


@pytest.fixture()
def world(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, Path, list[Any]]]:
    data = tmp_path / "data"
    data.mkdir()
    (data / "settings.toml").write_text("[serve]\nmax_runs = 2\n", encoding="utf-8")
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    monkeypatch.chdir(tmp_path)
    path = data / "specweaver.db"
    bootstrap_database(str(path))
    db = Database(path)
    project, save_standard = _project(tmp_path, db)
    contexts: list[Any] = []

    async def _capture(self: PipelineRunner, *_args: object, **_kwargs: object) -> None:
        contexts.append(self._context)

    monkeypatch.setattr(PipelineRunner, "run", _capture)
    monkeypatch.setattr(PipelineRunner, "resume", _capture, raising=False)
    with TestClient(create_app(token=TEST_TOKEN, db=db), headers=AUTH) as client:
        client.post(
            "/api/v1/projects", json={"name": "rest", "path": str(project), "scaffold": False}
        )
        asyncio.run(save_standard())
        yield client, project, contexts


def _wait_for(contexts: list[Any]) -> Any:
    for _ in range(100):
        if contexts:
            return contexts[-1]
        time.sleep(0.02)
    raise AssertionError("no run started")


def _park(project: Path, run_id: str) -> None:
    from specweaver.core.config.paths import state_db_path
    from specweaver.core.flow.engine.state import PipelineRun, RunStatus
    from specweaver.core.flow.engine.store import StateStore

    StateStore(state_db_path()).save_run(
        PipelineRun(
            run_id=run_id,
            pipeline_name="one_check",
            project_name="rest",
            spec_path=str(project / "specs" / "orders_spec.md"),
            status=RunStatus.PARKED,
            started_at="2026-10-23T00:00:00",
            updated_at="2026-10-23T00:00:00",
        )
    )


def _start(client: TestClient) -> Any:
    return client.post(
        "/api/v1/pipelines/one_check/run", json={"project": "rest", "spec": "specs/orders_spec.md"}
    )


def _resume(client: TestClient, project: Path) -> Any:
    _park(project, "r-resume")
    return client.post("/api/v1/runs/r-resume/resume")


def _gate(client: TestClient, project: Path) -> Any:
    _park(project, "r-gate")
    return client.post("/api/v1/runs/r-gate/gate", json={"action": "approve"})


@pytest.mark.parametrize(
    "door",
    [lambda c, p: _start(c), _resume, _gate],
    ids=["run", "resume", "gate"],
)
def test_every_api_door_gets_every_part(door, world) -> None:
    client, project, contexts = world

    answer = door(client, project)
    context = _wait_for(contexts)

    assert answer.status_code == 200, answer.text
    assert "Api rule." in (context.guidance.constitution or "")
    assert "api_case" in (context.guidance.standards or "")
    assert [rule.access for rule in context.isolation.doc_policy.rule] == ["open"]
    assert context.isolation.enforce_isolation is True
    assert context.isolation.session_isolation is True


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ('[[docs.rule]]\npaths = ["docs/**"]\naccess = "wide"\n', "DOC_POLICY"),
        ('[autonomy]\nmode = "sideways"\n', "AUTONOMY_POLICY"),
        ('[sandbox]\nexecution_mod = "container"\n', "SANDBOX_SETTINGS"),
        ('[standards]\nmod = "x"\n', "STANDARDS_SETTINGS"),
    ],
    ids=["docs", "autonomy", "sandbox", "standards"],
)
def test_a_broken_section_answers_with_its_code(text: str, code: str, world) -> None:
    client, project, contexts = world
    (project / "specweaver.toml").write_text(text, encoding="utf-8")

    answer = _start(client)

    assert answer.status_code == 500, answer.text
    assert answer.json()["error_code"] == code
    assert contexts == []


def test_a_run_whose_worktree_cannot_start_is_recorded_failed(world, monkeypatch) -> None:
    client, project, _contexts = world
    monkeypatch.setattr(PipelineRunner, "run", _REAL_RUN)
    (project / ".git").rmdir()

    run_id = _start(client).json()["run_id"]
    status = {}
    for _ in range(200):
        status = client.get(f"/api/v1/runs/{run_id}").json()
        if status.get("status") not in (None, "not_started", "running"):
            break
        time.sleep(0.02)

    assert status.get("status") == "failed", status
    assert "could not start" in str(client.get(f"/api/v1/runs/{run_id}?detail=full").json())
