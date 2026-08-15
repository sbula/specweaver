# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`replay_feedback` — the conjunction, and every way it must decline. `INT-US-04` SF-01 CB-3.

The seam is covered at integration tier. These are the branches a real resume cannot easily reach:
two gates sharing a loop target, a source that passed, and a pipeline edited between sessions.

Proves: INT-US-04 FR-3.
"""

from __future__ import annotations

import logging

from specweaver.core.flow.engine.hydration import replay_feedback
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
from specweaver.core.flow.engine.state import (
    PipelineRun,
    RunStatus,
    StepRecord,
    StepResult,
    StepStatus,
)
from specweaver.core.flow.handlers.run_context import RunContext


def _loop_gate(target: str) -> GateDefinition:
    return GateDefinition(
        type=GateType.AUTO,
        condition=GateCondition.ALL_PASSED,
        on_fail=OnFailAction.LOOP_BACK,
        loop_target=target,
        max_retries=2,
    )


def _pipeline(*names_and_gates) -> PipelineDefinition:
    return PipelineDefinition(
        name="p",
        steps=[
            PipelineStep(
                name=name,
                action=StepAction.VALIDATE if gate else StepAction.DRAFT,
                target=StepTarget.SPEC,
                gate=gate,
            )
            for name, gate in names_and_gates
        ],
    )


def _result(marker: str, status: StepStatus = StepStatus.FAILED) -> StepResult:
    return StepResult(status=status, output={"marker": marker}, started_at="1", completed_at="2")


def _run(records: list[StepRecord], *, current_step: int = 0) -> PipelineRun:
    return PipelineRun(
        run_id="r1",
        pipeline_name="p",
        project_name="proj",
        spec_path="specs/s.md",
        status=RunStatus.RUNNING,
        current_step=current_step,
        step_records=records,
        started_at="1",
        updated_at="1",
    )


def _ctx(tmp_path) -> RunContext:
    return RunContext(project_path=tmp_path, spec_path=tmp_path / "s.md")


_PENDING_TARGET = StepRecord(step_name="draft", status=StepStatus.PENDING, result=None)


class TestReplayFeedback:
    """The three-part condition, and the ways it correctly declines."""

    def test_the_highest_indexed_eligible_source_wins(self, tmp_path) -> None:
        """[Boundary] Two gates can share a loop target — `sw implement` already has that shape.

        `run_tests` and `validate_code` both point at `generate_code` there. Without a tie-break the
        replay is whichever the loop happened to see first.
        """
        pipeline = _pipeline(
            ("draft", None),
            ("first_gate", _loop_gate("draft")),
            ("second_gate", _loop_gate("draft")),
        )
        run = _run(
            [
                _PENDING_TARGET,
                StepRecord(
                    step_name="first_gate", status=StepStatus.FAILED, result=_result("first")
                ),
                StepRecord(
                    step_name="second_gate", status=StepStatus.FAILED, result=_result("second")
                ),
            ]
        )
        context = _ctx(tmp_path)

        replay_feedback(pipeline, run, context)

        assert context.feedback["draft"]["from_step"] == "second_gate"
        assert context.feedback["draft"]["findings"]["marker"] == "second"

    def test_a_passed_source_replays_nothing(self, tmp_path) -> None:
        """[Degradation] A gate that passed injected no feedback live; nor may a resume."""
        pipeline = _pipeline(("draft", None), ("gate", _loop_gate("draft")))
        run = _run(
            [
                _PENDING_TARGET,
                StepRecord(
                    step_name="gate",
                    status=StepStatus.PASSED,
                    result=_result("x", StepStatus.PASSED),
                ),
            ]
        )
        context = _ctx(tmp_path)

        replay_feedback(pipeline, run, context)
        assert context.feedback == {}

    def test_a_source_with_no_result_replays_nothing(self, tmp_path) -> None:
        """[Boundary] Before `TECH-021` every loop-back left this state; there is nothing to replay."""
        pipeline = _pipeline(("draft", None), ("gate", _loop_gate("draft")))
        run = _run(
            [_PENDING_TARGET, StepRecord(step_name="gate", status=StepStatus.FAILED, result=None)]
        )
        context = _ctx(tmp_path)

        replay_feedback(pipeline, run, context)
        assert context.feedback == {}

    def test_a_target_that_already_ran_replays_nothing(self, tmp_path) -> None:
        """[Boundary] Feedback is consumed exactly once; a re-run target must not get it twice."""
        pipeline = _pipeline(("draft", None), ("gate", _loop_gate("draft")))
        run = _run(
            [
                StepRecord(step_name="draft", status=StepStatus.PASSED, result=_result("done")),
                StepRecord(step_name="gate", status=StepStatus.FAILED, result=_result("f")),
            ]
        )
        context = _ctx(tmp_path)

        replay_feedback(pipeline, run, context)
        assert context.feedback == {}

    def test_a_parked_target_replays_nothing(self, tmp_path) -> None:
        """[Boundary] A HITL park also leaves a target awaiting execution — but not via loop-back."""
        pipeline = _pipeline(("draft", None), ("gate", _loop_gate("draft")))
        run = _run(
            [
                StepRecord(step_name="draft", status=StepStatus.WAITING_FOR_INPUT, result=None),
                StepRecord(step_name="gate", status=StepStatus.FAILED, result=_result("f")),
            ]
        )
        context = _ctx(tmp_path)

        replay_feedback(pipeline, run, context)
        assert context.feedback == {}

    def test_a_renamed_target_warns_and_replays_nothing(self, tmp_path, caplog) -> None:
        """[Degradation] The pipeline YAML can be edited between sessions.

        `rehydrate_from_records` guards the same way; a resume must survive it rather than hydrate
        the wrong step.
        """
        pipeline = _pipeline(("draft_v2", None), ("gate", _loop_gate("draft_v2")))
        run = _run(
            [
                _PENDING_TARGET,
                StepRecord(step_name="gate", status=StepStatus.FAILED, result=_result("f")),
            ]
        )
        context = _ctx(tmp_path)

        with caplog.at_level(logging.WARNING):
            replay_feedback(pipeline, run, context)

        assert context.feedback == {}
        assert any("skipping feedback replay" in r.getMessage() for r in caplog.records), (
            caplog.text
        )

    def test_a_current_step_out_of_range_is_a_no_op(self, tmp_path) -> None:
        """[Hostile] A resumed run may name an index the current pipeline no longer has."""
        pipeline = _pipeline(("draft", None), ("gate", _loop_gate("draft")))
        run = _run([_PENDING_TARGET], current_step=99)
        context = _ctx(tmp_path)

        replay_feedback(pipeline, run, context)
        assert context.feedback == {}

    def test_empty_step_records_is_a_no_op(self, tmp_path) -> None:
        """[Boundary] Mirrors `rehydrate_from_records`' own empty-records case."""
        replay_feedback(_pipeline(("draft", None)), _run([]), _ctx(tmp_path))

    def test_a_retry_gate_is_not_a_loop_back(self, tmp_path) -> None:
        """[Boundary] `on_fail=RETRY` re-runs the step in place and injects nothing live."""
        retry_gate = GateDefinition(
            type=GateType.AUTO,
            condition=GateCondition.ALL_PASSED,
            on_fail=OnFailAction.RETRY,
            max_retries=2,
        )
        pipeline = _pipeline(("draft", None), ("gate", retry_gate))
        run = _run(
            [
                _PENDING_TARGET,
                StepRecord(step_name="gate", status=StepStatus.FAILED, result=_result("f")),
            ]
        )
        context = _ctx(tmp_path)

        replay_feedback(pipeline, run, context)
        assert context.feedback == {}

    def test_a_renamed_source_step_is_skipped(self, tmp_path) -> None:
        """[Degradation] W-2 — the source-side name guard, which nothing had executed.

        Only the renamed *target* was covered. A pipeline edited between sessions can just as
        easily rename the gate step, and pairing a stored record with the wrong definition would
        replay another step's findings.
        """
        pipeline = _pipeline(("draft", None), ("gate_v2", _loop_gate("draft")))
        run = _run(
            [
                _PENDING_TARGET,
                StepRecord(step_name="gate_v1", status=StepStatus.FAILED, result=_result("stale")),
            ]
        )
        context = _ctx(tmp_path)

        replay_feedback(pipeline, run, context)
        assert context.feedback == {}

    def test_a_running_target_replays_too(self, tmp_path) -> None:
        """[Boundary] The second crash point: the process died mid-regeneration.

        `mark_step_running` flips the target to RUNNING before the handler executes, and that is
        persisted. Requiring PENDING alone would leave such a run to resume blind. Found by CB-3's
        W-1, which pinned the fixtures to a real loop-back.
        """
        pipeline = _pipeline(("draft", None), ("gate", _loop_gate("draft")))
        run = _run(
            [
                StepRecord(step_name="draft", status=StepStatus.RUNNING, result=None),
                StepRecord(step_name="gate", status=StepStatus.FAILED, result=_result("f")),
            ]
        )
        context = _ctx(tmp_path)

        replay_feedback(pipeline, run, context)
        assert context.feedback["draft"]["findings"]["marker"] == "f"
