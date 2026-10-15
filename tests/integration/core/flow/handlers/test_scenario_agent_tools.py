# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The scenario agent reads the spec and the contracts, and nothing else; its problems reach the person.

Proves: B-FLOW-01 FR-5a

A registered project with its real store; the real scenario step, the real dispatcher and the
real file tools, driven by a scripted model that calls them; the real dual handler and the real
end of `sw run`.

| Bucket | Case |
|---|---|
| Happy | the agent reads `specs/` and `contracts/`; a problem it names is shown at the end of the run |
| Boundary | a model without tool use gets the plain prompt and still works |
| Degradation | a run with no problem shows no problem block |
| Hostile | reads of `src/`, `tests/` and the old `scenarios/` are refused; it has no write, git or code tool; its problems never reach `feedback` |
"""

from __future__ import annotations

import contextlib
import json
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
import typer

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import (
    PipelineRun,
    RunStatus,
    StepRecord,
    StepResult,
    StepStatus,
)
from specweaver.core.flow.handlers.dual_pipeline import ArbitrateDualPipelineHandler
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext, RunHandle
from specweaver.core.flow.handlers.scenario import GenerateScenarioHandler
from specweaver.core.flow.interfaces import cli
from specweaver.infrastructure.llm.models import LLMResponse
from specweaver.sandbox.git.interfaces import facades
from specweaver.sandbox.git.interfaces import tool as git_tool
from tests.fixtures.db_utils import register_test_project
from tests.rendering import shows
from tests.scripted_llm import FixedRouter

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_SPEC = '''# Greet

| FR-91 | farewell |

## 2. Contract

```python
def farewell(name: str) -> str:
    """Bye."""
```
'''

_PROBLEM = "FR-91 says nothing about an empty name"


def _answer(problems: list[str]) -> str:
    scenario = {
        "name": "b",
        "description": "d",
        "function_under_test": "farewell",
        "req_id": "FR-91",
        "inputs": {"name": "Ann"},
    }
    return json.dumps(
        {"spec_path": "s", "contract_path": "c", "scenarios": [scenario], "problems": problems}
    )


class _Agent:
    """A model that calls its tools before it answers."""

    model = "scripted-1"

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        self.reads: dict[str, dict[str, Any]] = {}
        self.tools: list[str] = []

    async def generate(self, messages: Any, config: Any = None) -> LLMResponse:
        return LLMResponse(text=_answer(self.problems), model=self.model)

    async def generate_with_tools(
        self, messages: Any, config: Any, dispatcher: Any, **_: Any
    ) -> LLMResponse:
        self.tools = [t.name for t in dispatcher.available_tools()]
        for path in (
            "specs/greet_spec.md",
            "contracts/greet_contract.py",
            "src/greet.py",
            "tests/test_greet.py",
            "scenarios/old.yaml",
        ):
            self.reads[path] = await dispatcher.execute("read_file", {"path": path})
        return LLMResponse(text=_answer(self.problems), model=self.model)


class _Plain:
    model = "scripted-1"

    async def generate(self, messages: Any, config: Any = None) -> LLMResponse:
        return LLMResponse(text=_answer([]), model=self.model)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Database]:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    bootstrap_database(str(data / "specweaver.db"))
    db = Database(data / "specweaver.db")
    root = tmp_path / "greeter"
    for folder, name, text in (
        ("specs", "greet_spec.md", _SPEC),
        ("contracts", "greet_contract.py", "class GreetProtocol: ...\n"),
        ("src", "greet.py", "SRC_SECRET = 1\n"),
        ("tests", "test_greet.py", "TEST_SECRET = 1\n"),
        ("scenarios", "old.yaml", "OLD_SECRET: 1\n"),
    ):
        (root / folder).mkdir(parents=True, exist_ok=True)
        (root / folder / name).write_text(text, encoding="utf-8")
    register_test_project(db, "greeter", str(root))
    return root, db


async def _step(root: Path, db: Database, llm: Any) -> tuple[StepResult, RunContext]:
    context = RunContext(
        project_path=root,
        spec_path=root / "specs" / "greet_spec.md",
        db=db,
        model=ModelAccess(llm_router=FixedRouter(llm), config=None),
    )
    step = PipelineStep(
        name="generate_scenarios", action=StepAction.GENERATE, target=StepTarget.SCENARIO
    )
    return await GenerateScenarioHandler().execute(step, context), context


@pytest.mark.asyncio
async def test_the_agent_reads_specs_and_contracts_only(project: tuple[Path, Database]) -> None:
    agent = _Agent([])

    result, _ = await _step(*project, agent)

    assert result.status == StepStatus.PASSED
    assert "Bye." in json.dumps(agent.reads["specs/greet_spec.md"])
    assert "GreetProtocol" in json.dumps(agent.reads["contracts/greet_contract.py"])
    for refused in ("src/greet.py", "tests/test_greet.py", "scenarios/old.yaml"):
        assert "error" in agent.reads[refused], refused
    assert "SECRET" not in json.dumps(agent.reads)
    assert set(agent.tools) == {"read_file", "list_directory", "grep", "find_files"}


def test_the_agent_has_no_git() -> None:
    assert "scenario_agent" not in git_tool.ROLE_INTENTS
    assert "scenario_agent" not in facades._ROLE_INTERFACE_MAP
    with pytest.raises(ValueError, match="scenario_agent"):
        git_tool.GitTool(MagicMock(), "scenario_agent")


@pytest.mark.asyncio
async def test_a_model_without_tools_gets_the_plain_prompt(project: tuple[Path, Database]) -> None:
    result, _ = await _step(*project, _Plain())

    assert result.status == StepStatus.PASSED


def _scenario_run(problems: list[str]) -> PipelineRun:
    output = {"generated_path": "x", "scenario_count": 1, "problems": problems}
    record = StepRecord(
        step_name="generate_scenarios",
        status=StepStatus.PASSED,
        result=StepResult(status=StepStatus.PASSED, output=output, started_at="", completed_at=""),
    )
    return PipelineRun.model_construct(status=RunStatus.COMPLETED, step_records=[record])


async def _dual(root: Path, problems: list[str]) -> tuple[StepResult, RunContext]:
    runs = {
        "coder": PipelineRun.model_construct(status=RunStatus.COMPLETED, step_records=[]),
        "scenario": _scenario_run(problems),
    }

    class _Spawner:
        def spawn(self, pipeline: Any, feedback: Any = None, side: str | None = None) -> Any:
            class _Side:
                async def run(self, parent_run_id: str | None = None) -> Any:
                    return runs[side or "coder"]

            return _Side()

    context = RunContext(project_path=root, spec_path=root / "specs" / "greet_spec.md")
    context.run = RunHandle(run_id="r", pipeline_runner=_Spawner())
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
        return await ArbitrateDualPipelineHandler().execute(step, context), context


def _shown(result: StepResult, root: Path) -> str:
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
async def test_a_problem_the_agent_names_reaches_the_person(project: tuple[Path, Database]) -> None:
    root, db = project
    agent_result, _ = await _step(root, db, _Agent([_PROBLEM]))
    assert agent_result.output["problems"] == [_PROBLEM]

    result, context = await _dual(root, agent_result.output["problems"])

    assert shows(_shown(result, root), _PROBLEM)
    assert _PROBLEM not in json.dumps(context.feedback, default=str)


@pytest.mark.asyncio
async def test_a_run_without_problems_shows_none(project: tuple[Path, Database]) -> None:
    root, _ = project
    result, _ = await _dual(root, [])

    assert "problem" not in _shown(result, root).lower()
