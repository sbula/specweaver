# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Only scenarios that match the spec and its contract are stored; both sides read one contract.

Proves: B-FLOW-01 FR-3
Proves: B-FLOW-01 FR-6

A registered project with its real store; the real scenario step with a scripted model; the real
pipeline files; the real dual handler and the real runner's spawn.

| Bucket | Case |
|---|---|
| Happy | a refused answer is retried, and only the matching set is stored |
| Boundary | the step names the contract's methods and gives the earlier set, when the store has one |
| Degradation | three refused answers: the step fails and stores nothing |
| Hostile | the coder's pipeline never makes a second contract; both sides read the parent's |
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.flow.engine.models import (
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus, StepStatus
from specweaver.core.flow.handlers.dual_pipeline import ArbitrateDualPipelineHandler
from specweaver.core.flow.handlers.run_context import (
    GraphContext,
    ModelAccess,
    RunContext,
    RunHandle,
)
from specweaver.core.flow.handlers.scenario import GenerateScenarioHandler
from tests.fixtures.db_utils import register_test_project
from tests.scripted_llm import FixedRouter

if TYPE_CHECKING:
    from pathlib import Path


def _model_without_tools() -> AsyncMock:
    """A model double that has `generate` only: no tool use, so the plain prompt path runs."""
    llm = AsyncMock(spec=["generate"])
    llm.generate = AsyncMock()
    return llm


pytestmark = pytest.mark.integration

_SPEC = '''# Greet

## Functional Requirements

| FR-91 | greet |
| FR-92 | farewell |

## 2. Contract

```python
class Greeter:
    def __init__(self, greeting: str) -> None:
        """Keep it."""

    def greet(self, name: str) -> str:
        """Greet."""

def farewell(name: str) -> str:
    """Bye."""
```
'''


def _answer(req: str) -> str:
    scenarios = [
        {
            "name": "a",
            "description": "d",
            "function_under_test": "Greeter.greet",
            "req_id": req,
            "constructor_inputs": {"greeting": "Hi"},
            "inputs": {"name": "Ann"},
        },
        {
            "name": "b",
            "description": "d",
            "function_under_test": "farewell",
            "req_id": "FR-92",
            "inputs": {"name": "Ann"},
        },
    ]
    return json.dumps({"spec_path": "s", "contract_path": "c", "scenarios": scenarios})


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[RunContext, Path, AsyncMock]:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    bootstrap_database(str(data / "specweaver.db"))
    db = Database(data / "specweaver.db")
    root = tmp_path / "greeter"
    (root / "specs").mkdir(parents=True)
    (root / "specs" / "greet_spec.md").write_text(_SPEC, encoding="utf-8")
    register_test_project(db, "greeter", str(root))
    llm = _model_without_tools()
    context = RunContext(
        project_path=root,
        spec_path=root / "specs" / "greet_spec.md",
        db=db,
        model=ModelAccess(llm_router=FixedRouter(llm), config=None),
    )
    return context, data / "projects" / "greeter" / "scenarios", llm


async def _step(context: RunContext) -> Any:
    step = PipelineStep(
        name="generate_scenarios", action=StepAction.GENERATE, target=StepTarget.SCENARIO
    )
    return await GenerateScenarioHandler().execute(step, context)


def _prompts(llm: AsyncMock) -> list[str]:
    return [str(call.args[0]) for call in llm.generate.call_args_list]


@pytest.mark.asyncio
async def test_only_the_matching_set_is_stored(world: tuple[RunContext, Path, AsyncMock]) -> None:
    context, store, llm = world
    llm.generate.side_effect = [_answer("FR-99"), _answer("FR-91")]

    result = await _step(context)

    assert result.status == StepStatus.PASSED
    stored = (store / "definitions" / "greet_scenarios.yaml").read_text(encoding="utf-8")
    assert "FR-99" not in stored and "FR-91" in stored
    assert "Greeter.greet" in _prompts(llm)[0] and "FR-99" in _prompts(llm)[1]


@pytest.mark.asyncio
async def test_the_earlier_set_comes_in_the_prompt(
    world: tuple[RunContext, Path, AsyncMock],
) -> None:
    context, store, llm = world
    (store / "definitions").mkdir(parents=True)
    (store / "definitions" / "greet_scenarios.yaml").write_text("earlier-set-4qz: true\n")
    llm.generate.side_effect = [_answer("FR-91")]

    await _step(context)

    assert "earlier-set-4qz" in _prompts(llm)[0]


@pytest.mark.asyncio
async def test_three_refusals_fail_and_store_nothing(
    world: tuple[RunContext, Path, AsyncMock],
) -> None:
    context, store, llm = world
    llm.generate.side_effect = [_answer("FR-99")] * 3

    result = await _step(context)

    assert result.status == StepStatus.ERROR
    assert "FR-99" in (result.error_message or "")
    assert not (store / "definitions" / "greet_scenarios.yaml").exists()


def _steps(name: str) -> list[tuple[str, str, str]]:
    from importlib.resources import files

    data = yaml.safe_load(files("specweaver.workflows.pipelines").joinpath(name).read_text())
    return [(s["name"], s["action"], s["target"]) for s in data["steps"]]


def test_the_contract_is_made_once_before_the_sides() -> None:
    assert _steps("scenario_validation.yaml") == [
        ("generate_scenarios", "generate", "scenario"),
        ("convert_to_pytest", "convert", "scenario"),
    ]
    parent = [name for name, _, _ in _steps("scenario_integration.yaml")]
    assert parent.index("generate_contract") < parent.index("run_dual_pipelines")
    assert ("generate", "contract") not in {(a, t) for _, a, t in _steps("new_feature.yaml")}


@pytest.mark.asyncio
async def test_both_sides_read_the_parents_contract(tmp_path: Path) -> None:
    contract = str(tmp_path / "contracts" / "greet_contract.py")
    context = RunContext(
        project_path=tmp_path,
        spec_path=tmp_path / "specs" / "greet_spec.md",
        graph=GraphContext(api_contract_paths=[contract]),
    )
    parent = PipelineRunner(PipelineDefinition(name="p", steps=[]), context)
    context.run = RunHandle(run_id="r", pipeline_runner=parent)
    seen: list[list[str] | None] = []

    async def _record(self: PipelineRunner, parent_run_id: str | None = None) -> Any:
        seen.append(self._context.graph.api_contract_paths)

        class _Run:
            status = RunStatus.COMPLETED

        return _Run()

    step = PipelineStep(
        name="run_dual_pipelines", action=StepAction.ORCHESTRATE, target=StepTarget.COMPONENTS
    )
    with (
        patch.object(PipelineRunner, "run", _record),
        patch.object(
            ArbitrateDualPipelineHandler, "container_available", staticmethod(lambda r: True)
        ),
        patch.object(
            ArbitrateDualPipelineHandler, "isolation_refusal", staticmethod(lambda c: None)
        ),
    ):
        result = await ArbitrateDualPipelineHandler().execute(step, context)

    assert result.status == StepStatus.PASSED
    assert seen == [[contract], [contract]]
