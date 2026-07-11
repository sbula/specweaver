# mypy: ignore-errors
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus


class MockPath:
    name = "test_project"

    def resolve(self):
        return self

    def __str__(self):
        return "test_project"

    @property
    def parent(self):
        return self

    def exists(self):
        return True

    def __truediv__(self, other):
        return self


class MockContext:
    project_path = MockPath()
    spec_path = MockPath()
    db = MagicMock()
    dal_level = "DAL_A"


class MockPipeline:
    def __init__(self):
        self.name = "test_pipeline"
        self.steps: list = []


@pytest.fixture
def runner():
    context = MockContext()
    pipeline = MockPipeline()
    run = MagicMock()
    run.pipeline_name = "test_pipeline"
    run.project_name = "test_project"
    run.status = RunStatus.NOT_STARTED
    run.step_records = []

    r = PipelineRunner(pipeline, context)
    r._run = run
    r._store = MagicMock()
    r._store.load_run.return_value = run
    # Mock internal methods that are not relevant to handover
    r._execute_loop = AsyncMock()
    r._flush_telemetry = AsyncMock()
    r._save_handover = AsyncMock()
    r._persist = MagicMock()
    return r


@pytest.mark.asyncio
async def test_runner_run_calls_save_handover(runner):
    """Happy Path: Runner run() calls save_handover in finally block."""
    runner._run.status = RunStatus.COMPLETED

    await runner.run()
    runner._save_handover.assert_called_once_with(ANY)
    runner._flush_telemetry.assert_called_once()


@pytest.mark.asyncio
async def test_handover_called_on_run_failed(runner):
    runner._run.status = RunStatus.FAILED
    await runner.run()
    runner._save_handover.assert_called_once_with(ANY)


@pytest.mark.asyncio
async def test_handover_called_on_park(runner):
    runner._run.status = RunStatus.PARKED
    await runner.run()
    runner._save_handover.assert_called_once_with(ANY)


@pytest.mark.asyncio
@patch("specweaver.core.flow.engine.handover.save_handover_context", new_callable=AsyncMock)
async def test_handover_exception_does_not_crash_runner(mock_save, runner):
    runner._run.status = RunStatus.COMPLETED
    # Unmock the method to test the internal try/except
    runner._save_handover = PipelineRunner._save_handover.__get__(runner)
    mock_save.side_effect = Exception("Crash")
    await runner.run()  # Should not raise exception
    mock_save.assert_called_once()


@pytest.mark.asyncio
async def test_handover_called_on_empty_pipeline(runner):
    runner._pipeline.steps = []
    runner._run.status = RunStatus.COMPLETED
    await runner.run()
    runner._save_handover.assert_called_once_with(ANY)


@pytest.mark.asyncio
async def test_runner_run_calls_save_handover_on_interrupt(runner):
    """Happy Path: Runner run() calls save_handover on KeyboardInterrupt."""
    runner._execute_loop.side_effect = KeyboardInterrupt()
    runner._run.status = RunStatus.RUNNING

    with pytest.raises(KeyboardInterrupt):
        await runner.run()

    runner._save_handover.assert_called_once_with(ANY)


@pytest.mark.asyncio
async def test_runner_resume_calls_save_handover(runner):
    """Happy Path: Runner resume() calls save_handover in finally block."""
    runner._run.status = RunStatus.PARKED

    await runner.resume("test_run_id")

    runner._save_handover.assert_called_once_with(runner._run)
