# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Both sides of a dual run read one reviewed spec, unchanged while the run lasts.

Proves: B-FLOW-01 FR-15

A registered project with its real store; the real spec review with a scripted model; the real
dual handler with a recorded spawner; the real arbiter.

| Bucket | Case |
|---|---|
| Happy | an accepted review records the spec; the dual run starts; the coding side has no spec steps |
| Boundary | a denied review records nothing, so the dual run refuses |
| Degradation | a review of an unregistered project passes and records nothing |
| Hostile | the spec edited after its review: the dual run refuses, and the arbiter parks before any model call |
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import RunStatus, StepStatus
from specweaver.core.flow.handlers.arbiter import ArbitrateVerdictHandler
from specweaver.core.flow.handlers.dual_pipeline import ArbitrateDualPipelineHandler
from specweaver.core.flow.handlers.review import ReviewSpecHandler
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext, RunHandle
from specweaver.infrastructure.llm.models import LLMResponse
from tests.fixtures.db_utils import register_test_project
from tests.scripted_llm import FixedRouter

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_SPEC = "# Greet\n\n| FR-91 | greet |\n"


class _Model:
    model = "scripted-1"

    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.calls = 0

    async def generate(self, messages: Any, config: Any = None) -> LLMResponse:
        self.calls += 1
        return LLMResponse(text=self.answer, model=self.model)


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[RunContext, Path]:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    bootstrap_database(str(data / "specweaver.db"))
    db = Database(data / "specweaver.db")
    root = tmp_path / "greeter"
    (root / "specs").mkdir(parents=True)
    (root / "specs" / "greet_spec.md").write_text(_SPEC, encoding="utf-8")
    register_test_project(db, "greeter", str(root))
    context = RunContext(project_path=root, spec_path=root / "specs" / "greet_spec.md", db=db)
    return context, data / "projects" / "greeter" / "scenarios"


async def _review(context: RunContext, verdict: str) -> Any:
    context.model = ModelAccess(llm_router=FixedRouter(_Model(f"Looks fine.\nVERDICT: {verdict}")))
    step = PipelineStep(name="review_spec", action=StepAction.REVIEW, target=StepTarget.SPEC)
    return await ReviewSpecHandler().execute(step, context)


class _Spawner:
    def __init__(self) -> None:
        self.steps: dict[str, list[str]] = {}

    def spawn(self, pipeline: Any, feedback: Any = None, side: str | None = None) -> Any:
        self.steps[side or "?"] = [s.name for s in pipeline.steps]

        class _Done:
            async def run(self, parent_run_id: str | None = None) -> Any:
                class _Run:
                    status = RunStatus.COMPLETED
                    step_records: tuple[Any, ...] = ()

                return _Run()

        return _Done()


async def _dual(context: RunContext) -> tuple[Any, _Spawner]:
    spawner = _Spawner()
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
    ):
        return await ArbitrateDualPipelineHandler().execute(step, context), spawner


@pytest.mark.asyncio
async def test_a_reviewed_spec_starts_the_dual_run(world: tuple[RunContext, Path]) -> None:
    context, store = world

    reviewed = await _review(context, "ACCEPTED")
    result, spawner = await _dual(context)

    assert reviewed.status == StepStatus.PASSED
    record = json.loads((store / "reviewed" / "greet_spec.json").read_text(encoding="utf-8"))
    assert len(record["sha256"]) == 64
    assert result.status == StepStatus.PASSED
    assert {"draft_spec", "review_spec"}.isdisjoint(spawner.steps["coder"])
    assert "generate_code" in spawner.steps["coder"]


@pytest.mark.asyncio
async def test_a_denied_review_records_nothing(world: tuple[RunContext, Path]) -> None:
    context, store = world

    await _review(context, "DENIED")
    result, spawner = await _dual(context)

    assert not (store / "reviewed").exists()
    assert result.status == StepStatus.FAILED
    assert "sw review" in (result.error_message or "")
    assert spawner.steps == {}


@pytest.mark.asyncio
async def test_an_unregistered_project_review_records_nothing(tmp_path: Path) -> None:
    root = tmp_path / "loose"
    (root / "specs").mkdir(parents=True)
    (root / "specs" / "greet_spec.md").write_text(_SPEC, encoding="utf-8")
    context = RunContext(project_path=root, spec_path=root / "specs" / "greet_spec.md")

    result = await _review(context, "ACCEPTED")

    assert result.status == StepStatus.PASSED
    assert not list(tmp_path.rglob("reviewed"))


@pytest.mark.asyncio
async def test_a_spec_edited_after_its_review_is_refused(world: tuple[RunContext, Path]) -> None:
    context, _ = world
    await _review(context, "ACCEPTED")
    context.spec_path.write_text(_SPEC + "| FR-92 | farewell |\n", encoding="utf-8")

    result, spawner = await _dual(context)

    assert result.status == StepStatus.FAILED
    assert "changed" in (result.error_message or "") and "sw review" in (result.error_message or "")
    assert spawner.steps == {}


@pytest.mark.asyncio
async def test_the_arbiter_parks_on_a_spec_changed_mid_run(world: tuple[RunContext, Path]) -> None:
    context, _ = world
    await _review(context, "ACCEPTED")
    context.spec_path.write_text(_SPEC + "| FR-92 | farewell |\n", encoding="utf-8")
    judge = _Model(json.dumps({"verdict": "code_bug", "spec_clause": "FR-91"}))
    context.model = ModelAccess(llm_router=FixedRouter(judge))
    context.run = RunHandle(run_id="r", step_name="arbitrate_verdict")
    context.feedback = {
        "scenario_test_failures": {
            "total": 1,
            "passed": 0,
            "failed": 1,
            "errors": 0,
            "failures": [{"nodeid": "t::x", "message": "AssertionError", "stacktrace": ""}],
        }
    }
    step = PipelineStep(
        name="arbitrate_verdict", action=StepAction.ARBITRATE, target=StepTarget.VERDICT
    )

    result = await ArbitrateVerdictHandler().execute(step, context)

    assert result.status == StepStatus.WAITING_FOR_INPUT
    assert "sw review" in (result.error_message or "")
    assert judge.calls == 0
    assert "generate_code" not in context.feedback
