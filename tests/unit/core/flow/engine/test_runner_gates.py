# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for gate evaluation, retry, and feedback loops in the pipeline runner."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from specweaver.core.flow.engine.models import (
    GateCondition,
    GateDefinition,
    GateType,
    OnFailAction,
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus, StepResult, StepStatus
from specweaver.core.flow.handlers import RunContext, StepHandlerRegistry

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
            output={"verdict": "denied"},
            error_message="Mock failure",
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:01Z",
        )


class CountingHandler:
    """Fails N times then passes. Tracks call count."""

    def __init__(self, fail_count: int = 1) -> None:
        self.calls = 0
        self._fail_count = fail_count

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        self.calls += 1
        if self.calls <= self._fail_count:
            return StepResult(
                status=StepStatus.FAILED,
                output={"attempt": self.calls},
                error_message=f"Fail attempt {self.calls}",
                started_at="2026-01-01T00:00:00Z",
                completed_at="2026-01-01T00:00:01Z",
            )
        return StepResult(
            status=StepStatus.PASSED,
            output={"attempt": self.calls},
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:01Z",
        )


class AcceptHandler:
    """Returns verdict=accepted."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        return StepResult(
            status=StepStatus.PASSED,
            output={"verdict": "accepted"},
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:01Z",
        )


class DenyHandler:
    """Returns verdict=denied."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        return StepResult(
            status=StepStatus.PASSED,
            output={"verdict": "denied"},
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:01Z",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(tmp_path: Path) -> RunContext:
    return RunContext(
        project_path=tmp_path,
        spec_path=tmp_path / "spec.md",
    )


def _make_registry(**handlers) -> StepHandlerRegistry:
    """Create a registry with handlers for specific (action, target) combos."""
    registry = StepHandlerRegistry()
    for key, handler in handlers.items():
        action_str, target_str = key.split("_", 1)
        action = StepAction(action_str)
        target = StepTarget(target_str)
        registry.register(action, target, handler)
    return registry


# ---------------------------------------------------------------------------
# Gate condition evaluation
# ---------------------------------------------------------------------------


