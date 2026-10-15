# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Scenario files live in SpecWeaver's own store per registered project, never in the project.

Proves: B-FLOW-01 FR-11
Proves: B-FLOW-01 FR-18

A real database, the real registration and the real dual handler; its runners are recorded.

| Bucket | Case |
|---|---|
| Happy | a registered project's store is `<data>/projects/<name>/scenarios` |
| Boundary | removing the project removes its store |
| Degradation | an unregistered project has no store, and its dual run refuses |
| Hostile | old `scenarios/generated` in the project, or a non-Python project: the dual run refuses |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import RunStatus, StepStatus
from specweaver.core.flow.handlers.dual_pipeline import ArbitrateDualPipelineHandler
from specweaver.core.flow.handlers.run_context import RunContext, RunHandle
from specweaver.core.flow.handlers.scenario import scenario_store
from tests.fixtures.db_utils import register_test_project, remove_test_project

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    monkeypatch.setattr(
        ArbitrateDualPipelineHandler, "container_available", staticmethod(lambda root: True)
    )
    return data


@pytest.fixture
def db(data_dir: Path) -> Database:
    bootstrap_database(str(data_dir / "specweaver.db"))
    return Database(data_dir / "specweaver.db")


def _context(root: Path, db: Database) -> RunContext:
    root.mkdir(parents=True, exist_ok=True)
    return RunContext(project_path=root, spec_path=root / "specs" / "greet_spec.md", db=db)


def test_a_registered_project_has_its_store_outside_it(
    tmp_path: Path, data_dir: Path, db: Database
) -> None:
    root = tmp_path / "work" / "folder"
    context = _context(root, db)
    register_test_project(db, "greeter", str(root))

    store = scenario_store(context)

    assert store == data_dir / "projects" / "greeter" / "scenarios"
    assert not store.is_relative_to(root)


def test_removing_a_project_removes_its_store(tmp_path: Path, data_dir: Path, db: Database) -> None:
    root = tmp_path / "folder"
    context = _context(root, db)
    register_test_project(db, "greeter", str(root))
    store = scenario_store(context)
    assert store is not None
    (store / "generated").mkdir(parents=True)
    (store / "generated" / "test_greet_scenarios.py").write_text("x = 1\n")

    remove_test_project(db, "greeter")

    assert not store.exists()


class _Spawner:
    def __init__(self) -> None:
        self.spawned = 0

    def spawn(
        self, pipeline: Any, feedback: dict[str, Any] | None = None, side: str | None = None
    ) -> Any:
        self.spawned += 1

        class _Done:
            async def run(self, parent_run_id: str | None = None) -> Any:
                class _Run:
                    status = RunStatus.COMPLETED

                return _Run()

        return _Done()


async def _dual(context: RunContext) -> tuple[Any, _Spawner]:
    spawner = _Spawner()
    context.run = RunHandle(run_id="r", pipeline_runner=spawner)
    step = PipelineStep(
        name="run_dual_pipelines", action=StepAction.ORCHESTRATE, target=StepTarget.COMPONENTS
    )
    return await ArbitrateDualPipelineHandler().execute(step, context), spawner


@pytest.mark.asyncio
async def test_an_unregistered_project_refuses(tmp_path: Path, db: Database) -> None:
    result, spawner = await _dual(_context(tmp_path / "loose", db))

    assert result.status == StepStatus.FAILED
    assert "registered" in (result.error_message or "")
    assert spawner.spawned == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("make", "says"),
    [
        (lambda root: (root / "scenarios" / "generated").mkdir(parents=True), "scenarios/"),
        (lambda root: (root / "Cargo.toml").write_text('[package]\nname = "a"\n'), "Python"),
    ],
    ids=["old-scenarios-in-project", "rust-project"],
)
async def test_a_dual_run_refuses_where_isolation_cannot_hold(
    tmp_path: Path, db: Database, make: Any, says: str
) -> None:
    root = tmp_path / "folder"
    context = _context(root, db)
    register_test_project(db, "greeter", str(root))
    make(root)

    result, spawner = await _dual(context)

    assert result.status == StepStatus.FAILED
    assert says in (result.error_message or "")
    assert spawner.spawned == 0
