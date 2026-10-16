# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the runner does with telemetry at the end of a run (Feature 3.12, C-FLOW-01 FR-4).

The collector writes every call to the cost ledger itself, as the call happens. At the end of
run() and resume() the runner records only how its steps ended, and never touches the collector.

Proves: TECH-051 FR-4

**This file collected ZERO tests until 2026-08-16.** Its six tests for the runner's telemetry flush were
hidden behind a class without the `Test` prefix, so pytest never saw them. Renamed by `TECH-051`
CB-1; `scripts/check_test_collection.py` now fails the gate if it happens again.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from specweaver.core.flow.engine.models import (
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext
from tests.scripted_llm import FixedRouter

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


@pytest.fixture(autouse=True)
def outcomes(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The run ids whose step outcomes the runner recorded."""
    seen: list[str] = []
    monkeypatch.setattr(
        "specweaver.core.flow.engine.telemetry.record_step_outcomes",
        lambda db, run_id, steps: seen.append(run_id),
    )
    return seen


class TestQARunnerTelemetryFlush:
    """At its end a run records its step outcomes; the calls are already in the ledger."""

    @pytest.mark.asyncio
    async def test_a_finished_run_records_its_step_outcomes(
        self, tmp_path: Path, outcomes: list[str]
    ):
        """After a successful run, its step outcomes are recorded once."""
        from specweaver.infrastructure.llm.collector import TelemetryCollector

        mock_collector = MagicMock(spec=TelemetryCollector)
        mock_db = MagicMock()
        ctx = RunContext(
            model=ModelAccess(llm_router=FixedRouter(mock_collector)),
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
            db=mock_db,
        )
        runner = PipelineRunner(_pipeline(1), ctx, registry=_registry(PassHandler()))

        await runner.run()

        assert len(outcomes) == 1
        assert mock_collector.method_calls == []  # the collector wrote its own rows

    @pytest.mark.asyncio
    async def test_a_failed_run_records_its_step_outcomes(
        self, tmp_path: Path, outcomes: list[str]
    ):
        """After a failed run, its step outcomes are still recorded."""
        from specweaver.infrastructure.llm.collector import TelemetryCollector

        mock_collector = MagicMock(spec=TelemetryCollector)
        mock_db = MagicMock()
        ctx = RunContext(
            model=ModelAccess(llm_router=FixedRouter(mock_collector)),
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
            db=mock_db,
        )
        runner = PipelineRunner(_pipeline(1), ctx, registry=_registry(FailHandler()))

        await runner.run()

        assert len(outcomes) == 1
        assert mock_collector.method_calls == []  # the collector wrote its own rows

    @pytest.mark.asyncio
    async def test_no_flush_when_llm_is_not_collector(self, tmp_path: Path, outcomes: list[str]):
        """When context.model.llm is a plain adapter (not TelemetryCollector), no crash."""
        mock_adapter = MagicMock()  # no spec=TelemetryCollector
        ctx = RunContext(
            model=ModelAccess(llm_router=FixedRouter(mock_adapter)),
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
        )
        runner = PipelineRunner(_pipeline(1), ctx, registry=_registry(PassHandler()))

        await runner.run()

        # Should not crash — no assertion needed, test passes if no exception

    @pytest.mark.asyncio
    async def test_nothing_is_recorded_without_a_database(
        self, tmp_path: Path, outcomes: list[str]
    ):
        """When context.db is None, nothing is recorded."""
        from specweaver.infrastructure.llm.collector import TelemetryCollector

        mock_collector = MagicMock(spec=TelemetryCollector)
        ctx = RunContext(
            model=ModelAccess(llm_router=FixedRouter(mock_collector)),
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
            # db=None — omitted
        )
        runner = PipelineRunner(_pipeline(1), ctx, registry=_registry(PassHandler()))

        await runner.run()

        assert outcomes == []  # no database, nothing to record
        assert mock_collector.method_calls == []

    @pytest.mark.asyncio
    async def test_flush_called_when_context_llm_is_none(self, tmp_path: Path, outcomes: list[str]):
        """When context.model.llm is None, _flush_telemetry does nothing (no crash)."""
        ctx = RunContext(
            model=ModelAccess(llm_router=None),
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
        )
        runner = PipelineRunner(_pipeline(1), ctx, registry=_registry(PassHandler()))

        await runner.run()

        # No crash = success

    @pytest.mark.asyncio
    async def test_a_resumed_run_records_its_step_outcomes(
        self, tmp_path: Path, outcomes: list[str]
    ):
        """After resume(), the step outcomes are recorded."""
        from specweaver.core.flow.engine.state import PipelineRun, RunStatus, StepRecord
        from specweaver.infrastructure.llm.collector import TelemetryCollector

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
            model=ModelAccess(llm_router=FixedRouter(mock_collector)),
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
            db=mock_db,
        )
        runner = PipelineRunner(
            _pipeline(1),
            ctx,
            store=mock_store,
            registry=_registry(PassHandler()),
        )

        await runner.resume("test-resume-id")

        assert len(outcomes) == 1
        assert mock_collector.method_calls == []  # the collector wrote its own rows
