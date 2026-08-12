# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for resume-time plan rehydration — INT-US-21 SF-01 CB-3 (FR-3).

`context.plan_context.decomposition` / `context.plan_context.plan` live in memory and die with the process. On
`resume()` they must be rebuilt from **persisted step records** before the loop starts,
replaying the same `hydrate_plan_context` the live path uses so the two cannot diverge.

The load-bearing subtlety: a gate-parked step's RECORD status is WAITING_FOR_INPUT while its
stored RESULT status is PASSED. Keying on the record status would silently skip exactly the
step a resumed run needs (design R/B R2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.commons import json
from specweaver.core.flow.engine.hydration import rehydrate_from_records
from specweaver.core.flow.engine.models import (
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

if TYPE_CHECKING:
    from pathlib import Path


def _step(action: StepAction, target: StepTarget, name: str) -> PipelineStep:
    return PipelineStep(name=name, action=action, target=target)


def _pipeline(*steps: PipelineStep) -> PipelineDefinition:
    return PipelineDefinition(name="p", steps=list(steps))


def _run(*records: StepRecord, current_step: int = 0) -> PipelineRun:
    return PipelineRun(
        run_id="run-1",
        pipeline_name="p",
        project_name="proj",
        spec_path="specs/x_feature_spec.md",
        status=RunStatus.PARKED,
        current_step=current_step,
        step_records=list(records),
        started_at="1",
        updated_at="2",
    )


def _record(
    name: str,
    record_status: StepStatus,
    result_status: StepStatus | None = None,
    **output,
) -> StepRecord:
    result = None
    if result_status is not None:
        result = StepResult(status=result_status, output=output, started_at="1", completed_at="2")
    return StepRecord(step_name=name, status=record_status, result=result)


def _ctx(tmp_path: Path) -> RunContext:
    return RunContext(project_path=tmp_path, spec_path=tmp_path / "x_feature_spec.md")


DECOMPOSE = _step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose")
PLAN = _step(StepAction.PLAN, StepTarget.SPEC, "plan_spec")


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestRehydrationHappyPath:
    def test_gate_parked_record_still_rehydrates(self, tmp_path: Path) -> None:
        """THE case FR-3 exists for: record WAITING_FOR_INPUT, stored result PASSED."""
        ctx = _ctx(tmp_path)
        run = _run(
            _record(
                "decompose",
                StepStatus.WAITING_FOR_INPUT,
                StepStatus.PASSED,
                components=[{"name": "auth"}],
            )
        )

        rehydrate_from_records(_pipeline(DECOMPOSE), run, ctx)

        assert ctx.plan_context.decomposition is not None
        assert json.loads(ctx.plan_context.decomposition)["components"][0]["name"] == "auth"

    def test_completed_record_rehydrates(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        run = _run(_record("decompose", StepStatus.PASSED, StepStatus.PASSED, components=[]))

        rehydrate_from_records(_pipeline(DECOMPOSE), run, ctx)

        assert ctx.plan_context.decomposition == "{}" or ctx.plan_context.decomposition is not None

    def test_plan_record_rehydrates_from_the_artifact_file(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        plan_file = tmp_path / "x_plan.yaml"
        plan_file.write_text("impl: plan\n", encoding="utf-8")
        run = _run(
            _record("plan_spec", StepStatus.PASSED, StepStatus.PASSED, plan_path=str(plan_file))
        )

        rehydrate_from_records(_pipeline(PLAN), run, ctx)

        assert ctx.plan_context.plan == "impl: plan\n"

    def test_both_fields_rehydrate_in_one_pass(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        plan_file = tmp_path / "x_plan.yaml"
        plan_file.write_text("impl: plan\n", encoding="utf-8")
        run = _run(
            _record("plan_spec", StepStatus.PASSED, StepStatus.PASSED, plan_path=str(plan_file)),
            _record(
                "decompose",
                StepStatus.WAITING_FOR_INPUT,
                StepStatus.PASSED,
                components=[{"name": "auth"}],
            ),
            current_step=1,
        )

        rehydrate_from_records(_pipeline(PLAN, DECOMPOSE), run, ctx)

        assert ctx.plan_context.plan == "impl: plan\n"
        assert ctx.plan_context.decomposition is not None

    def test_later_index_wins(self, tmp_path: Path) -> None:
        """A loop_back that re-ran decompose leaves two records; the newest must win."""
        ctx = _ctx(tmp_path)
        run = _run(
            _record("decompose", StepStatus.PASSED, StepStatus.PASSED, components=[{"n": "old"}]),
            _record("decompose2", StepStatus.PASSED, StepStatus.PASSED, components=[{"n": "new"}]),
        )
        pipeline = _pipeline(
            DECOMPOSE, _step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose2")
        )

        rehydrate_from_records(pipeline, run, ctx)

        assert json.loads(ctx.plan_context.decomposition)["components"][0]["n"] == "new"


# ---------------------------------------------------------------------------
# Boundary / edge cases
# ---------------------------------------------------------------------------


class TestRehydrationBoundaries:
    def test_empty_step_records_is_a_noop(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)

        rehydrate_from_records(_pipeline(DECOMPOSE), _run(), ctx)

        assert ctx.plan_context.decomposition is None

    def test_more_records_than_pipeline_steps_skips_the_overflow(
        self, tmp_path: Path, caplog
    ) -> None:
        """A YAML edited between sessions can leave stored records with no step definition."""
        ctx = _ctx(tmp_path)
        run = _run(
            _record("decompose", StepStatus.PASSED, StepStatus.PASSED, components=[{"n": "a"}]),
            _record("gone", StepStatus.PASSED, StepStatus.PASSED, components=[{"n": "b"}]),
        )

        with caplog.at_level("WARNING"):
            rehydrate_from_records(_pipeline(DECOMPOSE), run, ctx)

        assert json.loads(ctx.plan_context.decomposition)["components"][0]["n"] == "a"
        assert any("gone" in r.getMessage() for r in caplog.records)

    def test_reordered_pipeline_skips_mismatched_indices(self, tmp_path: Path, caplog) -> None:
        """Same length, steps swapped — index pairing alone would hydrate the wrong field."""
        ctx = _ctx(tmp_path)
        run = _run(
            _record("decompose", StepStatus.PASSED, StepStatus.PASSED, components=[{"n": "a"}])
        )
        # The YAML now has a DIFFERENT step at index 0.
        reordered = _pipeline(_step(StepAction.VALIDATE, StepTarget.SPEC, "validate_spec"))

        with caplog.at_level("WARNING"):
            rehydrate_from_records(reordered, run, ctx)

        assert ctx.plan_context.decomposition is None
        assert any("decompose" in r.getMessage() for r in caplog.records)

    def test_resuming_with_a_different_pipeline_warns_up_front(
        self, tmp_path: Path, caplog
    ) -> None:
        """The caller picks the PipelineDefinition; nothing guarantees it produced these records.

        The REST resume path resolves the pipeline independently of the CLI path, so a mismatch
        is reachable. Warn once for the whole run rather than only per-step.
        """
        ctx = _ctx(tmp_path)
        run = _run(
            _record("decompose", StepStatus.PASSED, StepStatus.PASSED, components=[{"n": "a"}])
        )
        run.pipeline_name = "a_completely_different_pipeline"

        with caplog.at_level("WARNING"):
            rehydrate_from_records(_pipeline(DECOMPOSE), run, ctx)

        assert any("a_completely_different_pipeline" in r.getMessage() for r in caplog.records)
        # Same-named steps still rehydrate — the warning is advisory, not a hard stop.
        assert ctx.plan_context.decomposition is not None

    def test_fewer_records_than_steps_is_fine(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        run = _run(
            _record("decompose", StepStatus.PASSED, StepStatus.PASSED, components=[{"n": "a"}])
        )

        rehydrate_from_records(_pipeline(DECOMPOSE, PLAN), run, ctx)

        assert ctx.plan_context.decomposition is not None


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------


class TestRehydrationDegradation:
    def test_record_with_no_result_is_skipped(self, tmp_path: Path) -> None:
        """_handle_loop_back resets a target record to result=None — must not AttributeError."""
        ctx = _ctx(tmp_path)
        run = _run(_record("decompose", StepStatus.PENDING, None))

        rehydrate_from_records(_pipeline(DECOMPOSE), run, ctx)

        assert ctx.plan_context.decomposition is None

    def test_plan_artifact_deleted_between_sessions_warns_and_skips(
        self, tmp_path: Path, caplog
    ) -> None:
        ctx = _ctx(tmp_path)
        run = _run(
            _record(
                "plan_spec",
                StepStatus.PASSED,
                StepStatus.PASSED,
                plan_path=str(tmp_path / "vanished_plan.yaml"),
            )
        )

        with caplog.at_level("WARNING"):
            rehydrate_from_records(_pipeline(PLAN), run, ctx)

        assert ctx.plan_context.plan is None
        assert any("vanished_plan.yaml" in r.getMessage() for r in caplog.records)

    def test_a_failed_record_does_not_rehydrate(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        run = _run(
            _record("decompose", StepStatus.FAILED, StepStatus.FAILED, components=[{"n": "a"}])
        )

        rehydrate_from_records(_pipeline(DECOMPOSE), run, ctx)

        assert ctx.plan_context.decomposition is None


# ---------------------------------------------------------------------------
# Hostile / wrong input
# ---------------------------------------------------------------------------


class TestRehydrationHostile:
    def test_handler_parked_record_does_not_rehydrate(self, tmp_path: Path) -> None:
        """Handler-park: BOTH record and result are WAITING_FOR_INPUT — nothing was produced."""
        ctx = _ctx(tmp_path)
        run = _run(_record("decompose", StepStatus.WAITING_FOR_INPUT, StepStatus.WAITING_FOR_INPUT))

        rehydrate_from_records(_pipeline(DECOMPOSE), run, ctx)

        assert ctx.plan_context.decomposition is None

    @pytest.mark.parametrize(
        "result_status",
        [StepStatus.ERROR, StepStatus.SKIPPED, StepStatus.PENDING, StepStatus.RUNNING],
    )
    def test_non_passed_stored_results_never_rehydrate(
        self, tmp_path: Path, result_status: StepStatus
    ) -> None:
        ctx = _ctx(tmp_path)
        run = _run(_record("decompose", StepStatus.WAITING_FOR_INPUT, result_status, components=[]))

        rehydrate_from_records(_pipeline(DECOMPOSE), run, ctx)

        assert ctx.plan_context.decomposition is None

    def test_corrupt_plan_path_type_does_not_raise(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        run = _run(_record("plan_spec", StepStatus.PASSED, StepStatus.PASSED, plan_path=12345))

        rehydrate_from_records(_pipeline(PLAN), run, ctx)

        assert ctx.plan_context.plan is None


# NOTE: the resume() wiring is proven at the INTEGRATION level, where it belongs —
# tests/integration/core/flow/engine/test_rehydration_integration.py drives two real runner
# sessions through a real StateStore (SQLite), which is the seam FR-3 actually depends on.
# A version of that test briefly lived here; it used a real store and two sessions, so it was
# an integration test wearing a unit test's clothes.
