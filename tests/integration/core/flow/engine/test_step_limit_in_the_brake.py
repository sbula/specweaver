# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A step's call that would cross its step limit is refused like any limit; sub-runs keep their own.

Proves: B-FLOW-07 FR-6, B-FLOW-07 FR-7, B-FLOW-07 FR-9

The seam: the history (`infrastructure.llm` store) becomes a limit in the brake for a step the
runner (`core.flow`) runs. Real database; only HTTP is faked.

| Bucket | Case |
|---|---|
| Happy | a step whose call fits its step limit completes |
| Boundary | a step whose first call would cross it parks, naming `step_limits.review.<step>` |
| Degradation | without `[step_limits]` the same step completes |
| Hostile | two sub-runs with the same step each get their own limit |
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

import httpx2
import pytest

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.config.llm_settings import LlmSettingsFiles
from specweaver.core.flow.engine.models import PipelineDefinition
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus, StepResult, StepStatus
from specweaver.core.flow.handlers._llm import llm_for
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext
from specweaver.infrastructure.llm.models import Message, Role, TaskType
from specweaver.infrastructure.llm.router import build_router
from tests.fake_http import fake_httpx2
from tests.fixtures.db_utils import register_test_project

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 4

[roles]
default = {{ model = "m@gb10", max_output_tokens = {max_output} }}

[brake]
hosted_spend_per_run = 10
tokens_per_run = 1000000
agent_turns = 5
{step_limits}"""

_STEP_LIMITS = "\n[step_limits]\npercentile = 90\nmin_steps = 10\n"


def _reply(tokens: int) -> dict:
    return {
        "id": "c1",
        "object": "chat.completion",
        "created": 1,
        "model": "m",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
        ],
        "usage": {
            "prompt_tokens": tokens // 2,
            "completion_tokens": tokens // 2,
            "total_tokens": tokens,
        },
    }


class _Calls:
    async def execute(self, _step, context) -> StepResult:
        adapter, config = llm_for(context, TaskType.REVIEW)
        await adapter.generate([Message(role=Role.USER, content="hi")], config)
        return StepResult(status=StepStatus.PASSED, output={}, started_at="t0", completed_at="t1")


def _history(db: Database, tokens: int, steps: int = 10, step: str = "review_it") -> None:
    with db.connect() as conn:
        for n in range(steps):
            run = f"old-{n}"
            conn.execute(
                "INSERT INTO llm_usage_log (timestamp, project_name, task_type, model, provider, "
                "prompt_tokens, completion_tokens, total_tokens, estimated_cost, duration_ms, "
                "run_id, server, dal_level, step_name) VALUES (?, 'p', 'review', 'm', 'x', 0, 0, "
                "?, NULL, 1, ?, 'gb10', 'DAL_C', ?)",
                (f"2026-10-01T10:{n:02d}:00+00:00", tokens, run, step),
            )
            conn.execute(
                "INSERT INTO llm_step_outcome (run_id, step_name, outcome) VALUES (?, ?, 'passed')",
                (run, step),
            )


def _world(tmp_path: Path, *, max_output: int, step_limits: str = _STEP_LIMITS):
    db_path = tmp_path / "specweaver.db"
    bootstrap_database(str(db_path))
    db = Database(db_path)
    root = tmp_path / "proj"
    root.mkdir()
    register_test_project(db, "proj", str(root))
    files = LlmSettingsFiles.from_texts(
        machine_text=_MACHINE.format(max_output=max_output, step_limits=step_limits),
        machine_source="settings.toml",
        project_text="",
        project_source="-",
    )
    router = build_router(files, project="proj", roles=[TaskType.REVIEW], db=db)
    context = RunContext(
        project_path=root, spec_path=root / "a_spec.md", db=db, model=ModelAccess(llm_router=router)
    )
    registry = StepHandlerRegistry()
    registry.register("review", "spec", _Calls())
    return db, context, registry


def _pipeline(name: str = "p") -> PipelineDefinition:
    return PipelineDefinition.model_validate_json(
        json.dumps(
            {"name": name, "steps": [{"name": "review_it", "action": "review", "target": "spec"}]}
        )
    )


async def test_a_call_within_the_step_limit_completes(tmp_path: Path) -> None:
    db, context, registry = _world(tmp_path, max_output=100)
    _history(db, tokens=1000)

    with fake_httpx2(lambda _request: httpx2.Response(200, json=_reply(20))):
        run = await PipelineRunner(_pipeline(), context, registry=registry).run()

    assert run.status is RunStatus.COMPLETED


async def test_a_call_that_would_cross_parks_naming_the_step_limit(tmp_path: Path) -> None:
    db, context, registry = _world(tmp_path, max_output=100)
    _history(db, tokens=50)

    with fake_httpx2(lambda _request: httpx2.Response(200, json=_reply(20))) as seen:
        run = await PipelineRunner(_pipeline(), context, registry=registry).run()

    assert seen == []
    assert run.status is RunStatus.PARKED
    assert "step_limits.review.review_it" in (run.step_records[0].result.error_message or "")


async def test_without_step_limits_the_step_completes(tmp_path: Path) -> None:
    db, context, registry = _world(tmp_path, max_output=100, step_limits="")
    _history(db, tokens=50)

    with fake_httpx2(lambda _request: httpx2.Response(200, json=_reply(20))):
        run = await PipelineRunner(_pipeline(), context, registry=registry).run()

    assert run.status is RunStatus.COMPLETED


async def test_sub_runs_with_the_same_step_keep_their_own_limit(tmp_path: Path) -> None:
    db, context, registry = _world(tmp_path, max_output=500)
    _history(db, tokens=1000)

    def sub() -> PipelineRunner:
        return PipelineRunner(_pipeline(), context, registry=registry)

    with fake_httpx2(lambda _request: httpx2.Response(200, json=_reply(600))):
        first, second = await asyncio.gather(
            sub().run(parent_run_id="parent"), sub().run(parent_run_id="parent")
        )

    assert (first.status, second.status) == (RunStatus.COMPLETED, RunStatus.COMPLETED)


class _CallsTwice:
    async def execute(self, _step, context) -> StepResult:
        for _ in range(2):
            adapter, config = llm_for(context, TaskType.REVIEW)
            await adapter.generate([Message(role=Role.USER, content="hi")], config)
        return StepResult(status=StepStatus.PASSED, output={}, started_at="t0", completed_at="t1")


async def test_the_history_is_read_once_per_run_and_group(tmp_path: Path) -> None:
    from unittest.mock import patch

    from specweaver.infrastructure.llm import resolve

    db, context, registry = _world(tmp_path, max_output=10)
    _history(db, tokens=1000)
    registry.register("review", "spec", _CallsTwice())

    with (
        patch.object(resolve, "step_history_limit", wraps=resolve.step_history_limit) as read,
        fake_httpx2(lambda _request: httpx2.Response(200, json=_reply(20))),
    ):
        await PipelineRunner(_pipeline(), context, registry=registry).run()

    assert read.call_count == 1
