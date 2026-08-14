# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine

from specweaver.core.config.database import Database
from specweaver.core.flow.engine.handover import save_handover_context
from specweaver.core.flow.engine.models import (
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import PipelineRun, RunStatus, StepResult, StepStatus
from specweaver.core.flow.engine.store import StateStore
from specweaver.core.flow.handlers.base import IsolationPolicy, ModelAccess
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.handlers.run_context import RunContext, RunHandle
from specweaver.workspace.memory.store import Task, TaskStatus
from specweaver.workspace.store import Base


@pytest.mark.asyncio
async def test_handover_persistence_e2e(tmp_path: Path):
    """Happy Path: E2E database write of handover context."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)

    # Create schema synchronously for the test
    sync_engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(sync_engine)

    # Create a dummy project because of foreign key constraint
    with sync_engine.begin() as conn:
        conn.execute(
            Base.metadata.tables["workspace_projects"]
            .insert()
            .values(
                name="integration",
                root_path=".",
                created_at=datetime.now(UTC),
                last_used_at=datetime.now(UTC),
            )
        )
    sync_engine.dispose()

    async with db.async_session_scope() as session:
        # Setup active task in DB
        task_id = uuid.uuid4()
        task = Task(
            id=task_id,
            title="Integration Task",
            project_name="integration",
            status=TaskStatus.IN_PROGRESS,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(task)
        await session.commit()

    # Setup RunContext and Run
    ctx = RunContext(
        project_path=Path("."), spec_path=Path("."), db=db, run=RunHandle(task_id=str(task_id))
    )

    run = PipelineRun(
        run_id=str(uuid.uuid4()),
        pipeline_name="integration",
        project_name="integration",
        spec_path=".",
        started_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
        status=RunStatus.COMPLETED,
    )
    from specweaver.core.flow.engine.state import StepRecord

    run.step_records.append(
        StepRecord(
            step_name="int",
            result=StepResult(
                status=StepStatus.PASSED,
                started_at=datetime.now(UTC).isoformat(),
                completed_at=datetime.now(UTC).isoformat(),
                output={"files_touched": ["int_file.py"]},
            ),
        )
    )

    # Execute Handover
    await save_handover_context(ctx, run)

    # Verify Persistence
    async with db.async_session_scope() as session:
        result = await session.get(Task, task_id)
        assert result is not None
        assert result.handover_context is not None
        # HandoverContext is stored as a JSON string in SQLite
        ctx_dict = json.loads(result.handover_context)
        assert "int_file.py" in ctx_dict["files_touched"]
        assert "Integration" in ctx_dict["summary"] or "integration" in ctx_dict["summary"]


@pytest.mark.asyncio
async def test_handover_persisted_on_failure(tmp_path: Path):
    """Failure Path: E2E database write of handover context with errors."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    sync_engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(sync_engine)
    with sync_engine.begin() as conn:
        conn.execute(
            Base.metadata.tables["workspace_projects"]
            .insert()
            .values(
                name="integration",
                root_path=".",
                created_at=datetime.now(UTC),
                last_used_at=datetime.now(UTC),
            )
        )
    sync_engine.dispose()

    async with db.async_session_scope() as session:
        task_id = uuid.uuid4()
        task = Task(
            id=task_id,
            title="Integration Task",
            project_name="integration",
            status=TaskStatus.IN_PROGRESS,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(task)
        await session.commit()

    ctx = RunContext(
        project_path=Path("."), spec_path=Path("."), db=db, run=RunHandle(task_id=str(task_id))
    )
    run = PipelineRun(
        run_id=str(uuid.uuid4()),
        pipeline_name="integration",
        project_name="integration",
        spec_path=".",
        started_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
        status=RunStatus.FAILED,
    )
    from specweaver.core.flow.engine.state import StepRecord

    run.step_records.append(
        StepRecord(
            step_name="int",
            result=StepResult(
                status=StepStatus.ERROR,
                error_message="Integration Failed",
                started_at=datetime.now(UTC).isoformat(),
                completed_at=datetime.now(UTC).isoformat(),
            ),
        )
    )

    await save_handover_context(ctx, run)

    async with db.async_session_scope() as session:
        result = await session.get(Task, task_id)
        ctx_dict = json.loads(result.handover_context)
        assert "Integration Failed" in ctx_dict["errors_encountered"]


@pytest.mark.asyncio
async def test_handover_noop_when_no_task(tmp_path: Path):
    """Boundary Case: DB exists but no active task, should not crash."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    sync_engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()

    ctx = RunContext(
        project_path=Path("."), spec_path=Path("."), db=db, run=RunHandle(task_id=str(uuid.uuid4()))
    )
    run = PipelineRun(
        run_id=str(uuid.uuid4()),
        pipeline_name="integration",
        project_name="integration",
        spec_path=".",
        started_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
        status=RunStatus.COMPLETED,
    )

    await save_handover_context(ctx, run)
    # If no exception is raised, test passes


def _seed_seam_db(tmp_path: Path, name: str):
    """A real SQLite database with a project and one IN_PROGRESS task. Shared by the seam tests."""
    db = Database(tmp_path / f"{name}.db")
    sync_engine = create_engine(f"sqlite:///{tmp_path / f'{name}.db'}")
    Base.metadata.create_all(sync_engine)
    with sync_engine.begin() as conn:
        conn.execute(
            Base.metadata.tables["workspace_projects"]
            .insert()
            .values(
                name=name,
                root_path=".",
                created_at=datetime.now(UTC),
                last_used_at=datetime.now(UTC),
            )
        )
    sync_engine.dispose()
    return db


async def _seed_task(db, project: str) -> uuid.UUID:
    task_id = uuid.uuid4()
    async with db.async_session_scope() as session:
        session.add(
            Task(
                id=task_id,
                title=f"{project} Task",
                project_name=project,
                status=TaskStatus.IN_PROGRESS,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        await session.commit()
    return task_id


class _TouchesAFile:
    """Minimal real handler — the runner must execute a step for telemetry to exist."""

    async def execute(self, step, context):
        return StepResult(
            status=StepStatus.PASSED,
            started_at=datetime.now(UTC).isoformat(),
            completed_at=datetime.now(UTC).isoformat(),
            output={"files_touched": ["seam_file.py"]},
        )


def _seam_runner_parts(tmp_path: Path, db, task_id: uuid.UUID):
    """A RunContext, a one-step pipeline and a registry wired to the real handler above."""
    ctx = RunContext(
        project_path=tmp_path,
        spec_path=tmp_path / "spec.md",
        db=db,
        run=RunHandle(task_id=str(task_id)),
        model=ModelAccess(config=MagicMock()),
    )
    ctx.isolation = IsolationPolicy(dal_level="DAL_A")
    registry = StepHandlerRegistry()
    registry.register(StepAction.BASH, StepTarget.SCRIPT, _TouchesAFile())
    pipeline = PipelineDefinition(
        name="seam",
        steps=[
            PipelineStep(
                name="touch",
                action=StepAction.BASH,
                target=StepTarget.SCRIPT,
                params={"script": "noop.sh"},
                use_worktree=None,
            )
        ],
    )
    return ctx, pipeline, registry


async def _handover_of(db, task_id: uuid.UUID):
    async with db.async_session_scope() as session:
        task = await session.get(Task, task_id)
        return None if task is None else task.handover_context


@pytest.mark.asyncio
async def test_runner_finally_persists_handover_end_to_end(tmp_path: Path):
    """[Seam] the REAL PipelineRunner.run()'s `finally` reaches the REAL database.

    `INT-US-28` claims *"`save_handover_context()` ... persists pipeline telemetry to the Memory
    Bank in the runner's `finally` block."* Before this test that claim was proven in two halves
    that met at a mock, and so was not proven at all:

    * `tests/unit/core/flow/engine/test_runner_handover.py` drives a real `PipelineRunner` and
      asserts the `finally` calls `_save_handover` — with `_save_handover` replaced by an
      `AsyncMock`, so nothing reaches a database;
    * the tests above call `save_handover_context()` directly against a real database — so the
      runner is never involved.

    Either half can pass while the wiring between them is broken. This drives the runner over a
    real registered step and then reads the row back out of SQLite. `TECH-017` SF-01 CB-2.
    """
    db = _seed_seam_db(tmp_path, "seam")
    task_id = await _seed_task(db, "seam")
    ctx, pipeline, registry = _seam_runner_parts(tmp_path, db, task_id)

    run_state = await PipelineRunner(pipeline, ctx, registry=registry).run()
    assert run_state.status == RunStatus.COMPLETED, run_state

    # No mock anywhere between the runner's `finally` and this row.
    stored = await _handover_of(db, task_id)
    assert stored is not None, "the runner's finally never reached the DB"
    assert "seam_file.py" in json.loads(stored)["files_touched"]


@pytest.mark.asyncio
async def test_runner_resume_finally_persists_handover_end_to_end(tmp_path: Path):
    """[Seam] `resume()` has its OWN `finally`, and it reaches the database too.

    `runner.py` persists handover from two entry points — `run()` at line 176 and `resume()` at
    line 230. The test above covers only the first. Without this one, `resume()`'s span kept the
    exact shape CB-2 was written to catch: `test_runner_resume_calls_save_handover` drives a real
    runner but mocks `_save_handover`, and the direct-call tests never touch a runner at all.

    The handover column is cleared after the initial run, so a passing assertion can only mean the
    RESUMED run wrote it — not that the first one did. `TECH-017` SF-01 CB-2.
    """
    db = _seed_seam_db(tmp_path, "resumeseam")
    task_id = await _seed_task(db, "resumeseam")
    ctx, pipeline, registry = _seam_runner_parts(tmp_path, db, task_id)
    store = StateStore(tmp_path / "runs.db")

    first = await PipelineRunner(pipeline, ctx, registry=registry, store=store).run()
    assert await _handover_of(db, task_id) is not None, "precondition: run() must have written one"

    # Clear it, so anything found afterwards was written by the RESUMED run's finally.
    async with db.async_session_scope() as session:
        task = await session.get(Task, task_id)
        task.handover_context = None
        await session.commit()
    assert await _handover_of(db, task_id) is None

    await PipelineRunner(pipeline, ctx, registry=registry, store=store).resume(first.run_id)

    stored = await _handover_of(db, task_id)
    assert stored is not None, "resume()'s finally never reached the DB"
    assert "seam_file.py" in json.loads(stored)["files_touched"]
