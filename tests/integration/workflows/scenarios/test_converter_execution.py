# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""INT-US-24 SF-03 A1: the emitted scenario tests EXECUTE — and can FAIL.

The unit tier pins the emitted text; this tier writes the converter's output
into a tmp project and runs REAL pytest (via QARunnerAtom) against a real
``src/{stem}.py`` — green variant, red variant (wrong implementation must
genuinely fail), and the hyphenated-stem loader case. Isolates the "generated
tests actually execute" seam from the CLI so e2e failures never require
bisecting the whole chain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom
from specweaver.workflows.scenarios.scenario_converter import ScenarioConverter
from specweaver.workflows.scenarios.scenario_models import ScenarioDefinition, ScenarioSet

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

CORRECT_IMPL = """\
def greet(name):
    return f"Hello {name}"


def farewell(name):
    if not name:
        raise ValueError("name required")
    return f"Bye {name}"
"""

# Business-wrong: greet drops the salutation (the US-24 disease).
WRONG_IMPL = CORRECT_IMPL.replace('return f"Hello {name}"', "return name")


def _scenario_set() -> ScenarioSet:
    return ScenarioSet(
        spec_path="specs/greet_spec.md",
        contract_path="contracts/greet_contract.py",
        scenarios=[
            ScenarioDefinition(
                name="greet_bob",
                description="greeting includes salutation",
                function_under_test="greet",
                req_id="FR-1",
                inputs={"name": "Bob"},
                expected_output="Hello Bob",
            ),
            ScenarioDefinition(
                name="greet_ada",
                description="greeting includes salutation",
                function_under_test="greet",
                req_id="FR-1",
                inputs={"name": "Ada"},
                expected_output="Hello Ada",
            ),
            ScenarioDefinition(
                name="farewell_empty_raises",
                description="empty name rejected",
                function_under_test="farewell",
                req_id="FR-2",
                category="error",
                inputs={"name": ""},
                expected_output=None,
            ),
        ],
    )


def _project_with(tmp_path: Path, impl: str, stem: str = "greet") -> Path:
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / f"{stem}.py").write_text(impl, encoding="utf-8")
    gen_dir = project / "scenarios" / "generated"
    gen_dir.mkdir(parents=True)
    content = ScenarioConverter.convert(_scenario_set(), stem=stem)
    (gen_dir / f"test_{stem}_scenarios.py".replace("-", "_")).write_text(content, encoding="utf-8")
    return project


def _run(project: Path, stem: str = "greet") -> dict:
    target = f"scenarios/generated/test_{stem}_scenarios.py".replace("-", "_")
    result = QARunnerAtom(cwd=project).run(
        {
            "intent": "run_tests",
            "target": target,
            "kind": "",  # scenario runs carry no pytest marker (SF-01 FR-3)
            "timeout": 120,
        }
    )
    return {"status": result.status.value, **result.exports}


def test_green_variant_all_scenarios_pass(tmp_path: Path) -> None:
    # [Happy] correct impl → parametrized rows + raise-asserting single all pass.
    project = _project_with(tmp_path, CORRECT_IMPL)
    out = _run(project)
    assert out["status"] == "SUCCESS"
    assert out["total"] == 3
    assert out["passed"] == 3


def test_red_variant_business_wrong_impl_fails(tmp_path: Path) -> None:
    # [Hostile] unit-green-but-business-wrong impl → BOTH greet rows fail; the
    # farewell raise-test still passes. The generated tests can genuinely fail.
    project = _project_with(tmp_path, WRONG_IMPL)
    out = _run(project)
    assert out["status"] == "FAILED"
    assert out["failed"] == 2
    assert out["passed"] == 1


def test_mixed_none_expected_row_smoke_passes(tmp_path: Path) -> None:
    # [Boundary] G-b: a None-expected row in an equality group smoke-calls and
    # passes when the call doesn't raise; the valued rows still assert.
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "greet.py").write_text(CORRECT_IMPL, encoding="utf-8")
    gen_dir = project / "scenarios" / "generated"
    gen_dir.mkdir(parents=True)
    scenario_set = ScenarioSet(
        spec_path="specs/greet_spec.md",
        contract_path="c",
        scenarios=[
            ScenarioDefinition(
                name="valued",
                description="asserts",
                function_under_test="greet",
                req_id="FR-1",
                inputs={"name": "Bob"},
                expected_output="Hello Bob",
            ),
            ScenarioDefinition(
                name="smoke",
                description="no expectation — must not raise",
                function_under_test="greet",
                req_id="FR-1",
                inputs={"name": "Ada"},
                expected_output=None,
            ),
        ],
    )
    content = ScenarioConverter.convert(scenario_set, stem="greet")
    (gen_dir / "test_greet_scenarios.py").write_text(content, encoding="utf-8")
    out = _run(project)
    assert out["status"] == "SUCCESS"
    assert out["passed"] == 2


def test_hyphenated_stem_loads_via_file_anchor(tmp_path: Path) -> None:
    # [Boundary] non-identifier stem (hyphenated spec) — the file-anchored
    # loader needs no importable module name.
    project = _project_with(tmp_path, CORRECT_IMPL, stem="greet-svc")
    out = _run(project, stem="greet-svc")
    assert out["status"] == "SUCCESS"
    assert out["passed"] == 3
