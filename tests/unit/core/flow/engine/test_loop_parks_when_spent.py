# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A loop that has spent its rounds asks the person instead of failing, when its gate says so.

Proves: B-FLOW-01 NFR-5

The real runner, gate and store on a two-step loop: `make` always passes, `check` always fails.

| Bucket | Case |
|---|---|
| Happy | `on_exhausted: park`: 2 rounds, the 3rd failure parks the run |
| Boundary | the default, `stop`, still fails the run |
| Degradation | a resume gives 2 new rounds, then parks again; it never approves the failure |
| Hostile | an unknown `on_exhausted` value is refused when the pipeline is read |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

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
from specweaver.core.flow.engine.state import RunStatus, StepResult, StepStatus
from specweaver.core.flow.engine.store import StateStore
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.handlers.run_context import RunContext

if TYPE_CHECKING:
    from pathlib import Path


class _Counting:
    def __init__(self, status: StepStatus) -> None:
        self.status = status
        self.runs = 0

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        self.runs += 1
        return StepResult(
            status=self.status,
            error_message="" if self.status is StepStatus.PASSED else "wrong",
            started_at="",
            completed_at="",
        )


def _pipeline(**exhausted: str) -> PipelineDefinition:
    gate = GateDefinition(
        type=GateType.AUTO,
        on_fail=OnFailAction.LOOP_BACK,
        loop_target="make",
        max_retries=2,
        **exhausted,
    )
    return PipelineDefinition(
        name="loop",
        steps=[
            PipelineStep(name="make", action=StepAction.GENERATE, target=StepTarget.CODE),
            PipelineStep(
                name="check", action=StepAction.VALIDATE, target=StepTarget.TESTS, gate=gate
            ),
        ],
    )


def _runner(
    tmp_path: Path, store: StateStore, check: _Counting, **exhausted: str
) -> PipelineRunner:
    registry = StepHandlerRegistry()
    registry.register(StepAction.GENERATE, StepTarget.CODE, _Counting(StepStatus.PASSED))
    registry.register(StepAction.VALIDATE, StepTarget.TESTS, check)
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "specs" / "x_spec.md")
    return PipelineRunner(_pipeline(**exhausted), context, registry=registry, store=store)


@pytest.mark.asyncio
async def test_a_spent_loop_parks_for_the_person(tmp_path: Path) -> None:
    check = _Counting(StepStatus.FAILED)

    run = await _runner(
        tmp_path, StateStore(tmp_path / "flow.db"), check, on_exhausted="park"
    ).run()

    assert run.status == RunStatus.PARKED
    assert check.runs == 3


@pytest.mark.asyncio
async def test_the_default_still_fails(tmp_path: Path) -> None:
    check = _Counting(StepStatus.FAILED)

    run = await _runner(tmp_path, StateStore(tmp_path / "flow.db"), check).run()

    assert run.status == RunStatus.FAILED
    assert check.runs == 3


@pytest.mark.asyncio
async def test_a_resume_gives_two_new_rounds_then_parks_again(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "flow.db")
    run = await _runner(tmp_path, store, _Counting(StepStatus.FAILED), on_exhausted="park").run()
    again = _Counting(StepStatus.FAILED)

    resumed = await _runner(tmp_path, store, again, on_exhausted="park").resume(run.run_id)

    assert resumed.status == RunStatus.PARKED
    assert again.runs == 3


def test_an_unknown_value_is_refused() -> None:
    with pytest.raises(ValidationError):
        GateDefinition(on_fail=OnFailAction.LOOP_BACK, loop_target="make", on_exhausted="explode")