class TestGateConditions:
    """Tests for gate condition evaluation."""

    @pytest.mark.asyncio
    async def test_auto_gate_completed_passes(self, tmp_path: Path) -> None:
        """AUTO gate with COMPLETED condition passes when step passes."""
        pipeline = PipelineDefinition(
            name="test",
            steps=[
                PipelineStep(
                    name="validate",
                    action=StepAction.VALIDATE,
                    target=StepTarget.SPEC,
                    gate=GateDefinition(
                        type=GateType.AUTO,
                        condition=GateCondition.COMPLETED,
                        on_fail=OnFailAction.ABORT,
                    ),
                )
            ],
        )
        registry = StepHandlerRegistry()
        registry.register(StepAction.VALIDATE, StepTarget.SPEC, PassHandler())

        runner = PipelineRunner(pipeline, _make_context(tmp_path), registry=registry)
        run = await runner.run()

        assert run.status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_auto_gate_completed_fails_on_error(self, tmp_path: Path) -> None:
        """AUTO gate with COMPLETED condition fails when step fails."""
        pipeline = PipelineDefinition(
            name="test",
            steps=[
                PipelineStep(
                    name="validate",
                    action=StepAction.VALIDATE,
                    target=StepTarget.SPEC,
                    gate=GateDefinition(
                        type=GateType.AUTO,
                        condition=GateCondition.COMPLETED,
                        on_fail=OnFailAction.ABORT,
                    ),
                )
            ],
        )
        registry = StepHandlerRegistry()
        registry.register(StepAction.VALIDATE, StepTarget.SPEC, FailHandler())

        runner = PipelineRunner(pipeline, _make_context(tmp_path), registry=registry)
        run = await runner.run()

        assert run.status == RunStatus.FAILED

    @pytest.mark.asyncio
    async def test_auto_gate_all_passed(self, tmp_path: Path) -> None:
        """AUTO gate with ALL_PASSED condition passes when status is PASSED."""
        pipeline = PipelineDefinition(
            name="test",
            steps=[
                PipelineStep(
                    name="validate",
                    action=StepAction.VALIDATE,
                    target=StepTarget.SPEC,
                    gate=GateDefinition(
                        type=GateType.AUTO,
                        condition=GateCondition.ALL_PASSED,
                        on_fail=OnFailAction.ABORT,
                    ),
                )
            ],
        )
        registry = StepHandlerRegistry()
        registry.register(StepAction.VALIDATE, StepTarget.SPEC, PassHandler())

        runner = PipelineRunner(pipeline, _make_context(tmp_path), registry=registry)
        run = await runner.run()

        assert run.status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_auto_gate_accepted_passes(self, tmp_path: Path) -> None:
        """AUTO gate with ACCEPTED condition passes when verdict is accepted."""
        pipeline = PipelineDefinition(
            name="test",
            steps=[
                PipelineStep(
                    name="review",
                    action=StepAction.REVIEW,
                    target=StepTarget.SPEC,
                    gate=GateDefinition(
                        type=GateType.AUTO,
                        condition=GateCondition.ACCEPTED,
                        on_fail=OnFailAction.ABORT,
                    ),
                )
            ],
        )
        registry = StepHandlerRegistry()
        registry.register(StepAction.REVIEW, StepTarget.SPEC, AcceptHandler())

        runner = PipelineRunner(pipeline, _make_context(tmp_path), registry=registry)
        run = await runner.run()

        assert run.status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_auto_gate_accepted_fails_on_denied(self, tmp_path: Path) -> None:
        """AUTO gate with ACCEPTED condition aborts when verdict is denied."""
        pipeline = PipelineDefinition(
            name="test",
            steps=[
                PipelineStep(
                    name="review",
                    action=StepAction.REVIEW,
                    target=StepTarget.SPEC,
                    gate=GateDefinition(
                        type=GateType.AUTO,
                        condition=GateCondition.ACCEPTED,
                        on_fail=OnFailAction.ABORT,
                    ),
                )
            ],
        )
        registry = StepHandlerRegistry()
        registry.register(StepAction.REVIEW, StepTarget.SPEC, DenyHandler())

        runner = PipelineRunner(pipeline, _make_context(tmp_path), registry=registry)
        run = await runner.run()

        assert run.status == RunStatus.FAILED

    @pytest.mark.asyncio
    async def test_hitl_gate_parks_run(self, tmp_path: Path) -> None:
        """HITL gate always parks the run for human approval."""
        pipeline = PipelineDefinition(
            name="test",
            steps=[
                PipelineStep(
                    name="review",
                    action=StepAction.REVIEW,
                    target=StepTarget.SPEC,
                    gate=GateDefinition(
                        type=GateType.HITL,
                        condition=GateCondition.ACCEPTED,
                    ),
                )
            ],
        )
        registry = StepHandlerRegistry()
        registry.register(StepAction.REVIEW, StepTarget.SPEC, AcceptHandler())

        runner = PipelineRunner(pipeline, _make_context(tmp_path), registry=registry)
        run = await runner.run()

        assert run.status == RunStatus.PARKED

    @pytest.mark.asyncio
    @mock.patch("specweaver.core.flow.engine.reservation.SQLiteReservationSystem.acquire")
    async def test_reserve_gate_acquires_lock(
        self, mock_acquire: mock.MagicMock, tmp_path: Path
    ) -> None:
        """RESERVE gate advances when SQLite lock is acquired successfully."""
        mock_acquire.return_value = True

        pipeline = PipelineDefinition(
            name="test",
            steps=[
                PipelineStep(
                    name="validate",
                    action=StepAction.VALIDATE,
                    target=StepTarget.SPEC,
                    gate=GateDefinition(type=GateType.RESERVE),
                )
            ],
        )
        registry = StepHandlerRegistry()
        registry.register(StepAction.VALIDATE, StepTarget.SPEC, PassHandler())

        context = _make_context(tmp_path)
        context.pipeline_name = "test_pipe"

        runner = PipelineRunner(pipeline, context, registry=registry)
        run = await runner.run()

        assert mock_acquire.called
        assert mock_acquire.call_args[1]["resource_id"] == "pipeline:test_pipe"
        assert run.status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    @mock.patch("specweaver.core.flow.engine.reservation.SQLiteReservationSystem.acquire")
    async def test_reserve_gate_parks_on_collision(
        self, mock_acquire: mock.MagicMock, tmp_path: Path
    ) -> None:
        """RESERVE gate parks run safely when SQLite lock collides natively."""
        mock_acquire.return_value = False

        pipeline = PipelineDefinition(
            name="test",
            steps=[
                PipelineStep(
                    name="validate",
                    action=StepAction.VALIDATE,
                    target=StepTarget.SPEC,
                    gate=GateDefinition(type=GateType.RESERVE),
                )
            ],
        )
        registry = StepHandlerRegistry()
        registry.register(StepAction.VALIDATE, StepTarget.SPEC, PassHandler())

        context = _make_context(tmp_path)
        context.pipeline_name = "test_pipe"

        runner = PipelineRunner(pipeline, context, registry=registry)
        run = await runner.run()

        assert mock_acquire.called
        assert run.status == RunStatus.PARKED
        assert run.step_records[0].result is not None
        assert run.step_records[0].result.output.get("verdict") == "parked_for_resource"


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------


