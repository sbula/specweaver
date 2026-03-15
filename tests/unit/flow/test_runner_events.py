# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for the pipeline runner event callback mechanism."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from specweaver.flow.handlers import RunContext, StepHandlerRegistry
from specweaver.flow.models import PipelineDefinition, PipelineStep, StepAction, StepTarget
from specweaver.flow.runner import PipelineRunner
from specweaver.flow.state import RunStatus, StepResult, StepStatus

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Mock handlers
# ---------------------------------------------------------------------------


class PassHandler:
    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        return StepResult(
            status=StepStatus.PASSED,
            output={"mock": True},
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:01Z",
        )


class FailHandler:
    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        return StepResult(
            status=StepStatus.FAILED,
            error_message="Mock failure",
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:01Z",
        )


class ParkHandler:
    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        return StepResult(
            status=StepStatus.WAITING_FOR_INPUT,
            output={"message": "Waiting for human input"},
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:00Z",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pipeline(step_count: int = 2) -> PipelineDefinition:
    steps = [
        PipelineStep(
            name=f"step_{i}",
            action=StepAction.VALIDATE,
            target=StepTarget.SPEC,
        )
        for i in range(step_count)
    ]
    return PipelineDefinition(name="test_pipe", steps=steps)


def _make_registry(handler) -> StepHandlerRegistry:
    registry = StepHandlerRegistry()
    registry.register(StepAction.VALIDATE, StepTarget.SPEC, handler)
    return registry


def _make_context(tmp_path: Path) -> RunContext:
    return RunContext(
        project_path=tmp_path,
        spec_path=tmp_path / "specs" / "test.md",
    )


class EventCollector:
    """Collects runner events for assertions."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def __call__(self, event: str, **kwargs: Any) -> None:
        self.events.append({"event": event, **kwargs})

    @property
    def event_names(self) -> list[str]:
        return [e["event"] for e in self.events]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRunnerEventCallback:
    """Tests for the on_event callback mechanism."""

    @pytest.mark.asyncio
    async def test_successful_run_fires_events_in_order(self, tmp_path: Path) -> None:
        """A successful 2-step run should fire events in the correct order."""
        collector = EventCollector()
        pipeline = _make_pipeline(step_count=2)
        ctx = _make_context(tmp_path)
        registry = _make_registry(PassHandler())
        runner = PipelineRunner(pipeline, ctx, registry=registry, on_event=collector)

        await runner.run()

        expected = [
            "run_started",
            "step_started",
            "step_completed",
            "step_started",
            "step_completed",
            "run_completed",
        ]
        assert collector.event_names == expected

    @pytest.mark.asyncio
    async def test_failed_run_fires_failure_events(self, tmp_path: Path) -> None:
        """A failing run should fire step_failed and run_failed."""
        collector = EventCollector()
        pipeline = _make_pipeline(step_count=1)
        ctx = _make_context(tmp_path)
        registry = _make_registry(FailHandler())
        runner = PipelineRunner(pipeline, ctx, registry=registry, on_event=collector)

        await runner.run()

        assert "step_failed" in collector.event_names
        assert "run_failed" in collector.event_names
        assert "run_completed" not in collector.event_names

    @pytest.mark.asyncio
    async def test_parked_run_fires_parked_events(self, tmp_path: Path) -> None:
        """A parking run should fire step_parked and run_parked."""
        collector = EventCollector()
        pipeline = _make_pipeline(step_count=1)
        ctx = _make_context(tmp_path)
        registry = _make_registry(ParkHandler())
        runner = PipelineRunner(pipeline, ctx, registry=registry, on_event=collector)

        await runner.run()

        assert "step_parked" in collector.event_names
        assert "run_parked" in collector.event_names
        assert "run_completed" not in collector.event_names

    @pytest.mark.asyncio
    async def test_events_include_step_metadata(self, tmp_path: Path) -> None:
        """Events should include step_idx, step_name, total_steps."""
        collector = EventCollector()
        pipeline = _make_pipeline(step_count=1)
        ctx = _make_context(tmp_path)
        registry = _make_registry(PassHandler())
        runner = PipelineRunner(pipeline, ctx, registry=registry, on_event=collector)

        await runner.run()

        started = next(e for e in collector.events if e["event"] == "step_started")
        assert started["step_idx"] == 0
        assert started["step_name"] == "step_0"
        assert started["total_steps"] == 1

    @pytest.mark.asyncio
    async def test_completed_event_includes_result(self, tmp_path: Path) -> None:
        """step_completed events should include the StepResult."""
        collector = EventCollector()
        pipeline = _make_pipeline(step_count=1)
        ctx = _make_context(tmp_path)
        registry = _make_registry(PassHandler())
        runner = PipelineRunner(pipeline, ctx, registry=registry, on_event=collector)

        await runner.run()

        completed = next(e for e in collector.events if e["event"] == "step_completed")
        assert completed["result"].status == StepStatus.PASSED

    @pytest.mark.asyncio
    async def test_run_completed_includes_run(self, tmp_path: Path) -> None:
        """run_completed should include the PipelineRun."""
        collector = EventCollector()
        pipeline = _make_pipeline(step_count=1)
        ctx = _make_context(tmp_path)
        registry = _make_registry(PassHandler())
        runner = PipelineRunner(pipeline, ctx, registry=registry, on_event=collector)

        result = await runner.run()

        completed = next(e for e in collector.events if e["event"] == "run_completed")
        assert completed["run"].run_id == result.run_id

    @pytest.mark.asyncio
    async def test_no_callback_works(self, tmp_path: Path) -> None:
        """Runner without callback should work fine (backwards compat)."""
        pipeline = _make_pipeline(step_count=1)
        ctx = _make_context(tmp_path)
        registry = _make_registry(PassHandler())
        runner = PipelineRunner(pipeline, ctx, registry=registry)  # no on_event

        result = await runner.run()
        assert result.status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_empty_pipeline_fires_run_completed(self, tmp_path: Path) -> None:
        """Empty pipeline should fire run_completed."""
        collector = EventCollector()
        pipeline = PipelineDefinition(name="empty", steps=[])
        ctx = _make_context(tmp_path)
        runner = PipelineRunner(pipeline, ctx, on_event=collector)

        result = await runner.run()
        assert result.status == RunStatus.COMPLETED
        assert "run_completed" in collector.event_names
