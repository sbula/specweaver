# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""After a verdict only the side at fault runs again; on a first round both run, at the same time.

Proves: B-FLOW-01 FR-16
Proves: B-FLOW-01 FR-7

The real dual handler; its two sides are recorded.

| Bucket | Case |
|---|---|
| Happy | a code bug runs the coding side only; a scenario error runs the scenario side only |
| Boundary | no verdict: both sides run, and they overlap in time |
| Degradation | the handler returns only after the slower side has ended |
| Hostile | a verdict for both sides runs both, each with its own entry |
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import RunStatus, StepStatus
from specweaver.core.flow.handlers.dual_pipeline import ArbitrateDualPipelineHandler
from specweaver.core.flow.handlers.run_context import RunContext, RunHandle

if TYPE_CHECKING:
    from pathlib import Path

_STEP = PipelineStep(
    name="run_dual_pipelines", action=StepAction.ORCHESTRATE, target=StepTarget.COMPONENTS
)
_CODE = {"generate_code": {"findings": {"verdict": "code_bug"}}}
_SCENARIO = {"generate_scenarios": {"findings": {"verdict": "scenario_error"}}}


class _Spawner:
    def __init__(self, seconds: dict[str, float] | None = None) -> None:
        self.seconds = seconds or {}
        self.ran: dict[str, tuple[float, float]] = {}
        self.fed: dict[str, Any] = {}

    def spawn(self, pipeline: Any, feedback: Any = None, side: str | None = None) -> Any:
        spawner, name = self, side or "?"
        spawner.fed[name] = feedback

        class _Side:
            async def run(self, parent_run_id: str | None = None) -> Any:
                start = time.monotonic()
                await asyncio.sleep(spawner.seconds.get(name, 0))
                spawner.ran[name] = (start, time.monotonic())

                class _Run:
                    status = RunStatus.COMPLETED
                    step_records: tuple[Any, ...] = ()

                return _Run()

        return _Side()


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("container_available", "isolation_refusal", "review_refusal"):
        answer = True if name == "container_available" else None
        monkeypatch.setattr(ArbitrateDualPipelineHandler, name, staticmethod(lambda _, a=answer: a))


async def _dual(tmp_path: Path, feedback: dict[str, Any], spawner: _Spawner) -> Any:
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "specs" / "greet_spec.md")
    context.feedback = dict(feedback)
    context.run = RunHandle(run_id="r", pipeline_runner=spawner)
    return await ArbitrateDualPipelineHandler().execute(_STEP, context)


@pytest.mark.asyncio
@pytest.mark.parametrize(("feedback", "side"), [(_CODE, "coder"), (_SCENARIO, "scenario")])
async def test_only_the_side_at_fault_runs(tmp_path: Path, feedback: dict, side: str) -> None:
    spawner = _Spawner()

    result = await _dual(tmp_path, feedback, spawner)

    assert result.status == StepStatus.PASSED
    assert set(spawner.ran) == {side}


@pytest.mark.asyncio
async def test_a_verdict_for_both_runs_both(tmp_path: Path) -> None:
    spawner = _Spawner()

    await _dual(tmp_path, {**_CODE, **_SCENARIO}, spawner)

    assert set(spawner.ran) == {"coder", "scenario"}
    assert set(spawner.fed["coder"]) == {"generate_code"}
    assert set(spawner.fed["scenario"]) == {"generate_scenarios"}


@pytest.mark.asyncio
async def test_a_first_round_runs_both_at_the_same_time(tmp_path: Path) -> None:
    spawner = _Spawner({"coder": 0.05, "scenario": 0.15})

    result = await _dual(tmp_path, {}, spawner)
    ended = time.monotonic()

    assert result.status == StepStatus.PASSED
    (coder_start, coder_end), (scenario_start, scenario_end) = (
        spawner.ran["coder"],
        spawner.ran["scenario"],
    )
    assert scenario_start < coder_end and coder_start < scenario_end  # they overlap
    assert ended >= max(coder_end, scenario_end)
