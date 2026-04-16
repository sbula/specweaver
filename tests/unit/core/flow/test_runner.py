# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for the pipeline runner — sequential execution, parking, resume."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.handlers import RunContext, StepHandler, StepHandlerRegistry
from specweaver.core.flow.models import PipelineDefinition, PipelineStep, StepAction, StepTarget
from specweaver.core.flow.runner import PipelineRunner
from specweaver.core.flow.state import RunStatus, StepResult, StepStatus
from specweaver.core.flow.store import StateStore

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Mock handlers
# ---------------------------------------------------------------------------


class PassHandler:
    """Always passes."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        return StepResult(
            status=StepStatus.PASSED,
            output={"mock": True},
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:01Z",
        )


class FailHandler:
    """Always fails."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        return StepResult(
            status=StepStatus.FAILED,
            error_message="Mock failure",
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:01Z",
        )


class ParkHandler:
    """Always parks (HITL waiting)."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        return StepResult(
            status=StepStatus.WAITING_FOR_INPUT,
            output={"message": "Waiting for human input"},
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:00Z",
        )


class ErrorHandler:
    """Raises an exception."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        msg = "Something exploded"
        raise RuntimeError(msg)


class ContextInjectionHandler:
    """Passes context attributes back as output."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        return StepResult(
            status=StepStatus.PASSED,
            output={
                "run_id": context.run_id,
                "step_records_len": len(context.step_records) if context.step_records else 0,
            },
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:01Z",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pipeline(step_count: int = 2) -> PipelineDefinition:
    """Create a pipeline with N validate+spec steps."""
    steps = [
        PipelineStep(
            name=f"step_{i}",
            action=StepAction.VALIDATE,
            target=StepTarget.SPEC,
        )
        for i in range(step_count)
    ]
    return PipelineDefinition(name="test_pipe", steps=steps)


def _make_registry(handler: StepHandler) -> StepHandlerRegistry:
    """Create a registry where validate+spec maps to the given handler."""
    registry = StepHandlerRegistry()
    registry.register(StepAction.VALIDATE, StepTarget.SPEC, handler)
    return registry


def _make_context(tmp_path: Path) -> RunContext:
    return RunContext(
        project_path=tmp_path,
        spec_path=tmp_path / "specs" / "test.md",
    )


# ---------------------------------------------------------------------------
# Runner tests
# ---------------------------------------------------------------------------


class TestPipelineRunnerSuccess:
    """Tests for successful pipeline execution."""

    @pytest.mark.asyncio
    async def test_run_all_steps_pass(self, tmp_path: Path) -> None:
        pipeline = _make_pipeline(step_count=3)
        ctx = _make_context(tmp_path)
        registry = _make_registry(PassHandler())
        runner = PipelineRunner(pipeline, ctx, registry=registry)

        result = await runner.run()
        assert result.status == RunStatus.COMPLETED
        assert result.current_step == 3
        assert all(r.status == StepStatus.PASSED for r in result.step_records)

    @pytest.mark.asyncio
    async def test_run_single_step(self, tmp_path: Path) -> None:
        pipeline = _make_pipeline(step_count=1)
        ctx = _make_context(tmp_path)
        registry = _make_registry(PassHandler())
        runner = PipelineRunner(pipeline, ctx, registry=registry)

        result = await runner.run()
        assert result.status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_run_assigns_run_id(self, tmp_path: Path) -> None:
        pipeline = _make_pipeline(step_count=1)
        ctx = _make_context(tmp_path)
        registry = _make_registry(PassHandler())
        runner = PipelineRunner(pipeline, ctx, registry=registry)

        result = await runner.run()
        assert result.run_id  # non-empty UUID

    @pytest.mark.asyncio
    async def test_run_injects_state_into_context(self, tmp_path: Path) -> None:
        pipeline = _make_pipeline(step_count=1)
        ctx = _make_context(tmp_path)
        registry = _make_registry(ContextInjectionHandler())
        runner = PipelineRunner(pipeline, ctx, registry=registry)

        result = await runner.run()
        assert result.status == RunStatus.COMPLETED

        # Verify handler got the injected state
        output = result.step_records[0].result.output
        assert output["run_id"] == result.run_id
        assert output["step_records_len"] == 1

    @pytest.mark.asyncio
    async def test_run_assigns_parent_run_id(self, tmp_path: Path) -> None:
        pipeline = _make_pipeline(step_count=1)
        ctx = _make_context(tmp_path)
        registry = _make_registry(PassHandler())
        runner = PipelineRunner(pipeline, ctx, registry=registry)

        parent_id = "test-parent-id-123"
        result = await runner.run(parent_run_id=parent_id)
        assert result.parent_run_id == parent_id




class TestPipelineRunnerFailure:
    """Tests for failure handling."""

    @pytest.mark.asyncio
    async def test_stops_on_failure(self, tmp_path: Path) -> None:
        pipeline = _make_pipeline(step_count=3)
        ctx = _make_context(tmp_path)
        registry = _make_registry(FailHandler())
        runner = PipelineRunner(pipeline, ctx, registry=registry)

        result = await runner.run()
        assert result.status == RunStatus.FAILED
        assert result.current_step == 0  # stopped at first step
        assert result.step_records[0].status == StepStatus.FAILED
        assert result.step_records[1].status == StepStatus.PENDING

    @pytest.mark.asyncio
    async def test_handler_exception_becomes_error(self, tmp_path: Path) -> None:
        pipeline = _make_pipeline(step_count=1)
        ctx = _make_context(tmp_path)
        registry = _make_registry(ErrorHandler())
        runner = PipelineRunner(pipeline, ctx, registry=registry)

        result = await runner.run()
        assert result.status == RunStatus.FAILED
        assert result.step_records[0].status in (StepStatus.ERROR, StepStatus.FAILED)


class TestPipelineRunnerParking:
    """Tests for HITL parking."""

    @pytest.mark.asyncio
    async def test_parks_at_hitl_step(self, tmp_path: Path) -> None:
        pipeline = _make_pipeline(step_count=2)
        ctx = _make_context(tmp_path)
        registry = _make_registry(ParkHandler())
        runner = PipelineRunner(pipeline, ctx, registry=registry)

        result = await runner.run()
        assert result.status == RunStatus.PARKED
        assert result.current_step == 0
        assert result.step_records[0].status == StepStatus.WAITING_FOR_INPUT

    @pytest.mark.asyncio
    async def test_parking_only_first_step(self, tmp_path: Path) -> None:
        """Parking stops execution — second step stays PENDING."""
        pipeline = _make_pipeline(step_count=2)
        ctx = _make_context(tmp_path)
        registry = _make_registry(ParkHandler())
        runner = PipelineRunner(pipeline, ctx, registry=registry)

        result = await runner.run()
        assert result.step_records[1].status == StepStatus.PENDING


class TestPipelineRunnerPersistence:
    """Tests for state persistence and resume."""

    @pytest.mark.asyncio
    async def test_persists_state(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path / "state.db")
        pipeline = _make_pipeline(step_count=2)
        ctx = _make_context(tmp_path)
        registry = _make_registry(PassHandler())
        runner = PipelineRunner(pipeline, ctx, registry=registry, store=store)

        result = await runner.run()
        loaded = store.load_run(result.run_id)
        assert loaded is not None
        assert loaded.status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_resume_parked_run(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path / "state.db")
        pipeline = _make_pipeline(step_count=2)
        ctx = _make_context(tmp_path)

        # First run: parks at step 0
        park_reg = _make_registry(ParkHandler())
        runner1 = PipelineRunner(pipeline, ctx, registry=park_reg, store=store)
        parked = await runner1.run()
        assert parked.status == RunStatus.PARKED

        # Resume: now passes
        pass_reg = _make_registry(PassHandler())
        runner2 = PipelineRunner(pipeline, ctx, registry=pass_reg, store=store)
        resumed = await runner2.resume(parked.run_id)
        assert resumed.status == RunStatus.COMPLETED
        assert resumed.current_step == 2

    @pytest.mark.asyncio
    async def test_resume_failed_run(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path / "state.db")
        pipeline = _make_pipeline(step_count=2)
        ctx = _make_context(tmp_path)

        # First run: fails at step 0
        fail_reg = _make_registry(FailHandler())
        runner1 = PipelineRunner(pipeline, ctx, registry=fail_reg, store=store)
        failed = await runner1.run()
        assert failed.status == RunStatus.FAILED

        # Resume: now passes
        pass_reg = _make_registry(PassHandler())
        runner2 = PipelineRunner(pipeline, ctx, registry=pass_reg, store=store)
        resumed = await runner2.resume(failed.run_id)
        assert resumed.status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_resume_nonexistent_raises(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path / "state.db")
        pipeline = _make_pipeline()
        ctx = _make_context(tmp_path)
        runner = PipelineRunner(pipeline, ctx, store=store)
        with pytest.raises(ValueError, match="not found"):
            await runner.resume("nonexistent-id")

    @pytest.mark.asyncio
    async def test_audit_log_recorded(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path / "state.db")
        pipeline = _make_pipeline(step_count=1)
        ctx = _make_context(tmp_path)
        registry = _make_registry(PassHandler())
        runner = PipelineRunner(pipeline, ctx, registry=registry, store=store)

        result = await runner.run()
        events = store.get_audit_log(result.run_id)
        # Should have: run_started, step_started, step_completed, run_completed
        assert len(events) >= 3


class TestPipelineRunnerEdgeCases:
    """Edge case tests for the runner."""

    @pytest.mark.asyncio
    async def test_empty_pipeline(self, tmp_path: Path) -> None:
        pipeline = PipelineDefinition(name="empty", steps=[])
        ctx = _make_context(tmp_path)
        runner = PipelineRunner(pipeline, ctx)

        result = await runner.run()
        assert result.status == RunStatus.COMPLETED
        assert result.current_step == 0

    @pytest.mark.asyncio
    async def test_no_handler_for_step(self, tmp_path: Path) -> None:
        """Step with no registered handler → error."""
        steps = [
            PipelineStep(name="s1", action=StepAction.DRAFT, target=StepTarget.SPEC),
        ]
        pipeline = PipelineDefinition(name="no_handler", steps=steps)
        ctx = _make_context(tmp_path)
        # Empty registry
        registry = StepHandlerRegistry.__new__(StepHandlerRegistry)
        registry._handlers = {}

        runner = PipelineRunner(pipeline, ctx, registry=registry)
        result = await runner.run()
        assert result.status == RunStatus.FAILED

    @pytest.mark.asyncio
    async def test_mid_pipeline_failure(self, tmp_path: Path) -> None:
        """First step passes, second step fails — run stops at step 1."""
        steps = [
            PipelineStep(name="s_pass", action=StepAction.VALIDATE, target=StepTarget.SPEC),
            PipelineStep(name="s_fail", action=StepAction.REVIEW, target=StepTarget.SPEC),
        ]
        pipeline = PipelineDefinition(name="mid_fail", steps=steps)
        ctx = _make_context(tmp_path)

        registry = StepHandlerRegistry()
        registry.register(StepAction.VALIDATE, StepTarget.SPEC, PassHandler())
        registry.register(StepAction.REVIEW, StepTarget.SPEC, FailHandler())

        runner = PipelineRunner(pipeline, ctx, registry=registry)
        result = await runner.run()
        assert result.status == RunStatus.FAILED
        assert result.current_step == 1
        assert result.step_records[0].status == StepStatus.PASSED
        assert result.step_records[1].status == StepStatus.FAILED

    @pytest.mark.asyncio
    async def test_resume_without_store_raises(self, tmp_path: Path) -> None:
        """Resuming without a store configured should raise ValueError."""
        pipeline = _make_pipeline()
        ctx = _make_context(tmp_path)
        runner = PipelineRunner(pipeline, ctx)  # no store
        with pytest.raises(ValueError, match="no store"):
            await runner.resume("some-id")

    @pytest.mark.asyncio
    async def test_run_without_store_no_crash(self, tmp_path: Path) -> None:
        """Running without store configured should work fine (no persistence)."""
        pipeline = _make_pipeline(step_count=2)
        ctx = _make_context(tmp_path)
        registry = _make_registry(PassHandler())
        runner = PipelineRunner(pipeline, ctx, registry=registry)  # no store

        result = await runner.run()
        assert result.status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_parked_run_audit_events(self, tmp_path: Path) -> None:
        """Parked run should have run_started, step_started, run_parked events."""
        store = StateStore(tmp_path / "state.db")
        pipeline = _make_pipeline(step_count=1)
        ctx = _make_context(tmp_path)
        registry = _make_registry(ParkHandler())
        runner = PipelineRunner(pipeline, ctx, registry=registry, store=store)

        result = await runner.run()
        events = store.get_audit_log(result.run_id)
        event_types = [e["event"] for e in events]
        assert "run_started" in event_types
        assert "step_started" in event_types
        assert "run_parked" in event_types

    @pytest.mark.asyncio
    async def test_error_message_preserved_in_step(self, tmp_path: Path) -> None:
        """Handler exception message should be captured in step result."""
        pipeline = _make_pipeline(step_count=1)
        ctx = _make_context(tmp_path)
        registry = _make_registry(ErrorHandler())
        runner = PipelineRunner(pipeline, ctx, registry=registry)

        result = await runner.run()
        assert "Something exploded" in result.step_records[0].result.error_message
