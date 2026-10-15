# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Each side of a dual run gets only its own feedback, once; nothing crosses between the sides.

Proves: B-FLOW-01 FR-5b

Before this, `spawn` handed every sub-run the parent's context and `run` copied it shallowly, so
both sides read and wrote one `feedback` dict: the scenario side's `scenario_test_path` sat where the
coder could read it, and an arbiter verdict was applied again on every later round.

| Bucket | Case |
|---|---|
| Happy | the coder gets its verdict entry, the scenario side its own |
| Boundary | the next round gets nothing; no verdict means both sides start empty |
| Degradation | a spawn without `feedback` (decompose) still shares the parent's dict |
| Hostile | parent-only keys never reach the coder; the scenario side's writes never reach it |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from specweaver.core.flow.engine.fan_out import isolate_sub_run_context
from specweaver.core.flow.engine.models import (
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus, StepStatus
from specweaver.core.flow.handlers.dual_pipeline import ArbitrateDualPipelineHandler
from specweaver.core.flow.handlers.run_context import RunContext, RunHandle

if TYPE_CHECKING:
    from pathlib import Path

_VERDICTS = {
    "generate_code": {"findings": {"x": "code verdict"}},
    "generate_scenarios": {"findings": {"y": "scenario verdict"}},
    "scenario_test_failures": {"failed": 1},
}


def _context(tmp_path: Path, feedback: dict[str, Any]) -> RunContext:
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "specs" / "greet_spec.md")
    context.feedback = dict(feedback)
    return context


def _pipeline() -> PipelineDefinition:
    return PipelineDefinition(
        name="p",
        steps=[PipelineStep(name="s", action=StepAction.VALIDATE, target=StepTarget.SPEC)],
    )


# --- the engine seam: spawn ------------------------------------------------------------------


def test_a_spawn_with_feedback_gets_its_own_dict(tmp_path: Path) -> None:
    parent = PipelineRunner(_pipeline(), _context(tmp_path, _VERDICTS))

    child = parent.spawn(_pipeline(), feedback={"generate_code": "x"})
    sub_run = isolate_sub_run_context(child._context, parent_run_id="parent")
    sub_run.feedback["scenario_test_path"] = "/somewhere"

    assert child._context.feedback == {"generate_code": "x", "scenario_test_path": "/somewhere"}
    assert parent._context.feedback == _VERDICTS


def test_a_spawn_without_feedback_still_shares(tmp_path: Path) -> None:
    parent = PipelineRunner(_pipeline(), _context(tmp_path, {}))

    child = parent.spawn(_pipeline())

    assert child._context.feedback is parent._context.feedback


# --- the dual handler ------------------------------------------------------------------------


class _Spawner:
    """The parent runner, recording what each side is handed."""

    def __init__(self) -> None:
        self.handed: list[dict[str, Any]] = []

    def spawn(
        self,
        pipeline: PipelineDefinition,
        feedback: dict[str, Any] | None = None,
        side: str | None = None,
    ) -> Any:
        self.handed.append(dict(feedback or {}))

        class _Done:
            async def run(self, parent_run_id: str | None = None) -> Any:
                class _Run:
                    status = RunStatus.COMPLETED

                return _Run()

        return _Done()


@pytest.fixture(autouse=True)
def _a_container_is_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ArbitrateDualPipelineHandler, "container_available", staticmethod(lambda root: True)
    )
    monkeypatch.setattr(
        ArbitrateDualPipelineHandler, "isolation_refusal", staticmethod(lambda context: None)
    )
    monkeypatch.setattr(
        ArbitrateDualPipelineHandler, "review_refusal", staticmethod(lambda context: None)
    )


async def _dual_round(context: RunContext, spawner: _Spawner) -> None:
    context.run = RunHandle(run_id="r", pipeline_runner=spawner)
    step = PipelineStep(
        name="run_dual_pipelines", action=StepAction.ORCHESTRATE, target=StepTarget.COMPONENTS
    )
    await ArbitrateDualPipelineHandler().execute(step, context)


@pytest.mark.asyncio
async def test_each_side_gets_only_its_own_entry(tmp_path: Path) -> None:
    context, spawner = _context(tmp_path, _VERDICTS), _Spawner()

    await _dual_round(context, spawner)

    coder, scenario = spawner.handed
    assert coder == {"generate_code": _VERDICTS["generate_code"]}
    assert scenario == {"generate_scenarios": _VERDICTS["generate_scenarios"]}


@pytest.mark.asyncio
async def test_a_verdict_reaches_its_side_once(tmp_path: Path) -> None:
    context, spawner = _context(tmp_path, _VERDICTS), _Spawner()

    await _dual_round(context, spawner)
    await _dual_round(context, spawner)

    assert spawner.handed[2:] == [{}, {}]
    assert "generate_code" not in context.feedback
    assert context.feedback["scenario_test_failures"] == {"failed": 1}


@pytest.mark.asyncio
async def test_no_verdict_means_both_sides_start_empty(tmp_path: Path) -> None:
    context, spawner = _context(tmp_path, {}), _Spawner()

    await _dual_round(context, spawner)

    assert spawner.handed == [{}, {}]


@pytest.mark.asyncio
async def test_a_dual_run_refuses_without_a_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Proves: B-FLOW-01 FR-18
    monkeypatch.setattr(
        ArbitrateDualPipelineHandler, "container_available", staticmethod(lambda root: False)
    )
    context, spawner = _context(tmp_path, {}), _Spawner()
    context.run = RunHandle(run_id="r", pipeline_runner=spawner)
    step = PipelineStep(
        name="run_dual_pipelines", action=StepAction.ORCHESTRATE, target=StepTarget.COMPONENTS
    )

    result = await ArbitrateDualPipelineHandler().execute(step, context)

    assert result.status == StepStatus.FAILED
    assert "container" in (result.error_message or "")
    assert spawner.handed == []


@pytest.mark.asyncio
async def test_the_run_holding_a_dual_run_is_marked(tmp_path: Path) -> None:
    # Proves: B-FLOW-01 FR-12
    context, spawner = _context(tmp_path, {}), _Spawner()

    await _dual_round(context, spawner)

    assert context.run.dual_side == "parent"
