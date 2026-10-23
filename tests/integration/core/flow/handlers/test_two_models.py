# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The two sides of a dual run use different models where the settings allow it.

Proves: B-FLOW-01 FR-17

Real settings texts, the real role resolver and router, the real dual handler with a recorded
spawner, and the real end of `sw run`.

| Bucket | Case |
|---|---|
| Happy | `roles.implement` and `roles.scenario` name two models: the dual run starts |
| Boundary | the settings name one model: the run starts, warns, and the run summary says so |
| Degradation | a router that cannot name its models: the summary says the models are unknown |
| Hostile | two models named, but both sides resolve to one: refused, naming both keys; `--model` moves the coding side only |
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
import typer

from specweaver.core.config.llm_settings import RoleEntry
from specweaver.core.config.llm_settings_parse import LlmSettingsFiles
from specweaver.core.flow.engine.models import (
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.state import PipelineRun, RunStatus, StepRecord, StepStatus
from specweaver.core.flow.handlers._llm import roles_of
from specweaver.core.flow.handlers.dual_pipeline import ArbitrateDualPipelineHandler
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext, RunHandle
from specweaver.core.flow.interfaces import cli
from specweaver.infrastructure.llm.budget import SpendBudget
from specweaver.infrastructure.llm.catalogue import Catalogue
from specweaver.infrastructure.llm.models import TaskType
from specweaver.infrastructure.llm.resolve import RoleResolver
from specweaver.infrastructure.llm.router import ModelRouter
from tests.rendering import shows
from tests.scripted_llm import FixedRouter

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_SERVERS = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2

[brake]
hosted_spend_per_run = 1000
tokens_per_run = 100000000
agent_turns = 10
"""

_CATALOGUE = Catalogue.from_text(
    'schema_version = 1\n\n[models."openai-compatible/coder-a"]\nmax_output = 8192\n\n'
    '[models."openai-compatible/tester-b"]\nmax_output = 8192\n\n'
    '[models."openai-compatible/other-c"]\nmax_output = 8192\n'
)


def _router(roles: str, run_model: str | None = None) -> ModelRouter:
    files = LlmSettingsFiles.from_texts(
        machine_text=f"{_SERVERS}\n[roles]\n{roles}",
        machine_source="settings.toml",
        project_text="",
        project_source="specweaver.toml",
    )
    resolver = RoleResolver(
        files,
        telemetry_project="demo",
        budget=SpendBudget(),
        catalogue=_CATALOGUE,
        run_model=RoleEntry.model_validate(run_model) if run_model else None,
    )
    return ModelRouter(resolver)


class _Spawner:
    def __init__(self) -> None:
        self.sides: list[str] = []

    def spawn(self, pipeline: Any, feedback: Any = None, side: str | None = None) -> Any:
        self.sides.append(side or "?")

        class _Done:
            async def run(self, parent_run_id: str | None = None) -> Any:
                class _Run:
                    status = RunStatus.COMPLETED
                    step_records: tuple[Any, ...] = ()

                return _Run()

        return _Done()


async def _dual(tmp_path: Path, router: Any) -> tuple[Any, _Spawner]:
    spawner = _Spawner()
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "specs" / "greet_spec.md")
    context.model = ModelAccess(llm_router=router)
    context.run = RunHandle(run_id="r", pipeline_runner=spawner)
    step = PipelineStep(
        name="run_dual_pipelines", action=StepAction.ORCHESTRATE, target=StepTarget.COMPONENTS
    )
    with (
        patch.object(
            ArbitrateDualPipelineHandler, "container_available", staticmethod(lambda r: True)
        ),
        patch.object(
            ArbitrateDualPipelineHandler, "isolation_refusal", staticmethod(lambda c: None)
        ),
        patch.object(ArbitrateDualPipelineHandler, "review_refusal", staticmethod(lambda c: None)),
    ):
        return await ArbitrateDualPipelineHandler().execute(step, context), spawner


def _summary(result: Any, root: Path) -> str:
    run = PipelineRun.model_construct(
        status=RunStatus.COMPLETED,
        step_records=[
            StepRecord(step_name="run_dual_pipelines", status=StepStatus.PASSED, result=result)
        ],
    )
    with patch.object(cli._core, "console") as console, contextlib.suppress(typer.Exit):
        cli._finish_run(run, root, warn_on_console=False)
    return " ".join(str(call) for call in console.print.call_args_list)


@pytest.mark.asyncio
async def test_two_models_start_the_dual_run(tmp_path: Path) -> None:
    router = _router('implement = "coder-a@gb10"\nscenario = "tester-b@gb10"\n')

    result, spawner = await _dual(tmp_path, router)

    assert result.status == StepStatus.PASSED
    assert sorted(spawner.sides) == ["coder", "scenario"]
    assert "one model" not in _summary(result, tmp_path)


@pytest.mark.asyncio
async def test_one_model_for_both_is_refused_when_two_are_named(tmp_path: Path) -> None:
    router = _router('default = "coder-a@gb10"\nreview = "tester-b@gb10"\n')

    result, spawner = await _dual(tmp_path, router)

    assert result.status == StepStatus.FAILED
    assert "roles.implement" in (result.error_message or "")
    assert "roles.scenario" in (result.error_message or "")
    assert spawner.sides == []


@pytest.mark.asyncio
async def test_one_named_model_warns_and_the_summary_says_so(tmp_path: Path) -> None:
    result, spawner = await _dual(tmp_path, _router('default = "coder-a@gb10"\n'))

    assert result.status == StepStatus.PASSED
    assert len(spawner.sides) == 2
    assert shows(_summary(result, tmp_path), "Both sides used one model, coder-a")


@pytest.mark.asyncio
async def test_a_router_that_cannot_name_its_models_is_reported(tmp_path: Path) -> None:
    result, _ = await _dual(tmp_path, FixedRouter(object()))

    assert shows(_summary(result, tmp_path), "models of the two sides are unknown")


def test_the_model_flag_moves_the_coding_side_only() -> None:
    for roles in (
        'default = "coder-a@gb10"\nscenario = "tester-b@gb10"\n',
        'default = "coder-a@gb10"\n',
    ):
        router = _router(roles, run_model="other-c@gb10")
        kept = "tester-b" if "scenario" in roles else "coder-a"

        assert router.model_of(TaskType.IMPLEMENT) == "other-c"
        assert router.model_of(TaskType.SCENARIO) == kept


def test_the_settings_accept_the_scenario_role() -> None:
    assert (
        _router('scenario = "tester-b@gb10"\ndefault = "coder-a@gb10"\n').model_of(
            TaskType.SCENARIO
        )
        == "tester-b"
    )


def test_a_dual_run_checks_every_role_its_sides_use() -> None:
    from importlib.resources import files

    import yaml

    data = yaml.safe_load(
        files("specweaver.workflows.pipelines").joinpath("scenario_integration.yaml").read_text()
    )
    roles = roles_of(PipelineDefinition(**data))

    assert {TaskType.SCENARIO, TaskType.IMPLEMENT, TaskType.PLAN, TaskType.REVIEW} <= set(roles)
    assert TaskType.DRAFT not in roles  # the coding side drafts no spec in a dual run
