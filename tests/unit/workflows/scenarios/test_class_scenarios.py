# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A scenario may name a class's method: the test builds the object, then calls the method.

Proves: B-FLOW-01 FR-4

The generated file is written beside a real module and its tests are run.

| Bucket | Case |
|---|---|
| Happy | `Greeter.greet` with constructor values: the test builds `Greeter`, calls `greet`, asserts |
| Boundary | a group of several scenarios carries each scenario's own constructor values |
| Degradation | a wrong method makes the generated test fail |
| Hostile | a lowercase owner, three parts, or a non-identifier part is refused; other languages get no dot in a name |
"""

from __future__ import annotations

import importlib
import importlib.util
from typing import TYPE_CHECKING, Any

import pytest

from specweaver.workflows.scenarios.scenario_converter import ScenarioConverter
from specweaver.workflows.scenarios.scenario_models import ScenarioDefinition, ScenarioSet

if TYPE_CHECKING:
    from pathlib import Path

_GREETER = """
class Greeter:
    def __init__(self, greeting):
        self.greeting = greeting

    def greet(self, name):
        return f"{self.greeting}, {name}"
"""


def _scenario(name: str, greeting: str, who: str, expected: str) -> ScenarioDefinition:
    return ScenarioDefinition(
        name=name,
        description="greets",
        function_under_test="Greeter.greet",
        req_id="FR-1",
        constructor_inputs={"greeting": greeting},
        inputs={"name": who},
        expected_output=expected,
    )


def _set(*scenarios: ScenarioDefinition) -> ScenarioSet:
    return ScenarioSet(
        spec_path="specs/greet_spec.md",
        contract_path="contracts/greet_contract.py",
        scenarios=list(scenarios),
    )


def _run(tmp_path: Path, source: str, scenario_set: ScenarioSet) -> int:
    """Write the module and the generated tests, run every test; return how many ran."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "greet.py").write_text(source)
    generated = tmp_path / "scenarios" / "generated" / "test_greet_scenarios.py"
    generated.parent.mkdir(parents=True)
    generated.write_text(ScenarioConverter.convert(scenario_set, stem="greet"))
    spec = importlib.util.spec_from_file_location("_generated", generated)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ran = 0
    for name in dir(module):
        test: Any = getattr(module, name)
        if not name.startswith("test_"):
            continue
        marks = [m for m in getattr(test, "pytestmark", []) if m.name == "parametrize"]
        rows = [p.values for p in marks[0].args[1]] if marks else [()]
        for row in rows:
            test(*row)
            ran += 1
    return ran


def test_a_method_runs_on_a_built_object(tmp_path: Path) -> None:
    ran = _run(tmp_path, _GREETER, _set(_scenario("hi", "Hi", "Ann", "Hi, Ann")))

    assert ran == 1


def test_each_scenario_in_a_group_keeps_its_constructor_values(tmp_path: Path) -> None:
    scenarios = _set(
        _scenario("hi", "Hi", "Ann", "Hi, Ann"), _scenario("hey", "Hey", "Bo", "Hey, Bo")
    )

    assert _run(tmp_path, _GREETER, scenarios) == 2


def test_a_wrong_method_fails_the_test(tmp_path: Path) -> None:
    wrong = _GREETER.replace('f"{self.greeting}, {name}"', "name")

    with pytest.raises(AssertionError):
        _run(tmp_path, wrong, _set(_scenario("hi", "Hi", "Ann", "Hi, Ann")))


@pytest.mark.parametrize("name", ["os.system", "Greeter.greet.now", "Greeter.gr-eet", "Gre eter.x"])
def test_a_bad_dotted_name_is_refused(name: str) -> None:
    scenario = _scenario("hi", "Hi", "Ann", "Hi, Ann").model_copy(
        update={"function_under_test": name}
    )

    with pytest.raises(ValueError, match="identifier"):
        ScenarioConverter.convert(_set(scenario), stem="greet")


@pytest.mark.parametrize("language", ["java", "kotlin", "rust"])
def test_other_languages_keep_names_free_of_dots(language: str) -> None:
    module = importlib.import_module(
        f"specweaver.sandbox.language.core.{language}.scenario_converter"
    )
    converter = next(
        getattr(module, n) for n in dir(module) if n.endswith("ScenarioConverter") and n[0] != "_"
    )

    text = converter().convert(_set(_scenario("hi", "Hi", "Ann", "Hi, Ann")))

    assert "greeter.greet" not in text.lower()
    assert "greet" in text.lower()
