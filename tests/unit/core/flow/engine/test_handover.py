# mypy: ignore-errors
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from specweaver.core.flow.engine.handover import save_handover_context
from specweaver.core.flow.engine.state import PipelineRun, RunStatus, StepResult, StepStatus
from specweaver.core.flow.handlers.base import RunContext

if TYPE_CHECKING:
    from specweaver.workspace.memory.models import HandoverContext


@pytest.fixture
def mock_db():
    db = MagicMock()
    session = AsyncMock()
    # Mock async context manager for db.async_session_scope()
    db.async_session_scope.return_value.__aenter__.return_value = session
    return db, session


@pytest.fixture
def mock_repo(monkeypatch):
    repo = AsyncMock()
    monkeypatch.setattr(
        "specweaver.core.flow.engine.handover.MemoryRepository", MagicMock(return_value=repo)
    )
    return repo


@pytest.fixture
def run_context(mock_db):
    db, _ = mock_db
    return RunContext(
        project_path=Path("."),
        spec_path=Path("."),
        db=db,
        task_id=None,
    )


def create_pipeline_run(status: RunStatus, steps: int = 1) -> PipelineRun:
    run = PipelineRun(
        run_id=str(uuid.uuid4()),
        pipeline_name="test_pipeline",
        project_name="test_project",
        spec_path="test_spec",
        started_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
        status=status,
    )
    for i in range(steps):
        from specweaver.core.flow.engine.state import StepRecord

        run.step_records.append(
            StepRecord(
                step_name=f"step_{i}",
                status=status
                if status in (StepStatus.PASSED, StepStatus.FAILED, StepStatus.ERROR)
                else StepStatus.PASSED,
                result=StepResult(
                    status=StepStatus.PASSED,
                    started_at=datetime.now(UTC).isoformat(),
                    completed_at=datetime.now(UTC).isoformat(),
                    output={"files_touched": [f"file_{i}.py"]},
                ),
            )
        )
    return run


@pytest.mark.asyncio
async def test_handover_success_with_task_id(run_context, mock_repo):
    """Happy Path: Uses explicitly provided task_id."""
    run_context.task_id = str(uuid.uuid4())
    run = create_pipeline_run(RunStatus.COMPLETED, steps=3)

    await save_handover_context(run_context, run)

    mock_repo.list_tasks.assert_not_called()
    mock_repo.update_handover_context.assert_called_once()

    call_args = mock_repo.update_handover_context.call_args[0]
    assert call_args[0] == uuid.UUID(run_context.task_id)
    ctx: HandoverContext = call_args[1]
    assert ctx.summary == "Pipeline 'test_pipeline' completed. 3 steps executed."
    assert "file_0.py" in ctx.files_touched


@pytest.mark.asyncio
async def test_handover_success_with_list_tasks_fallback(run_context, mock_repo):
    """Graceful Degradation: Falls back to list_tasks if task_id is missing."""
    task_id = str(uuid.uuid4())
    mock_repo.list_tasks.return_value = [{"id": task_id}]
    run = create_pipeline_run(RunStatus.COMPLETED)

    await save_handover_context(run_context, run)

    mock_repo.list_tasks.assert_called_once()
    mock_repo.update_handover_context.assert_called_once()
    assert mock_repo.update_handover_context.call_args[0][0] == uuid.UUID(task_id)


@pytest.mark.asyncio
async def test_skips_parked_and_not_started(run_context, mock_repo):
    """Boundary Case: Status guard properly skips specific statuses."""
    for status in [RunStatus.PARKED, RunStatus.NOT_STARTED]:
        run = create_pipeline_run(status)
        await save_handover_context(run_context, run)
        mock_repo.update_handover_context.assert_not_called()


@pytest.mark.asyncio
async def test_saves_running_on_interrupt(run_context, mock_repo):
    """Happy Path: Saves RUNNING status (simulating KeyboardInterrupt)."""
    run_context.task_id = str(uuid.uuid4())
    run = create_pipeline_run(RunStatus.RUNNING)
    await save_handover_context(run_context, run)
    mock_repo.update_handover_context.assert_called_once()


@pytest.mark.asyncio
async def test_skips_empty_pipeline(run_context, mock_repo):
    """Boundary Case: RT-15 guard against 0-step pipelines."""
    run_context.task_id = str(uuid.uuid4())
    run = create_pipeline_run(RunStatus.COMPLETED, steps=0)
    await save_handover_context(run_context, run)
    mock_repo.update_handover_context.assert_not_called()


