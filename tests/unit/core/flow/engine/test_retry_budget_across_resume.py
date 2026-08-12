# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A step's retry budget must survive `sw resume` (`TECH-033`).

`gate.max_retries` is checked against `LoopState.attempts`, which `_execute_loop` builds empty on
every entry. `resume()` re-enters that loop, so every resume handed the step a full fresh budget —
`max_retries: 3` bounded retries *per session*, not per step.

**Why no existing test catches it.** Every retry test lives inside a single `_execute_loop` entry,
where the counter is correct. The reset is only observable across a resume, which means the test
has to persist a run, load it back, and count executions on the far side.

The case that matters is not an exhausted run being restarted — it is a `loop_back` interrupted by
a HITL park. Step fails, loops back, the run parks, a human resumes: one in-flight loop, whose
budget must carry. `_handle_loop_back` did not even record what it spent, so that path was broken
on both sides.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.engine.models import (
    GateDefinition,
    GateType,
    OnFailAction,
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.engine.store import StateStore
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.handlers.run_context import RunContext

if TYPE_CHECKING:
    from pathlib import Path

MAX_RETRIES = 3


class CountingFailHandler:
    """Always fails, and counts how many times it was actually asked to run."""

    def __init__(self) -> None:
        self.executions = 0

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        self.executions += 1
        return StepResult(
            status=StepStatus.FAILED,
            error_message="deliberate failure",
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:01Z",
        )


def _retry_pipeline() -> PipelineDefinition:
    return PipelineDefinition(
        name="retry_pipe",
        steps=[
            PipelineStep(
                name="flaky",
                action=StepAction.VALIDATE,
                target=StepTarget.SPEC,
                gate=GateDefinition(
                    type=GateType.AUTO,
                    on_fail=OnFailAction.RETRY,
                    max_retries=MAX_RETRIES,
                ),
            )
        ],
    )


def _runner(tmp_path: Path, store: StateStore, handler: CountingFailHandler) -> PipelineRunner:
    registry = StepHandlerRegistry()
    registry.register(StepAction.VALIDATE, StepTarget.SPEC, handler)
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "specs" / "test.md")
    return PipelineRunner(_retry_pipeline(), context, registry=registry, store=store)


@pytest.mark.asyncio
async def test_a_first_run_spends_exactly_the_declared_budget(tmp_path: Path) -> None:
    """The baseline, and the vacuity guard for everything below.

    `max_retries: 3` means the initial attempt plus three retries — four executions. If this ever
    reads zero the handler was never reached and the resume assertions would pass while proving
    nothing.
    """
    store = StateStore(tmp_path / "flow.db")
    handler = CountingFailHandler()

    run = await _runner(tmp_path, store, handler).run()

    assert handler.executions == MAX_RETRIES + 1, "initial attempt plus three retries"
    assert run.step_records[0].status == StepStatus.FAILED


@pytest.mark.asyncio
async def test_a_resume_does_not_hand_back_a_fresh_budget(tmp_path: Path) -> None:
    """The core `TECH-033` claim.

    Before the fix a resume restarted the counter at zero and spent the whole budget again, so a
    run could burn `max_retries` per resume without limit. After it, the persisted counter is read
    back: the step gets one final attempt, the gate sees the budget is gone, and the run stops.
    """
    store = StateStore(tmp_path / "flow.db")
    first = CountingFailHandler()
    run = await _runner(tmp_path, store, first).run()

    resumed = CountingFailHandler()
    await _runner(tmp_path, store, resumed).resume(run.run_id)

    assert resumed.executions == 1, (
        f"resume spent {resumed.executions} attempts on an exhausted step — the budget reset"
    )


@pytest.mark.asyncio
async def test_a_partly_spent_budget_carries_the_remainder(tmp_path: Path) -> None:
    """The case that actually matters: an in-flight loop interrupted, then resumed.

    A step that has used one of three retries must have **two** left after a resume, not three.
    Asserted on the remainder rather than on exhaustion, because a fix that merely capped resumes
    at one attempt would pass the test above and fail this one.
    """
    store = StateStore(tmp_path / "flow.db")
    handler = CountingFailHandler()
    runner = _runner(tmp_path, store, handler)

    run = await runner.run()
    # Rewind to a mid-loop state: one retry spent, the run parked rather than failed.
    run.step_records[0].attempt = 2
    run.step_records[0].status = StepStatus.PENDING
    run.current_step = 0
    store.save_run(run)

    resumed = CountingFailHandler()
    await _runner(tmp_path, store, resumed).resume(run.run_id)

    assert resumed.executions == MAX_RETRIES, (
        f"one retry was already spent, so three attempts should remain of four; "
        f"got {resumed.executions}"
    )


@pytest.mark.asyncio
async def test_loop_back_records_the_budget_it_spends(tmp_path: Path) -> None:
    """`_handle_loop_back` spent the budget and never wrote `record.attempt`.

    Seeding from the persisted counter would therefore have fixed `retry` and left `loop_back`
    resetting — a fix that looks complete and is half done. This pins the write side directly at
    the gate, since the loop-back path needs a two-step pipeline to reach at all.
    """
    from specweaver.core.flow.engine.gates import GateEvaluator
    from specweaver.core.flow.engine.state import PipelineRun, StepRecord

    pipeline = PipelineDefinition(
        name="loop_pipe",
        steps=[
            PipelineStep(name="draft", action=StepAction.DRAFT, target=StepTarget.SPEC),
            PipelineStep(
                name="check",
                action=StepAction.VALIDATE,
                target=StepTarget.SPEC,
                gate=GateDefinition(
                    type=GateType.AUTO,
                    on_fail=OnFailAction.LOOP_BACK,
                    loop_target="draft",
                    max_retries=MAX_RETRIES,
                ),
            ),
        ],
    )
    run = PipelineRun(
        run_id="r1",
        pipeline_name="loop_pipe",
        project_name="p",
        spec_path="s.md",
        current_step=1,
        step_records=[StepRecord(step_name="draft"), StepRecord(step_name="check")],
        started_at="t",
        updated_at="t",
    )
    failure = StepResult(
        status=StepStatus.FAILED,
        error_message="nope",
        started_at="t",
        completed_at="t",
    )

    verdict = GateEvaluator(pipeline).evaluate(
        pipeline.steps[1].gate, failure, pipeline.steps[1], run, {}
    )

    assert verdict == "loop_back"
    assert run.step_records[1].attempt == 2, (
        "loop_back spent a retry without recording it, so the spend cannot survive a resume"
    )
