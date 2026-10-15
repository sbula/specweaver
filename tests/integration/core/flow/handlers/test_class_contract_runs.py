# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A class in a spec's contract is named in the contract, and a scenario on it runs.

Proves: B-FLOW-01 FR-2
Proves: B-FLOW-01 FR-4

The real contract step on a real project; the names it reports go into scenarios, the real
converter writes the tests, and they run against a real module.

| Bucket | Case |
|---|---|
| Happy | the contract step names `Greeter.greet` and `farewell`; scenarios on both pass on a right module |
| Boundary | a spec with functions only names them as before |
| Degradation | a module whose method is wrong fails its scenario |
| Hostile | a spec whose contract has no `def` at all is refused |
"""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING, Any

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.generation import GenerateContractHandler
from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.workflows.scenarios.scenario_converter import ScenarioConverter
from specweaver.workflows.scenarios.scenario_models import ScenarioDefinition, ScenarioSet

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_SPEC = '''# Greet

## 2. Contract

```python
class Greeter:
    def __init__(self, greeting: str) -> None:
        """Keep the greeting."""

    def greet(self, name: str) -> str:
        """Return the greeting and the name."""

def farewell(name: str) -> str:
    """Return the farewell."""
```
'''

_MODULE = """
class Greeter:
    def __init__(self, greeting):
        self.greeting = greeting

    def greet(self, name):
        return f"{self.greeting}, {name}"


def farewell(name):
    return f"Bye, {name}"
"""


def _project(tmp_path: Path, spec: str) -> RunContext:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "greet"\n')
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "greet_spec.md").write_text(spec, encoding="utf-8")
    return RunContext(project_path=tmp_path, spec_path=tmp_path / "specs" / "greet_spec.md")


async def _contract(context: RunContext) -> Any:
    step = PipelineStep(
        name="generate_contract", action=StepAction.GENERATE, target=StepTarget.CONTRACT
    )
    return await GenerateContractHandler().execute(step, context)


def _scenarios(methods: list[str]) -> ScenarioSet:
    values = {
        "Greeter.greet": ({"greeting": "Hi"}, {"name": "Ann"}, "Hi, Ann"),
        "farewell": ({}, {"name": "Ann"}, "Bye, Ann"),
    }
    return ScenarioSet(
        spec_path="specs/greet_spec.md",
        contract_path="contracts/greet_contract.py",
        scenarios=[
            ScenarioDefinition(
                name=f"s_{i}",
                description="d",
                function_under_test=method,
                req_id="FR-1",
                constructor_inputs=values[method][0],
                inputs=values[method][1],
                expected_output=values[method][2],
            )
            for i, method in enumerate(methods)
        ],
    )


def _run_generated(root: Path, source: str, scenario_set: ScenarioSet) -> int:
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "greet.py").write_text(source)
    generated = root / "scenarios" / "generated" / "test_greet_scenarios.py"
    generated.parent.mkdir(parents=True, exist_ok=True)
    generated.write_text(ScenarioConverter.convert(scenario_set, stem="greet"))
    spec = importlib.util.spec_from_file_location("_generated_greet", generated)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tests = [getattr(module, n) for n in dir(module) if n.startswith("test_")]
    for test in tests:
        test()
    return len(tests)


@pytest.mark.asyncio
async def test_a_class_method_from_the_contract_runs(tmp_path: Path) -> None:
    context = _project(tmp_path, _SPEC)

    result = await _contract(context)

    assert result.status == StepStatus.PASSED
    methods = result.output["methods"]
    assert methods == ["Greeter.greet", "farewell"]
    assert _run_generated(tmp_path, _MODULE, _scenarios(methods)) == 2


@pytest.mark.asyncio
async def test_a_wrong_method_fails_its_scenario(tmp_path: Path) -> None:
    context = _project(tmp_path, _SPEC)
    methods = (await _contract(context)).output["methods"]
    wrong = _MODULE.replace('f"{self.greeting}, {name}"', "name")

    with pytest.raises(AssertionError):
        _run_generated(tmp_path, wrong, _scenarios(methods))


@pytest.mark.asyncio
async def test_functions_only_are_named_as_before(tmp_path: Path) -> None:
    spec = '# Greet\n\n## 2. Contract\n\n```python\ndef farewell(name: str) -> str:\n    """Bye."""\n```\n'

    result = await _contract(_project(tmp_path, spec))

    assert result.output["methods"] == ["farewell"]


@pytest.mark.asyncio
async def test_a_contract_with_no_def_is_refused(tmp_path: Path) -> None:
    spec = "# Greet\n\n## 2. Contract\n\n```python\nclass Greeter:\n    pass\n```\n"

    result = await _contract(_project(tmp_path, spec))

    assert result.status == StepStatus.ERROR
