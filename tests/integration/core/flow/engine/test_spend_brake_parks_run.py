# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A step whose call the spend brake stopped parks the run, whatever the step did with the stop.

Proves: B-FLOW-05 FR-3, B-FLOW-05 FR-7

The seam: the brake (`infrastructure.llm`) stops a call; the runner (`core.flow`) parks the run.
Settings file → router → real collector; only HTTP is faked.

| Bucket | Case |
|---|---|
| Happy | a step within its limits completes the run |
| Boundary | a step that lets the stop out parks the run instead of failing it |
| Degradation | a gate set to retry does not retry a stopped step |
| Hostile | a step that swallows the stop and reports success still parks the run |
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx2
import pytest

from specweaver.core.config.llm_settings import LlmSettingsFiles
from specweaver.core.flow.engine.models import PipelineDefinition
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus, StepResult, StepStatus
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext
from specweaver.infrastructure.llm.models import Message, Role, TaskType
from specweaver.infrastructure.llm.router import build_router
from tests.fake_http import fake_httpx2

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2

[roles]
default = {{ model = "qwen3-coder-next@gb10", max_output_tokens = 100 }}

[brake]
hosted_spend_per_run = 10
tokens_per_run = {tokens}
agent_turns = 5
"""

_REPLY = {
    "id": "c1",
    "object": "chat.completion",
    "created": 1,
    "model": "m",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
    ],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
}


class _CallsTheModel:
    """A step that calls the review model once; `swallow` hides any error like `drift` does."""

    def __init__(self, *, swallow: bool) -> None:
        self.calls = 0
        self._swallow = swallow

    async def execute(self, _step, context) -> StepResult:
        self.calls += 1
        routed = context.model.llm_router.get_for_task(TaskType.REVIEW)
        try:
            await routed.adapter.generate([Message(role=Role.USER, content="hi")], routed.config)
        except Exception:
            if not self._swallow:
                raise
        return StepResult(status=StepStatus.PASSED, output={}, started_at="t0", completed_at="t1")


def _pipeline(gate: dict | None = None) -> PipelineDefinition:
    step = {"name": "review_it", "action": "review", "target": "spec"}
    if gate:
        step["gate"] = gate
    return PipelineDefinition.model_validate_json(json.dumps({"name": "brake", "steps": [step]}))


async def _run(tmp_path: Path, handler: _CallsTheModel, tokens: int, gate: dict | None = None):
    files = LlmSettingsFiles.from_texts(
        machine_text=_MACHINE.format(tokens=tokens),
        machine_source="settings.toml",
        project_text="",
        project_source="-",
    )
    router = build_router(files, project="demo", roles=[TaskType.REVIEW])
    context = RunContext(
        project_path=tmp_path,
        spec_path=tmp_path / "a_spec.md",
        model=ModelAccess(llm_router=router),
    )
    registry = StepHandlerRegistry()
    registry.register("review", "spec", handler)
    with fake_httpx2(lambda _request: httpx2.Response(200, json=_REPLY)):
        return await PipelineRunner(_pipeline(gate), context, registry=registry).run()


async def test_a_step_within_its_limits_completes_the_run(tmp_path: Path) -> None:
    run = await _run(tmp_path, _CallsTheModel(swallow=False), tokens=1_000_000)

    assert run.status is RunStatus.COMPLETED


@pytest.mark.parametrize("swallow", [False, True])
async def test_a_stopped_step_parks_the_run(tmp_path: Path, swallow: bool) -> None:
    run = await _run(tmp_path, _CallsTheModel(swallow=swallow), tokens=50)

    assert run.status is RunStatus.PARKED
    assert "brake.tokens_per_run" in (run.step_records[0].result.error_message or "")


async def test_a_retry_gate_does_not_retry_a_stopped_step(tmp_path: Path) -> None:
    handler = _CallsTheModel(swallow=False)
    gate = {"type": "auto", "condition": "all_passed", "on_fail": "retry", "max_retries": 3}

    run = await _run(tmp_path, handler, tokens=50, gate=gate)

    assert run.status is RunStatus.PARKED
    assert handler.calls == 1
