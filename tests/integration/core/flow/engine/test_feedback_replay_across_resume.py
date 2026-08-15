# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A resumed run regenerates against the findings it already had. `INT-US-04` SF-01 CB-3.

`context.feedback` is an in-memory field (`run_context.py:157`). `rehydrate_from_records` rebuilt
`plan_context` and nothing else, so a resumed run regenerated with **no findings** and repeated the
mistake validation had just caught. The information was never missing — `TECH-021` retains the
failing step's `result` on loop-back precisely so a resuming human can see why it failed. Only the
replay was absent.

> [!IMPORTANT]
> **These tests assert at the CONSUMER, not on the dict.** `generation.py:87` pops
> `context.feedback[step.name]` where `step` is the step about to run — the **loop target**.
> `inject_feedback` writes under the same key. A replay that keyed on the *failing* step's name
> would build a dict nothing ever reads, and an assertion like `assert context.feedback` would pass
> anyway. So the regenerating handler records what it was handed, and that is what is asserted.

Proves: INT-US-04 FR-3.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
from specweaver.core.flow.engine.state import (
    PipelineRun,
    RunStatus,
    StepRecord,
    StepResult,
    StepStatus,
)
from specweaver.core.flow.engine.store import StateStore
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.handlers.run_context import RunContext

if TYPE_CHECKING:
    from pathlib import Path

_FINDINGS = {
    "results": [
        {
            "rule_id": "S01",
            "status": "fail",
            "message": "weasel words",
            "findings": [
                {
                    "message": "'should probably'",
                    "line": 7,
                    "severity": "error",
                    "suggestion": "cut",
                }
            ],
        }
    ],
    "total": 1,
    "passed": 0,
    "failed": 1,
}


class _RecordingDraftHandler:
    """The regenerating step. Records the feedback it was handed, exactly as the real one pops it."""

    def __init__(self) -> None:
        self.seen: list[Any] = []

    async def execute(self, step, context):
        feedback = getattr(context, "feedback", {}) or {}
        entry = feedback.pop(step.name, None)
        self.seen.append(entry)
        return StepResult(status=StepStatus.PASSED, output={}, started_at="1", completed_at="2")


class _FailOnceValidator:
    def __init__(self, *, fail_times: int = 1) -> None:
        self.calls = 0
        self._fail_times = fail_times

    async def execute(self, step, context):
        self.calls += 1
        if self.calls <= self._fail_times:
            return StepResult(
                status=StepStatus.FAILED,
                output=_FINDINGS,
                error_message="1 validation rules failed",
                started_at="1",
                completed_at="2",
            )
        return StepResult(status=StepStatus.PASSED, output={}, started_at="1", completed_at="2")


class _SnapshottingDraftHandler(_RecordingDraftHandler):
    """Snapshots the PERSISTED run the instant the loop target re-runs (W-1).

    That instant is the one a crash would freeze: the gate has reset the target and retained the
    source result, and `step_execution.py:308` has already persisted both.
    """

    def __init__(self, store: StateStore) -> None:
        super().__init__()
        self._store = store
        self.snapshot: Any = None

    async def execute(self, step, context):
        if self.seen and self.snapshot is None:
            self.snapshot = self._store.load_run(context.run.run_id)
        return await super().execute(step, context)


class _ParkingValidator:
    async def execute(self, step, context):
        return StepResult(
            status=StepStatus.WAITING_FOR_INPUT, output={}, started_at="1", completed_at="2"
        )


def _pipeline(*, on_fail: OnFailAction = OnFailAction.LOOP_BACK) -> PipelineDefinition:
    gate = GateDefinition(
        type=GateType.AUTO,
        condition=GateCondition.ALL_PASSED,
        on_fail=on_fail,
        loop_target="draft" if on_fail is OnFailAction.LOOP_BACK else None,
        max_retries=1,
    )
    return PipelineDefinition(
        name="draft_then_validate",
        steps=[
            PipelineStep(name="draft", action=StepAction.DRAFT, target=StepTarget.SPEC),
            PipelineStep(
                name="validate_spec",
                action=StepAction.VALIDATE,
                target=StepTarget.SPEC,
                gate=gate,
            ),
        ],
    )


def _interrupted_at_loop_target() -> PipelineRun:
    """The persisted state a crash between loop-back and re-execution leaves behind."""
    return PipelineRun(
        run_id="run-loopback-1",
        pipeline_name="draft_then_validate",
        project_name="proj",
        spec_path="specs/spec.md",
        status=RunStatus.RUNNING,
        current_step=0,
        step_records=[
            StepRecord(step_name="draft", status=StepStatus.PENDING, result=None),
            StepRecord(
                step_name="validate_spec",
                status=StepStatus.FAILED,
                attempt=2,
                result=StepResult(
                    status=StepStatus.FAILED,
                    output=_FINDINGS,
                    error_message="1 validation rules failed",
                    started_at="1",
                    completed_at="2",
                ),
            ),
        ],
        started_at="2026-08-14T10:00:00Z",
        updated_at="2026-08-14T10:00:00Z",
    )


def _registry(draft, validator) -> StepHandlerRegistry:
    registry = StepHandlerRegistry()
    registry.register(StepAction.DRAFT, StepTarget.SPEC, draft)
    registry.register(StepAction.VALIDATE, StepTarget.SPEC, validator)
    return registry


