# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests — flow engine with real StateStore, gates, and handlers.

Exercises PipelineRunner with real StateStore persistence and gate logic.
Only the LLM adapter is mocked. All state management, gate evaluation,
retry/loop-back, and feedback injection are tested end-to-end.

Uses the shared ``sample_project`` fixture for project scaffolding.
"""

from __future__ import annotations
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.base import StepHandler
from specweaver.core.flow.handlers.registry import StepHandlerRegistry

import asyncio
from typing import TYPE_CHECKING

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
from specweaver.core.flow.engine.store import StateStore


if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(project: Path) -> RunContext:
    """Create a RunContext from a sample project path."""
    spec = project / "specs" / "calculator.md"
    return RunContext(project_path=project, spec_path=spec)


def _make_store(project: Path) -> StateStore:
    """Create a StateStore in the project directory."""
    return StateStore(project / ".specweaver" / "pipeline_state.db")


class _AlwaysPassHandler:
    """Handler that always returns PASSED."""

    async def execute(
        self,
        step: PipelineStep,
        context: RunContext,
    ) -> StepResult:
        from specweaver.core.flow.handlers.base import _now_iso

        started = _now_iso()
        return StepResult(
            status=StepStatus.PASSED,
            output={"verdict": "accepted"},
            started_at=started,
            completed_at=_now_iso(),
        )


class _AlwaysFailHandler:
    """Handler that always returns FAILED."""

    async def execute(
        self,
        step: PipelineStep,
        context: RunContext,
    ) -> StepResult:
        from specweaver.core.flow.handlers.base import _now_iso

        started = _now_iso()
        return StepResult(
            status=StepStatus.FAILED,
            output={"error_count": 3},
            error_message="Validation failed",
            started_at=started,
            completed_at=_now_iso(),
        )


class _CountingHandler:
    """Handler that fails N times, then passes."""

    def __init__(self, fail_count: int = 2) -> None:
        self.calls = 0
        self.fail_count = fail_count

    async def execute(
        self,
        step: PipelineStep,
        context: RunContext,
    ) -> StepResult:
        from specweaver.core.flow.handlers.base import _now_iso

        self.calls += 1
        started = _now_iso()
        if self.calls <= self.fail_count:
            return StepResult(
                status=StepStatus.FAILED,
                output={"attempt": self.calls},
                error_message=f"Fail #{self.calls}",
                started_at=started,
                completed_at=_now_iso(),
            )
        return StepResult(
            status=StepStatus.PASSED,
            output={"attempt": self.calls, "verdict": "accepted"},
            started_at=started,
            completed_at=_now_iso(),
        )


class _HITLHandler:
    """Handler that returns WAITING_FOR_INPUT."""

    async def execute(
        self,
        step: PipelineStep,
        context: RunContext,
    ) -> StepResult:
        from specweaver.core.flow.handlers.base import _now_iso

        started = _now_iso()
        return StepResult(
            status=StepStatus.WAITING_FOR_INPUT,
            output={"question": "Approve?"},
            started_at=started,
            completed_at=_now_iso(),
        )


def _registry_with(*handlers: tuple[StepAction, StepTarget, StepHandler]) -> StepHandlerRegistry:
    """Build a registry with custom handlers."""
    reg = StepHandlerRegistry()
    for action, target, handler in handlers:
        reg.register(action, target, handler)
    return reg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFlowEngineCompletion:
    """Pipeline runs to completion with real state persistence."""

    def test_simple_two_step_pipeline_completes(self, sample_project: Path) -> None:
        """Two-step pipeline (validate+check) runs to COMPLETED."""
        pipeline = PipelineDefinition(
            name="simple",
            steps=[
                PipelineStep(
                    name="validate_spec",
                    action=StepAction.VALIDATE,
                    target=StepTarget.SPEC,
                ),
                PipelineStep(
                    name="validate_code",
                    action=StepAction.VALIDATE,
                    target=StepTarget.CODE,
                ),
            ],
        )

        ctx = _make_context(sample_project)
        store = _make_store(sample_project)
        registry = _registry_with(
            (StepAction.VALIDATE, StepTarget.SPEC, _AlwaysPassHandler()),
            (StepAction.VALIDATE, StepTarget.CODE, _AlwaysPassHandler()),
        )

        runner = PipelineRunner(pipeline, ctx, registry=registry, store=store)
        run = asyncio.run(runner.run())

        assert run.status == RunStatus.COMPLETED
        assert run.current_step == 2
        assert all(r.status == StepStatus.PASSED for r in run.step_records)

        # State was persisted
        reloaded = store.load_run(run.run_id)
        assert reloaded is not None
        assert reloaded.status == RunStatus.COMPLETED

    def test_state_persistence_across_steps(self, sample_project: Path) -> None:
        """State is persisted after each step (audit log has all events)."""
        pipeline = PipelineDefinition(
            name="audit",
            steps=[
                PipelineStep(
                    name="step_a",
                    action=StepAction.VALIDATE,
                    target=StepTarget.SPEC,
                ),
                PipelineStep(
                    name="step_b",
                    action=StepAction.VALIDATE,
                    target=StepTarget.CODE,
                ),
            ],
        )

        ctx = _make_context(sample_project)
        store = _make_store(sample_project)
        registry = _registry_with(
            (StepAction.VALIDATE, StepTarget.SPEC, _AlwaysPassHandler()),
            (StepAction.VALIDATE, StepTarget.CODE, _AlwaysPassHandler()),
        )

        runner = PipelineRunner(pipeline, ctx, registry=registry, store=store)
        run = asyncio.run(runner.run())

        # Audit log should have multiple events
        log = store.get_audit_log(run.run_id)
        events = [entry["event"] for entry in log]
        assert "run_started" in events
        assert "run_completed" in events
        assert events.count("step_started") == 2
        assert events.count("step_completed") == 2

    def test_empty_pipeline_completes_immediately(self, sample_project: Path) -> None:
        """Pipeline with no steps → COMPLETED immediately."""
        pipeline = PipelineDefinition(name="empty", steps=[])
        ctx = _make_context(sample_project)
        store = _make_store(sample_project)

        runner = PipelineRunner(pipeline, ctx, store=store)
        run = asyncio.run(runner.run())

        assert run.status == RunStatus.COMPLETED


class TestFlowEngineGates:
    """Gate evaluation with retry, loop-back, HITL, and abort."""

    def test_gate_retry_then_pass(self, sample_project: Path) -> None:
        """Step fails twice, gate retries, third attempt passes."""
        counting = _CountingHandler(fail_count=2)

        pipeline = PipelineDefinition(
            name="retry",
            steps=[
                PipelineStep(
                    name="flaky_step",
                    action=StepAction.VALIDATE,
                    target=StepTarget.SPEC,
                    gate=GateDefinition(
                        type=GateType.AUTO,
                        condition=GateCondition.COMPLETED,
                        on_fail=OnFailAction.RETRY,
                        max_retries=3,
                    ),
                ),
            ],
        )

        ctx = _make_context(sample_project)
        store = _make_store(sample_project)
        registry = _registry_with(
            (StepAction.VALIDATE, StepTarget.SPEC, counting),
        )

        runner = PipelineRunner(pipeline, ctx, registry=registry, store=store)
        run = asyncio.run(runner.run())

        assert run.status == RunStatus.COMPLETED
        assert counting.calls == 3  # failed 2, passed on 3rd

    def test_gate_retry_exhausted(self, sample_project: Path) -> None:
        """Step always fails → retries exhausted → FAILED."""
        pipeline = PipelineDefinition(
            name="exhausted",
            steps=[
                PipelineStep(
                    name="always_fail",
                    action=StepAction.VALIDATE,
                    target=StepTarget.SPEC,
                    gate=GateDefinition(
                        type=GateType.AUTO,
                        condition=GateCondition.COMPLETED,
                        on_fail=OnFailAction.RETRY,
                        max_retries=2,
                    ),
                ),
            ],
        )

        ctx = _make_context(sample_project)
        store = _make_store(sample_project)
        registry = _registry_with(
            (StepAction.VALIDATE, StepTarget.SPEC, _AlwaysFailHandler()),
        )

        runner = PipelineRunner(pipeline, ctx, registry=registry, store=store)
        run = asyncio.run(runner.run())

        assert run.status == RunStatus.FAILED

    def test_gate_abort_on_failure(self, sample_project: Path) -> None:
        """Gate with on_fail=ABORT stops immediately."""
        pipeline = PipelineDefinition(
            name="abort",
            steps=[
                PipelineStep(
                    name="must_pass",
                    action=StepAction.VALIDATE,
                    target=StepTarget.SPEC,
                    gate=GateDefinition(
                        type=GateType.AUTO,
                        condition=GateCondition.ALL_PASSED,
                        on_fail=OnFailAction.ABORT,
                    ),
                ),
                PipelineStep(
                    name="never_reached",
                    action=StepAction.VALIDATE,
                    target=StepTarget.CODE,
                ),
            ],
        )

        ctx = _make_context(sample_project)
        store = _make_store(sample_project)
        registry = _registry_with(
            (StepAction.VALIDATE, StepTarget.SPEC, _AlwaysFailHandler()),
            (StepAction.VALIDATE, StepTarget.CODE, _AlwaysPassHandler()),
        )

        runner = PipelineRunner(pipeline, ctx, registry=registry, store=store)
        run = asyncio.run(runner.run())

        assert run.status == RunStatus.FAILED
        # Second step should still be PENDING (never executed)
        assert run.step_records[1].status == StepStatus.PENDING

    def test_hitl_gate_parks_pipeline(self, sample_project: Path) -> None:
        """HITL gate parks the pipeline for human approval."""
        pipeline = PipelineDefinition(
            name="hitl",
            steps=[
                PipelineStep(
                    name="needs_approval",
                    action=StepAction.REVIEW,
                    target=StepTarget.SPEC,
                    gate=GateDefinition(
                        type=GateType.HITL,
                        condition=GateCondition.ACCEPTED,
                    ),
                ),
            ],
        )

        ctx = _make_context(sample_project)
        store = _make_store(sample_project)
        registry = _registry_with(
            (StepAction.REVIEW, StepTarget.SPEC, _AlwaysPassHandler()),
        )

        runner = PipelineRunner(pipeline, ctx, registry=registry, store=store)
        run = asyncio.run(runner.run())

        assert run.status == RunStatus.PARKED

        # State was persisted — can be resumed
        reloaded = store.load_run(run.run_id)
        assert reloaded is not None
        assert reloaded.status == RunStatus.PARKED

    def test_loop_back_with_feedback_injection(self, sample_project: Path) -> None:
        """Loop-back gate injects feedback into context and re-runs."""
        counting = _CountingHandler(fail_count=1)

        pipeline = PipelineDefinition(
            name="loop",
            steps=[
                PipelineStep(
                    name="draft_spec",
                    action=StepAction.DRAFT,
                    target=StepTarget.SPEC,
                ),
                PipelineStep(
                    name="review_spec",
                    action=StepAction.REVIEW,
                    target=StepTarget.SPEC,
                    gate=GateDefinition(
                        type=GateType.AUTO,
                        condition=GateCondition.ACCEPTED,
                        on_fail=OnFailAction.LOOP_BACK,
                        loop_target="draft_spec",
                        max_retries=3,
                    ),
                ),
            ],
        )

        ctx = _make_context(sample_project)
        store = _make_store(sample_project)
        registry = _registry_with(
            (StepAction.DRAFT, StepTarget.SPEC, _AlwaysPassHandler()),
            (StepAction.REVIEW, StepTarget.SPEC, counting),
        )

        runner = PipelineRunner(pipeline, ctx, registry=registry, store=store)
        run = asyncio.run(runner.run())

        assert run.status == RunStatus.COMPLETED
        assert counting.calls == 2  # failed once, looped back, passed

    def test_gate_continue_on_failure(self, sample_project: Path) -> None:
        """Gate with on_fail=CONTINUE advances even on failure."""
        pipeline = PipelineDefinition(
            name="continue",
            steps=[
                PipelineStep(
                    name="optional_step",
                    action=StepAction.VALIDATE,
                    target=StepTarget.SPEC,
                    gate=GateDefinition(
                        type=GateType.AUTO,
                        condition=GateCondition.ALL_PASSED,
                        on_fail=OnFailAction.CONTINUE,
                    ),
                ),
                PipelineStep(
                    name="must_run",
                    action=StepAction.VALIDATE,
                    target=StepTarget.CODE,
                ),
            ],
        )

        ctx = _make_context(sample_project)
        store = _make_store(sample_project)
        registry = _registry_with(
            (StepAction.VALIDATE, StepTarget.SPEC, _AlwaysFailHandler()),
            (StepAction.VALIDATE, StepTarget.CODE, _AlwaysPassHandler()),
        )

        runner = PipelineRunner(pipeline, ctx, registry=registry, store=store)
        run = asyncio.run(runner.run())

        assert run.status == RunStatus.COMPLETED
        assert run.current_step == 2


class TestFlowEngineResume:
    """Pipeline pause/resume with state persistence."""

    def test_resume_after_waiting_for_input(self, sample_project: Path) -> None:
        """Handler returns WAITING_FOR_INPUT → parks, resume → completes."""
        pipeline = PipelineDefinition(
            name="resume",
            steps=[
                PipelineStep(
                    name="interactive_step",
                    action=StepAction.REVIEW,
                    target=StepTarget.SPEC,
                ),
                PipelineStep(
                    name="final_step",
                    action=StepAction.VALIDATE,
                    target=StepTarget.CODE,
                ),
            ],
        )

        ctx = _make_context(sample_project)
        store = _make_store(sample_project)

        # First run: HITL handler parks the pipeline
        registry1 = _registry_with(
            (StepAction.REVIEW, StepTarget.SPEC, _HITLHandler()),
            (StepAction.VALIDATE, StepTarget.CODE, _AlwaysPassHandler()),
        )
        runner1 = PipelineRunner(pipeline, ctx, registry=registry1, store=store)
        run1 = asyncio.run(runner1.run())
        assert run1.status == RunStatus.PARKED
        assert run1.current_step == 0

        # State was persisted
        reloaded = store.load_run(run1.run_id)
        assert reloaded is not None
        assert reloaded.status == RunStatus.PARKED

        # Resume: handler now returns PASSED (human approved externally)
        registry2 = _registry_with(
            (StepAction.REVIEW, StepTarget.SPEC, _AlwaysPassHandler()),
            (StepAction.VALIDATE, StepTarget.CODE, _AlwaysPassHandler()),
        )
        runner2 = PipelineRunner(pipeline, ctx, registry=registry2, store=store)
        run2 = asyncio.run(runner2.resume(run1.run_id))
        assert run2.status == RunStatus.COMPLETED
        assert run2.current_step == 2
