# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for runner telemetry flush (Feature 3.12).

Verifies that PipelineRunner flushes the TelemetryCollector
(if present on context.llm) after run() and resume() complete.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from specweaver.flow.handlers import RunContext, StepHandlerRegistry
from specweaver.flow.models import PipelineDefinition, PipelineStep, StepAction, StepTarget
from specweaver.flow.runner import PipelineRunner
from specweaver.flow.state import StepResult, StepStatus

if TYPE_CHECKING:
    from pathlib import Path


class PassHandler:
    """Always passes."""

    async def execute(self, step, context) -> StepResult:
        return StepResult(
            status=StepStatus.PASSED,
            output={"mock": True},
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:01Z",
        )


class FailHandler:
    """Always fails."""

    async def execute(self, step, context) -> StepResult:
        return StepResult(
            status=StepStatus.FAILED,
            error_message="Mock failure",
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:01Z",
        )


def _pipeline(n: int = 1) -> PipelineDefinition:
    steps = [
        PipelineStep(name=f"s{i}", action=StepAction.VALIDATE, target=StepTarget.SPEC)
        for i in range(n)
    ]
    return PipelineDefinition(name="test", steps=steps)


def _registry(handler) -> StepHandlerRegistry:
    reg = StepHandlerRegistry()
    reg.register(StepAction.VALIDATE, StepTarget.SPEC, handler)
    return reg


class TestRunnerTelemetryFlush:
    """Runner flushes TelemetryCollector after pipeline completes."""

    @pytest.mark.asyncio
    async def test_flush_called_on_successful_run(self, tmp_path: Path):
        """After a successful pipeline run, flush() is called on context.llm."""
        from specweaver.llm.collector import TelemetryCollector

        mock_collector = MagicMock(spec=TelemetryCollector)
        mock_db = MagicMock()
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
            llm=mock_collector,
            db=mock_db,
        )
        runner = PipelineRunner(_pipeline(1), ctx, registry=_registry(PassHandler()))

        await runner.run()

        mock_collector.flush.assert_called_once_with(mock_db)

    @pytest.mark.asyncio
    async def test_flush_called_on_failed_run(self, tmp_path: Path):
        """After a failed pipeline run, flush() is still called."""
        from specweaver.llm.collector import TelemetryCollector

        mock_collector = MagicMock(spec=TelemetryCollector)
        mock_db = MagicMock()
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
            llm=mock_collector,
            db=mock_db,
        )
        runner = PipelineRunner(_pipeline(1), ctx, registry=_registry(FailHandler()))

        await runner.run()

        mock_collector.flush.assert_called_once_with(mock_db)

    @pytest.mark.asyncio
    async def test_no_flush_when_llm_is_not_collector(self, tmp_path: Path):
        """When context.llm is a plain adapter (not TelemetryCollector), no crash."""
        mock_adapter = MagicMock()  # no spec=TelemetryCollector
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
            llm=mock_adapter,
        )
        runner = PipelineRunner(_pipeline(1), ctx, registry=_registry(PassHandler()))

        await runner.run()

        # Should not crash — no assertion needed, test passes if no exception

    @pytest.mark.asyncio
    async def test_flush_skipped_when_db_is_none(self, tmp_path: Path):
        """When context.db is None, flush is skipped (not called)."""
        from specweaver.llm.collector import TelemetryCollector

        mock_collector = MagicMock(spec=TelemetryCollector)
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
            llm=mock_collector,
            # db=None — omitted
        )
        runner = PipelineRunner(_pipeline(1), ctx, registry=_registry(PassHandler()))

        await runner.run()

        mock_collector.flush.assert_not_called()

    @pytest.mark.asyncio
    async def test_flush_called_when_context_llm_is_none(self, tmp_path: Path):
        """When context.llm is None, _flush_telemetry does nothing (no crash)."""
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
            llm=None,
        )
        runner = PipelineRunner(_pipeline(1), ctx, registry=_registry(PassHandler()))

        await runner.run()

        # No crash = success

    @pytest.mark.asyncio
    async def test_resume_flushes_telemetry(self, tmp_path: Path):
        """After resume(), flush() is called on context.llm."""
        from specweaver.flow.state import PipelineRun, RunStatus, StepRecord
        from specweaver.llm.collector import TelemetryCollector

        mock_collector = MagicMock(spec=TelemetryCollector)
        mock_db = MagicMock()
        mock_store = MagicMock()

        # Create a parked run with one step
        PipelineStep(
            name="s0",
            action=StepAction.VALIDATE,
            target=StepTarget.SPEC,
        )
        run = PipelineRun(
            run_id="test-resume-id",
            pipeline_name="test",
            project_name="testproj",
            spec_path=str(tmp_path / "spec.md"),
            status=RunStatus.PARKED,
            current_step=0,
            step_records=[StepRecord(step_name="s0")],
            started_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        mock_store.load_run.return_value = run

        ctx = RunContext(
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
            llm=mock_collector,
            db=mock_db,
        )
        runner = PipelineRunner(
            _pipeline(1),
            ctx,
            store=mock_store,
            registry=_registry(PassHandler()),
        )

        await runner.resume("test-resume-id")

        mock_collector.flush.assert_called_once_with(mock_db)
