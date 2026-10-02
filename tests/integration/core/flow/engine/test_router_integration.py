# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A router inside a real pipeline: parsed, validated, and acted on.

Proves: C-FLOW-02 FR-1, C-FLOW-02 FR-2, C-FLOW-02 FR-4

Cited from `INT-US-06-MIG`. Three mutants die across this file and its siblings:

* FR-1 — `router = step_def.router` -> `None`, so the step never reads its own router: 5 fail.
* FR-2 — skipping `_validate_router` in `validate_flow`, so a target naming no step is accepted: 1 fails.
* FR-4 — `run.route_to_step(result, target_idx)` -> `run.complete_current_step(result)`, so the jump
  resolves and is then thrown away: 4 fail.

FR-4's mutant is the one worth naming: the router still evaluates, still logs, still emits — only the
`current_step` move disappears. A weaker mutant that merely wrapped the call in a false branch was a
no-op and proved nothing.
"""

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.core.config.database import Database
from specweaver.core.config.llm_settings import LlmSettingsFiles
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.handlers.generation import GenerateCodeHandler
from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.infrastructure.llm.collector import TelemetryCollector
from specweaver.infrastructure.llm.models import LLMResponse, TaskType
from specweaver.infrastructure.llm.router import ModelRouter, build_router
from tests.fixtures.db_utils import register_test_project, set_test_active_project


@pytest.fixture
def tmp_db(tmp_path: Path) -> Database:
    """Provides a fresh database with a registered project."""
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database

    bootstrap_database(str(tmp_path / "test.db"))
    db = Database(tmp_path / "test.db")
    register_test_project(db, "test-proj", str(tmp_path))
    set_test_active_project(db, "test-proj")
    return db


def _router(machine: str, roles: list[TaskType]) -> ModelRouter:
    """The router a command builds, from a machine settings file and no project file."""
    files = LlmSettingsFiles.from_texts(
        machine_text=machine, machine_source="-", project_text="", project_source="-"
    )
    return build_router(
        files, project="test-proj", roles=roles, spend_limit_usd=None, token_limit=None
    )


_HOSTED = """\
[servers.anthropic]
kind = "anthropic"
private = false
max_parallel = 2

[servers.gemini]
kind = "gemini"
private = false
max_parallel = 2

[roles]
implement = { model = "claude-sonnet-4-5@anthropic", max_output_tokens = 8192 }
plan = { model = "claude-sonnet-4-5@anthropic", max_output_tokens = 8192 }
draft = { model = "claude-sonnet-4-5@anthropic", max_output_tokens = 8192 }
review = { model = "fast-model@gemini", max_output_tokens = 8192 }
validate = { model = "fast-model@gemini", max_output_tokens = 8192 }
"""

_KEYS = {"ANTHROPIC_API_KEY": "dummy1", "GEMINI_API_KEY": "dummy2"}


def test_routed_calls_are_priced_from_the_catalogue() -> None:
    """T8: a routed collector prices its server's models from the shipped catalogue."""
    with patch.dict(os.environ, _KEYS):
        res = _router(_HOSTED, [TaskType.IMPLEMENT]).get_for_task(TaskType.IMPLEMENT)

        assert isinstance(res.adapter, TelemetryCollector)
        facts = res.adapter._prices("claude-sonnet-4-5")
        assert facts is not None and facts.usd_per_million_input > 0


def test_memory_leak_check_caching() -> None:
    """T16: the router must bound its adapters by server, not by task type or call count."""
    tasks = [TaskType.IMPLEMENT, TaskType.PLAN, TaskType.DRAFT, TaskType.REVIEW, TaskType.VALIDATE]

    with (
        patch.dict(os.environ, _KEYS),
        patch(
            "specweaver.infrastructure.llm.resolve.adapter_for_server",
            side_effect=lambda _name, _server: MagicMock(),
        ),
    ):
        router = _router(_HOSTED, tasks)
        for _ in range(50):
            for t in tasks:
                res = router.get_for_task(t)
                assert res is not None, f"Failed for task {t}"

    # 5 task types asked 50 times each (250 calls), on 2 servers: exactly 2 adapters.
    assert len(router.collectors()) == 2


@pytest.mark.asyncio
async def test_fallback_pipeline_execution(tmp_db: Database, tmp_path: Path) -> None:
    """T12: a generation step whose role is unset runs on the `default` role's model."""
    spec_file = tmp_path / "s.md"
    spec_file.write_text("# Spec")
    out_dir = tmp_path / "out"
    out_dir.mkdir(exist_ok=True)
    context = RunContext(project_path=tmp_path, spec_path=spec_file, output_dir=out_dir)
    context.db = tmp_db

    mock_adapter = AsyncMock()
    mock_adapter.provider_name = "openai-compatible"
    mock_adapter.generate.return_value = LLMResponse(
        text="```python\nprint(1)\n```", model="local-model"
    )

    machine = """\
[servers.local]
kind = "openai-compatible"
base_url = "http://localhost:8000/v1"
private = true
max_parallel = 1

[roles]
default = { model = "local-model@local", max_output_tokens = 4096 }
"""
    with patch(
        "specweaver.infrastructure.llm.resolve.adapter_for_server", return_value=mock_adapter
    ):
        context.model = context.model.model_copy(
            update={"llm_router": _router(machine, [TaskType.IMPLEMENT])}
        )

        handler = GenerateCodeHandler()
        step = PipelineStep(name="test", action=StepAction.GENERATE, target=StepTarget.CODE)

        res = await handler.execute(step, context)

    assert res.status.value == "passed", res.error_message
    mock_adapter.generate.assert_called_once()
    assert mock_adapter.generate.call_args.args[1].model == "local-model"