@pytest.mark.integration
class TestFeedbackReplayAcrossResume:
    """`rehydrate_from_records` → `replay_feedback` → the regenerating handler."""

    @pytest.mark.asyncio
    async def test_a_resumed_run_regenerates_with_the_findings(self, tmp_path: Path) -> None:
        """[Happy] The defect itself: a run interrupted at the loop target must not resume blind.

        **The interruption point is constructed, not simulated by crashing.** In one process a
        loop-back is immediately followed by re-execution, so the paused-at-target state only
        exists on disk if the process dies in between — after `inject_feedback` and its
        `runner._persist(run)` (`step_execution.py:305-308`), before the loop iterates. The record
        shape below is exactly what `gates.py:222-233` leaves behind at that instant: the failing
        step keeps its status, result and spent attempt (`TECH-021`, `TECH-033`), and the target is
        reset to PENDING with `result=None`.
        """
        store = StateStore(tmp_path / "state.db")
        run = _interrupted_at_loop_target()
        store.save_run(run)

        draft = _RecordingDraftHandler()
        ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        assert ctx.feedback == {}, "a fresh context must start with no feedback"
        runner = PipelineRunner(
            _pipeline(),
            ctx,
            store=store,
            registry=_registry(draft, _FailOnceValidator(fail_times=0)),
        )
        await runner.resume(run.run_id)

        assert draft.seen, "the resumed run never re-ran the loop target"
        replayed = draft.seen[0]
        assert replayed is not None, (
            "the regenerating step was handed NO feedback on resume — it is about to repeat the "
            "mistake validation caught, which is the whole defect FR-3 exists for"
        )
        assert replayed["from_step"] == "validate_spec"
        assert replayed["findings"]["results"][0]["rule_id"] == "S01"
        assert replayed["findings"]["results"][0]["findings"][0]["line"] == 7

    @pytest.mark.asyncio
    async def test_a_run_that_never_looped_back_replays_nothing(self, tmp_path: Path) -> None:
        """[Boundary] `PENDING` alone is not a loop-back signal — every record starts `PENDING`."""
        store = StateStore(tmp_path / "state.db")

        draft1, validator1 = _RecordingDraftHandler(), _ParkingValidator()
        ctx1 = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        runner1 = PipelineRunner(
            _pipeline(), ctx1, store=store, registry=_registry(draft1, validator1)
        )
        run1 = await runner1.run()

        draft2 = _RecordingDraftHandler()
        ctx2 = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        runner2 = PipelineRunner(
            _pipeline(),
            ctx2,
            store=store,
            registry=_registry(draft2, _FailOnceValidator(fail_times=0)),
        )
        await runner2.resume(run1.run_id)

        assert ctx2.feedback == {}, (
            f"feedback was invented for a run that never looped back: {ctx2.feedback}"
        )

    @pytest.mark.asyncio
    async def test_a_retry_gate_replays_nothing(self, tmp_path: Path) -> None:
        """[Degradation] `on_fail=RETRY` re-runs the step and never injects feedback in-session.

        Replaying for it would hand a step findings it would not have had live — the live and
        resumed paths must not diverge.
        """
        store = StateStore(tmp_path / "state.db")
        pipeline = _pipeline(on_fail=OnFailAction.RETRY)

        ctx1 = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        runner1 = PipelineRunner(
            pipeline,
            ctx1,
            store=store,
            registry=_registry(_RecordingDraftHandler(), _FailOnceValidator(fail_times=5)),
        )
        run1 = await runner1.run()

        ctx2 = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        runner2 = PipelineRunner(
            pipeline,
            ctx2,
            store=store,
            registry=_registry(_RecordingDraftHandler(), _FailOnceValidator(fail_times=0)),
        )
        await runner2.resume(run1.run_id)

        assert ctx2.feedback == {}, f"a RETRY gate must not replay feedback: {ctx2.feedback}"

    @pytest.mark.asyncio
    async def test_a_real_loop_back_leaves_the_state_the_replay_expects(
        self, tmp_path: Path
    ) -> None:
        """[Boundary] W-1 — pins the hand-built fixture above to what the engine actually produces.

        Every other test here constructs the interrupted run by hand. If `gates.py` ever stopped
        resetting the target, or stopped retaining the failing source result (`TECH-021`), those
        fixtures would drift from reality and keep passing over a dead feature. This asserts the
        three facts `replay_feedback` keys on, read back from the **store** at the moment the loop
        target re-runs.
        """
        store = StateStore(tmp_path / "state.db")
        draft = _SnapshottingDraftHandler(store)
        ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        runner = PipelineRunner(
            _pipeline(), ctx, store=store, registry=_registry(draft, _FailOnceValidator())
        )
        await runner.run()

        snap = draft.snapshot
        assert snap is not None, "the loop target never re-ran, so no loop-back was observed"

        target, source = snap.step_records[0], snap.step_records[1]
        assert snap.current_step == 0, "a loop-back must rewind current_step to the target"
        assert target.result is None, (
            "target result not cleared — nothing marks it as owing a re-run"
        )
        # PENDING right after the gate, RUNNING once re-entered; both persist, so both are crash
        # points the replay must accept. This test is what found that -- the hand-built fixtures
        # above all use PENDING, and the real state here is RUNNING.
        assert target.status in (StepStatus.PENDING, StepStatus.RUNNING), target.status
        assert source.result is not None, (
            "the failing result was discarded — TECH-021's fix is what makes the replay possible"
        )
        assert source.result.status != StepStatus.PASSED
        assert source.result.output["results"][0]["rule_id"] == "S01"