@pytest.mark.asyncio
async def test_error_deduplication(run_context, mock_repo):
    """Happy Path: Deduplicates identical errors."""
    run_context.task_id = str(uuid.uuid4())
    run = create_pipeline_run(RunStatus.FAILED, steps=0)
    # Add identical errors
    for _ in range(3):
        from specweaver.core.flow.engine.state import StepRecord

        run.step_records.append(
            StepRecord(
                step_name="err_step",
                result=StepResult(
                    status=StepStatus.ERROR,
                    error_message="Duplicate Error",
                    started_at=datetime.now(UTC).isoformat(),
                    completed_at=datetime.now(UTC).isoformat(),
                ),
            )
        )

    await save_handover_context(run_context, run)
    ctx: HandoverContext = mock_repo.update_handover_context.call_args[0][1]
    assert ctx.errors_encountered == ["Duplicate Error"]


@pytest.mark.asyncio
async def test_error_truncation_and_capping(run_context, mock_repo):
    """Boundary Case: RT-23 string truncation and RT-14 capping."""
    run_context.task_id = str(uuid.uuid4())
    run = create_pipeline_run(RunStatus.FAILED, steps=0)

    # Add 15 unique errors, each 600 chars long
    long_msg = "A" * 600
    for i in range(15):
        from specweaver.core.flow.engine.state import StepRecord

        run.step_records.append(
            StepRecord(
                step_name=f"step_{i}",
                result=StepResult(
                    status=StepStatus.ERROR,
                    error_message=f"{long_msg}{i}",
                    started_at=datetime.now(UTC).isoformat(),
                    completed_at=datetime.now(UTC).isoformat(),
                ),
            )
        )

    await save_handover_context(run_context, run)
    ctx: HandoverContext = mock_repo.update_handover_context.call_args[0][1]

    assert len(ctx.errors_encountered) == 10  # Capped at 10
    assert len(ctx.errors_encountered[0]) == 500  # Truncated to 500


@pytest.mark.asyncio
async def test_files_touched_type_safety(run_context, mock_repo):
    """Hostile Input: RT-19 output is not a dictionary."""
    run_context.task_id = str(uuid.uuid4())
    run = create_pipeline_run(RunStatus.COMPLETED, steps=0)

    # output is a string (bypassing pydantic for hostile input)
    from specweaver.core.flow.engine.state import StepRecord

    run.step_records.append(
        StepRecord(
            step_name="s1",
            result=StepResult.model_construct(
                status=StepStatus.PASSED,
                output="I am a string",
                started_at=datetime.now(UTC).isoformat(),
                completed_at=datetime.now(UTC).isoformat(),
            ),
        )
    )
    # output is None
    run.step_records.append(
        StepRecord(
            step_name="s2",
            result=StepResult.model_construct(
                status=StepStatus.PASSED,
                output=None,
                started_at=datetime.now(UTC).isoformat(),
                completed_at=datetime.now(UTC).isoformat(),
            ),
        )
    )

    # Should not crash
    await save_handover_context(run_context, run)
    ctx: HandoverContext = mock_repo.update_handover_context.call_args[0][1]
    assert ctx.files_touched == []


@pytest.mark.asyncio
async def test_files_deduplication_and_truncation(run_context, mock_repo):
    """Boundary Case: RT-20 deduplication, RT-23 truncation."""
    run_context.task_id = str(uuid.uuid4())
    run = create_pipeline_run(RunStatus.COMPLETED, steps=0)

    long_file = "B" * 200
    from specweaver.core.flow.engine.state import StepRecord

    run.step_records.append(
        StepRecord(
            step_name="s1",
            result=StepResult(
                status=StepStatus.PASSED,
                output={"files_touched": [long_file, long_file, "normal_file.py"]},
                started_at=datetime.now(UTC).isoformat(),
                completed_at=datetime.now(UTC).isoformat(),
            ),
        )
    )

    await save_handover_context(run_context, run)
    ctx: HandoverContext = mock_repo.update_handover_context.call_args[0][1]

    assert len(ctx.files_touched) == 2
    assert len(ctx.files_touched[0]) == 150  # Truncated
    assert ctx.files_touched[1] == "normal_file.py"


@pytest.mark.asyncio
async def test_graceful_degradation_on_exception(run_context, mock_repo):
    """Graceful Degradation: Handles general exceptions cleanly."""
    run_context.task_id = str(uuid.uuid4())
    run = create_pipeline_run(RunStatus.COMPLETED)

    mock_repo.update_handover_context.side_effect = Exception("DB Connection Lost")

    # Should not raise
    await save_handover_context(run_context, run)


@pytest.mark.asyncio
async def test_saves_on_failed_run(run_context, mock_repo):
    run_context.task_id = str(uuid.uuid4())
    run = create_pipeline_run(RunStatus.FAILED)
    await save_handover_context(run_context, run)
    mock_repo.update_handover_context.assert_called_once()


@pytest.mark.asyncio
async def test_skips_sub_pipeline(run_context, mock_repo):
    """Boundary Case: Skips if parent_run_id is set."""
    run_context.task_id = str(uuid.uuid4())
    run = create_pipeline_run(RunStatus.COMPLETED)
    run.parent_run_id = str(uuid.uuid4())
    await save_handover_context(run_context, run)
    mock_repo.update_handover_context.assert_not_called()


