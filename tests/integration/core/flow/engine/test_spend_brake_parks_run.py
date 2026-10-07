# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A step whose call the spend brake stopped parks the run, whatever the step did with the stop.

Proves: B-FLOW-05 FR-3, B-FLOW-05 FR-7, B-FLOW-05 FR-8

The seam: the brake (`infrastructure.llm`) stops a call; the runner (`core.flow`) parks the run.
Settings file → router → real collector; only HTTP is faked.

| Bucket | Case |
|---|---|
| Happy | a step within its limits completes the run |
| Boundary | a step that lets the stop out parks the run instead of failing it |
| Degradation | a gate set to retry does not retry a stopped step; a resumed run keeps its totals; a stop in a step's own worktree parks and merges nothing |
| Hostile | a step that swallows the stop and reports success still parks the run, keeping what it found |
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import patch

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
        return StepResult(
            status=StepStatus.PASSED, output=_FOUND, started_at="t0", completed_at="t1"
        )


_FOUND = {"is_drifted": True}


def _pipeline(gate: dict | None = None, *, worktree: bool = False) -> PipelineDefinition:
    step = {"name": "review_it", "action": "review", "target": "spec", "use_worktree": worktree}
    if gate:
        step["gate"] = gate
    return PipelineDefinition.model_validate_json(json.dumps({"name": "brake", "steps": [step]}))


async def _run(
    tmp_path: Path,
    handler: _CallsTheModel,
    tokens: int,
    gate: dict | None = None,
    *,
    worktree: bool = False,
):
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
        pipeline = _pipeline(gate, worktree=worktree)
        return await PipelineRunner(pipeline, context, registry=registry).run()


async def test_a_step_within_its_limits_completes_the_run(tmp_path: Path) -> None:
    run = await _run(tmp_path, _CallsTheModel(swallow=False), tokens=1_000_000)

    assert run.status is RunStatus.COMPLETED


@pytest.mark.parametrize("swallow", [False, True])
async def test_a_stopped_step_parks_the_run(tmp_path: Path, swallow: bool) -> None:
    run = await _run(tmp_path, _CallsTheModel(swallow=swallow), tokens=50)

    assert run.status is RunStatus.PARKED
    assert "brake.tokens_per_run" in (run.step_records[0].result.error_message or "")


async def test_a_parked_step_keeps_what_it_found_before_the_stop(tmp_path: Path) -> None:
    run = await _run(tmp_path, _CallsTheModel(swallow=True), tokens=50)

    assert run.step_records[0].result.output == _FOUND


@pytest.mark.parametrize("swallow", [False, True])
async def test_a_stopped_step_in_its_own_worktree_parks_and_merges_nothing(
    tmp_path: Path, swallow: bool
) -> None:
    from specweaver.sandbox.base import AtomResult, AtomStatus

    intents: list[str] = []

    def git(_self, request: dict) -> AtomResult:
        intents.append(request["intent"])
        return AtomResult(status=AtomStatus.SUCCESS, message="", exports={})

    with patch("specweaver.sandbox.git.core.atom.GitAtom.run", autospec=True, side_effect=git):
        run = await _run(tmp_path, _CallsTheModel(swallow=swallow), tokens=50, worktree=True)

    assert run.status is RunStatus.PARKED
    assert "worktree_add" in intents
    assert "strip_merge" not in intents


async def test_a_retry_gate_does_not_retry_a_stopped_step(tmp_path: Path) -> None:
    handler = _CallsTheModel(swallow=False)
    gate = {"type": "auto", "condition": "all_passed", "on_fail": "retry", "max_retries": 3}

    run = await _run(tmp_path, handler, tokens=50, gate=gate)

    assert run.status is RunStatus.PARKED
    assert handler.calls == 1


_BIG_REPLY = {
    **_REPLY,
    "usage": {"prompt_tokens": 50, "completion_tokens": 50, "total_tokens": 100},
}


class _CallsTwice(_CallsTheModel):
    async def execute(self, _step, context) -> StepResult:
        self.calls += 1
        routed = context.model.llm_router.get_for_task(TaskType.REVIEW)
        for _ in range(2):
            await routed.adapter.generate([Message(role=Role.USER, content="hi")], routed.config)
        return StepResult(status=StepStatus.PASSED, output={}, started_at="t0", completed_at="t1")


async def test_a_resumed_run_continues_from_the_totals_it_parked_with(tmp_path: Path) -> None:
    from specweaver.core.flow.engine.store import StateStore

    store = StateStore(tmp_path / "state.db")

    def runner_for(handler):
        files = LlmSettingsFiles.from_texts(
            machine_text=_MACHINE.format(tokens=150),
            machine_source="settings.toml",
            project_text="",
            project_source="-",
        )
        context = RunContext(
            project_path=tmp_path,
            spec_path=tmp_path / "a_spec.md",
            model=ModelAccess(
                llm_router=build_router(files, project="demo", roles=[TaskType.REVIEW])
            ),
        )
        registry = StepHandlerRegistry()
        registry.register("review", "spec", handler)
        return PipelineRunner(_pipeline(), context, registry=registry, store=store)

    with fake_httpx2(lambda _request: httpx2.Response(200, json=_BIG_REPLY)) as first:
        parked = await runner_for(_CallsTwice(swallow=False)).run()
    assert parked.status is RunStatus.PARKED
    assert len(first) == 1  # the first call spent 100 of 150; the second could cross

    with fake_httpx2(lambda _request: httpx2.Response(200, json=_BIG_REPLY)) as resumed:
        again = await runner_for(_CallsTwice(swallow=False)).resume(parked.run_id)

    assert again.status is RunStatus.PARKED
    assert resumed == [], "the resumed run started from zero and spent past its limit"