class TestRetryLogic:
    """Tests for retry on gate failure."""

    @pytest.mark.asyncio
    async def test_retry_succeeds_after_failure(self, tmp_path: Path) -> None:
        """Step fails once, then passes on retry."""
        handler = CountingHandler(fail_count=1)
        pipeline = PipelineDefinition(
            name="test",
            steps=[
                PipelineStep(
                    name="validate",
                    action=StepAction.VALIDATE,
                    target=StepTarget.SPEC,
                    gate=GateDefinition(
                        type=GateType.AUTO,
                        condition=GateCondition.COMPLETED,
                        on_fail=OnFailAction.RETRY,
                        max_retries=3,
                    ),
                )
            ],
        )
        registry = StepHandlerRegistry()
        registry.register(StepAction.VALIDATE, StepTarget.SPEC, handler)

        runner = PipelineRunner(pipeline, _make_context(tmp_path), registry=registry)
        run = await runner.run()

        assert run.status == RunStatus.COMPLETED
        assert handler.calls == 2  # 1 fail + 1 pass

    @pytest.mark.asyncio
    async def test_retry_exhausted(self, tmp_path: Path) -> None:
        """All retries fail → run fails."""
        handler = CountingHandler(fail_count=100)  # always fails
        pipeline = PipelineDefinition(
            name="test",
            steps=[
                PipelineStep(
                    name="validate",
                    action=StepAction.VALIDATE,
                    target=StepTarget.SPEC,
                    gate=GateDefinition(
                        type=GateType.AUTO,
                        condition=GateCondition.COMPLETED,
                        on_fail=OnFailAction.RETRY,
                        max_retries=2,
                    ),
                )
            ],
        )
        registry = StepHandlerRegistry()
        registry.register(StepAction.VALIDATE, StepTarget.SPEC, handler)

        runner = PipelineRunner(pipeline, _make_context(tmp_path), registry=registry)
        run = await runner.run()

        assert run.status == RunStatus.FAILED
        # 1 initial + 2 retries = 3 calls
        assert handler.calls == 3

    @pytest.mark.asyncio
    async def test_continue_on_fail(self, tmp_path: Path) -> None:
        """CONTINUE action advances despite gate failure."""
        pipeline = PipelineDefinition(
            name="test",
            steps=[
                PipelineStep(
                    name="validate",
                    action=StepAction.VALIDATE,
                    target=StepTarget.SPEC,
                    gate=GateDefinition(
                        type=GateType.AUTO,
                        condition=GateCondition.ALL_PASSED,
                        on_fail=OnFailAction.CONTINUE,
                    ),
                ),
                PipelineStep(
                    name="review",
                    action=StepAction.REVIEW,
                    target=StepTarget.SPEC,
                ),
            ],
        )
        registry = StepHandlerRegistry()
        registry.register(StepAction.VALIDATE, StepTarget.SPEC, FailHandler())
        registry.register(StepAction.REVIEW, StepTarget.SPEC, PassHandler())

        runner = PipelineRunner(pipeline, _make_context(tmp_path), registry=registry)
        run = await runner.run()

        assert run.status == RunStatus.COMPLETED
        assert run.current_step == 2  # both steps executed


# ---------------------------------------------------------------------------
# Loop-back logic
# ---------------------------------------------------------------------------


