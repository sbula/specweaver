# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Each model call is stored with its server, its run's DAL and its step.

Proves: B-FLOW-07 FR-1, B-FLOW-07 FR-10

The seam: a pipeline step (`core.flow`) calls through `llm_for` and the router
(`infrastructure.llm`), and the call reaches the database with where it ran. Only HTTP is faked.

| Bucket | Case |
|---|---|
| Happy | a step's call is stored with server, DAL and step name |
| Boundary | two steps of one run store their own step names |
| Degradation | not applicable — an old database is proven by the migration test (CB-1) |
| Hostile | not applicable — the values come from the run, never from input |
"""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

import httpx2
import pytest

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.config.llm_settings import LlmSettingsFiles
from specweaver.core.flow.engine.models import PipelineDefinition
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import StepResult, StepStatus
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
max_parallel = 2

[roles]
default = { model = "qwen3-coder-next@gb10", max_output_tokens = 100 }

[brake]
hosted_spend_per_run = 10
tokens_per_run = 1000000
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
    "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
}


class _CallsOnce:
    async def execute(self, _step, context) -> StepResult:
        adapter, config = llm_for(context, TaskType.REVIEW)
        await adapter.generate([Message(role=Role.USER, content="hi")], config)
        return StepResult(status=StepStatus.PASSED, output={}, started_at="t0", completed_at="t1")


def _rows(path: Path) -> list[tuple]:
    with sqlite3.connect(path) as conn:
        return conn.execute(
            "SELECT server, dal_level, step_name FROM llm_usage_log ORDER BY id"
        ).fetchall()


async def test_each_call_records_server_dal_and_step(tmp_path: Path) -> None:
    db_path = tmp_path / "specweaver.db"
    bootstrap_database(str(db_path))
    db = Database(db_path)
    root = tmp_path / "proj"
    root.mkdir()
    register_test_project(db, "proj", str(root))
    files = LlmSettingsFiles.from_texts(
        machine_text=_MACHINE, machine_source="settings.toml", project_text="", project_source="-"
    )
    context = RunContext(
        project_path=root,
        spec_path=root / "a_spec.md",
        db=db,
        model=ModelAccess(llm_router=build_router(files, project="proj", roles=[TaskType.REVIEW])),
    )
    registry = StepHandlerRegistry()
    registry.register("review", "spec", _CallsOnce())
    registry.register("review", "code", _CallsOnce())
    pipeline = PipelineDefinition.model_validate_json(
        json.dumps(
            {
                "name": "p",
                "steps": [
                    {"name": "first", "action": "review", "target": "spec"},
                    {"name": "second", "action": "review", "target": "code"},
                ],
            }
        )
    )

    with fake_httpx2(lambda _request: httpx2.Response(200, json=_REPLY)):
        await PipelineRunner(pipeline, context, registry=registry).run()

    assert _rows(db_path) == [("gb10", "DAL_C", "first"), ("gb10", "DAL_C", "second")]
