# mypy: ignore-errors
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from specweaver.core.config.database import Database
from specweaver.core.flow.engine.handover import save_handover_context
from specweaver.core.flow.engine.state import PipelineRun, RunStatus, StepResult, StepStatus
from specweaver.core.flow.handlers.base import RunContext
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
    ctx = RunContext(project_path=Path("."), spec_path=Path("."), db=db, task_id=str(task_id))

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

    ctx = RunContext(project_path=Path("."), spec_path=Path("."), db=db, task_id=str(task_id))
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

    ctx = RunContext(project_path=Path("."), spec_path=Path("."), db=db, task_id=str(uuid.uuid4()))
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