class TestLoopBack:
    """Tests for loop_back on gate failure."""

    @pytest.mark.asyncio
    async def test_loop_back_to_earlier_step(self, tmp_path: Path) -> None:
        """Review denied → loop back to draft → draft passes → review accepts."""
        draft_handler = PassHandler()
        # Review: deny first time, accept second time
        review_handler = CountingHandler(fail_count=1)

        pipeline = PipelineDefinition(
            name="test",
            steps=[
                PipelineStep(
                    name="draft",
                    action=StepAction.DRAFT,
                    target=StepTarget.SPEC,
                ),
                PipelineStep(
                    name="review",
                    action=StepAction.REVIEW,
                    target=StepTarget.SPEC,
                    gate=GateDefinition(
                        type=GateType.AUTO,
                        condition=GateCondition.COMPLETED,
                        on_fail=OnFailAction.LOOP_BACK,
                        loop_target="draft",
                        max_retries=3,
                    ),
                ),
            ],
        )
        registry = StepHandlerRegistry()
        registry.register(StepAction.DRAFT, StepTarget.SPEC, draft_handler)
        registry.register(StepAction.REVIEW, StepTarget.SPEC, review_handler)

        runner = PipelineRunner(pipeline, _make_context(tmp_path), registry=registry)
        run = await runner.run()

        assert run.status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_loop_back_exhausted(self, tmp_path: Path) -> None:
        """All loop-back retries fail → run fails."""
        pipeline = PipelineDefinition(
            name="test",
            steps=[
                PipelineStep(
                    name="draft",
                    action=StepAction.DRAFT,
                    target=StepTarget.SPEC,
                ),
                PipelineStep(
                    name="review",
                    action=StepAction.REVIEW,
                    target=StepTarget.SPEC,
                    gate=GateDefinition(
                        type=GateType.AUTO,
                        condition=GateCondition.COMPLETED,
                        on_fail=OnFailAction.LOOP_BACK,
                        loop_target="draft",
                        max_retries=1,
                    ),
                ),
            ],
        )
        registry = StepHandlerRegistry()
        registry.register(StepAction.DRAFT, StepTarget.SPEC, PassHandler())
        registry.register(StepAction.REVIEW, StepTarget.SPEC, FailHandler())

        runner = PipelineRunner(pipeline, _make_context(tmp_path), registry=registry)
        run = await runner.run()

        assert run.status == RunStatus.FAILED


# ---------------------------------------------------------------------------
# Feedback injection
# ---------------------------------------------------------------------------


class TestFeedbackInjection:
    """Tests for feedback context injection during loop-back."""

    @pytest.mark.asyncio
    async def test_feedback_stored_in_context(self, tmp_path: Path) -> None:
        """When looping back, review findings are injected into context."""
        context = _make_context(tmp_path)

        draft_handler = PassHandler()
        review_handler = CountingHandler(fail_count=1)

        pipeline = PipelineDefinition(
            name="test",
            steps=[
                PipelineStep(
                    name="draft",
                    action=StepAction.DRAFT,
                    target=StepTarget.SPEC,
                ),
                PipelineStep(
                    name="review",
                    action=StepAction.REVIEW,
                    target=StepTarget.SPEC,
                    gate=GateDefinition(
                        type=GateType.AUTO,
                        condition=GateCondition.COMPLETED,
                        on_fail=OnFailAction.LOOP_BACK,
                        loop_target="draft",
                        max_retries=3,
                    ),
                ),
            ],
        )
        registry = StepHandlerRegistry()
        registry.register(StepAction.DRAFT, StepTarget.SPEC, draft_handler)
        registry.register(StepAction.REVIEW, StepTarget.SPEC, review_handler)

        runner = PipelineRunner(pipeline, context, registry=registry)
        run = await runner.run()

        assert run.status == RunStatus.COMPLETED
        # Feedback should have been stored
        assert hasattr(context, "feedback")
        assert "draft" in context.feedback


# ---------------------------------------------------------------------------
# No gate (backwards compatibility)
# ---------------------------------------------------------------------------