@pytest.mark.asyncio
async def test_skips_when_no_db(run_context, mock_repo):
    run_context.db = None
    run = create_pipeline_run(RunStatus.COMPLETED)
    await save_handover_context(run_context, run)
    mock_repo.update_handover_context.assert_not_called()


@pytest.mark.asyncio
async def test_skips_when_no_active_task(run_context, mock_repo):
    run_context.task_id = None
    mock_repo.list_tasks.return_value = []
    run = create_pipeline_run(RunStatus.COMPLETED)
    await save_handover_context(run_context, run)
    mock_repo.update_handover_context.assert_not_called()


@pytest.mark.asyncio
async def test_errors_order_preserved(run_context, mock_repo):
    run_context.task_id = str(uuid.uuid4())
    run = create_pipeline_run(RunStatus.FAILED, steps=0)
    from specweaver.core.flow.engine.state import StepRecord

    for msg in ["Error A", "Error B", "Error A", "Error C"]:
        run.step_records.append(
            StepRecord(
                step_name="err",
                result=StepResult(
                    status=StepStatus.ERROR,
                    error_message=msg,
                    started_at=datetime.now(UTC).isoformat(),
                    completed_at=datetime.now(UTC).isoformat(),
                ),
            )
        )
    await save_handover_context(run_context, run)
    ctx: HandoverContext = mock_repo.update_handover_context.call_args[0][1]
    assert ctx.errors_encountered == ["Error A", "Error B", "Error C"]


@pytest.mark.asyncio
async def test_files_touched_capped_at_30(run_context, mock_repo):
    run_context.task_id = str(uuid.uuid4())
    run = create_pipeline_run(RunStatus.COMPLETED, steps=0)
    files = [f"file_{i}.py" for i in range(50)]
    from specweaver.core.flow.engine.state import StepRecord

    run.step_records.append(
        StepRecord(
            step_name="files",
            result=StepResult(
                status=StepStatus.PASSED,
                output={"files_touched": files},
                started_at=datetime.now(UTC).isoformat(),
                completed_at=datetime.now(UTC).isoformat(),
            ),
        )
    )
    await save_handover_context(run_context, run)
    ctx: HandoverContext = mock_repo.update_handover_context.call_args[0][1]
    assert len(ctx.files_touched) == 30


@pytest.mark.asyncio
async def test_metadata_contains_run_id(run_context, mock_repo):
    run_context.task_id = str(uuid.uuid4())
    run = create_pipeline_run(RunStatus.COMPLETED)
    await save_handover_context(run_context, run)
    ctx: HandoverContext = mock_repo.update_handover_context.call_args[0][1]
    assert ctx.metadata["run_id"] == run.run_id


@pytest.mark.asyncio
async def test_handover_passes_pydantic_validation(run_context, mock_repo):
    run_context.task_id = str(uuid.uuid4())
    run = create_pipeline_run(RunStatus.COMPLETED)
    await save_handover_context(run_context, run)
    ctx: HandoverContext = mock_repo.update_handover_context.call_args[0][1]
    assert ctx.model_dump_json() is not None


@pytest.mark.asyncio
async def test_handover_under_8kb(run_context, mock_repo):
    run_context.task_id = str(uuid.uuid4())
    run = create_pipeline_run(RunStatus.FAILED, steps=0)
    long_msg = "A" * 600
    from specweaver.core.flow.engine.state import StepRecord

    for i in range(15):
        run.step_records.append(
            StepRecord(
                step_name=f"err_{i}",
                result=StepResult(
                    status=StepStatus.ERROR,
                    error_message=f"{long_msg}{i}",
                    started_at=datetime.now(UTC).isoformat(),
                    completed_at=datetime.now(UTC).isoformat(),
                ),
            )
        )
    files = ["B" * 200 for _ in range(50)]
    run.step_records.append(
        StepRecord(
            step_name="files",
            result=StepResult(
                status=StepStatus.PASSED,
                output={"files_touched": files},
                started_at=datetime.now(UTC).isoformat(),
                completed_at=datetime.now(UTC).isoformat(),
            ),
        )
    )

    await save_handover_context(run_context, run)
    ctx: HandoverContext = mock_repo.update_handover_context.call_args[0][1]
    json_str = ctx.model_dump_json()
    assert len(json_str.encode("utf-8")) < 8192


@pytest.mark.asyncio
async def test_summary_format(run_context, mock_repo):
    run_context.task_id = str(uuid.uuid4())
    run = create_pipeline_run(RunStatus.COMPLETED, steps=5)
    await save_handover_context(run_context, run)
    ctx: HandoverContext = mock_repo.update_handover_context.call_args[0][1]
    assert "test_pipeline" in ctx.summary
    assert "completed" in ctx.summary
    assert "5 steps" in ctx.summary