class TestNoGate:
    """Tests that steps without gates behave as before (fail → stop)."""

    @pytest.mark.asyncio
    async def test_no_gate_fail_stops(self, tmp_path: Path) -> None:
        """Without a gate, failure stops the pipeline (backwards compat)."""
        pipeline = PipelineDefinition(
            name="test",
            steps=[
                PipelineStep(
                    name="validate",
                    action=StepAction.VALIDATE,
                    target=StepTarget.SPEC,
                    # No gate!
                )
            ],
        )
        registry = StepHandlerRegistry()
        registry.register(StepAction.VALIDATE, StepTarget.SPEC, FailHandler())

        runner = PipelineRunner(pipeline, _make_context(tmp_path), registry=registry)
        run = await runner.run()

        assert run.status == RunStatus.FAILED

    @pytest.mark.asyncio
    async def test_no_gate_pass_completes(self, tmp_path: Path) -> None:
        """Without a gate, success advances normally."""
        pipeline = PipelineDefinition(
            name="test",
            steps=[
                PipelineStep(
                    name="validate",
                    action=StepAction.VALIDATE,
                    target=StepTarget.SPEC,
                )
            ],
        )
        registry = StepHandlerRegistry()
        registry.register(StepAction.VALIDATE, StepTarget.SPEC, PassHandler())

        runner = PipelineRunner(pipeline, _make_context(tmp_path), registry=registry)
        run = await runner.run()

        assert run.status == RunStatus.COMPLETED


class TestGateEdgeCases:
    """Tests covering defensive edge cases in GateEvaluator."""

    def test_passes_unhandled_condition(self, tmp_path: Path) -> None:
        from specweaver.core.flow.engine.gates import GateEvaluator
        from specweaver.core.flow.engine.models import PipelineDefinition

        pipeline = PipelineDefinition(name="p", steps=[])
        evaluator = GateEvaluator(pipeline)

        gate = GateDefinition.model_construct(
            condition="UNKNOWN_ENUM_VALUE", on_fail=OnFailAction.ABORT
        )  # type: ignore
        result = StepResult(
            status=StepStatus.FAILED, output={}, started_at="now", completed_at="now"
        )
        assert evaluator.passes(gate, result) is True

    def test_find_step_index_not_found(self, tmp_path: Path) -> None:
        from specweaver.core.flow.engine.gates import GateEvaluator
        from specweaver.core.flow.engine.models import PipelineDefinition

        pipeline = PipelineDefinition(name="p", steps=[])
        evaluator = GateEvaluator(pipeline)
        assert evaluator.find_step_index("imaginary_step") is None

    def test_inject_feedback_dynamic_init(self) -> None:
        from specweaver.core.flow.engine.gates import GateEvaluator

        class MockContext:
            pass

        context = MockContext()
        result = StepResult(
            status=StepStatus.FAILED, output={"foo": "bar"}, started_at="now", completed_at="now"
        )
        GateEvaluator.inject_feedback(context, "a", "b", result)
        assert hasattr(context, "feedback")
        assert context.feedback["b"]["findings"] == {"foo": "bar"}

    def test_handle_loop_back_missing_target(self, tmp_path: Path) -> None:
        from specweaver.core.flow.engine.gates import GateEvaluator
        from specweaver.core.flow.engine.models import PipelineDefinition
        from specweaver.core.flow.engine.state import PipelineRun

        pipeline = PipelineDefinition(name="p", steps=[])
        evaluator = GateEvaluator(pipeline)
        gate = GateDefinition(
            condition=GateCondition.ALL_PASSED, on_fail=OnFailAction.LOOP_BACK, loop_target="none"
        )
        result = StepResult(
            status=StepStatus.FAILED, output={}, started_at="now", completed_at="now"
        )
        run = PipelineRun.model_construct(pipeline_name="p", steps=[])

        action = evaluator._handle_loop_back(gate, result, run, {0: 0})
        # because target doesn't exist, it stops
        assert action == "stop"

    def test_handle_retry_missing_record(self, tmp_path: Path) -> None:
        from specweaver.core.flow.engine.gates import GateEvaluator
        from specweaver.core.flow.engine.models import PipelineDefinition
        from specweaver.core.flow.engine.state import PipelineRun

        pipeline = PipelineDefinition(name="p", steps=[])
        evaluator = GateEvaluator(pipeline)
        gate = GateDefinition(
            condition=GateCondition.ALL_PASSED, on_fail=OnFailAction.RETRY, max_retries=5
        )
        result = StepResult(
            status=StepStatus.FAILED, output={}, started_at="now", completed_at="now"
        )
        # Empty step records array, simulating record is None fetch
        run = PipelineRun.model_construct(pipeline_name="p", steps=[])
        run.step_records = []

        action = evaluator._handle_retry(gate, result, run, {0: 0})
        assert action == "retry"
