# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The implement pipeline is one bundled pipeline, `implement_spec`: generation piped into QA.

Proves: TECH-078 FR-4

generate_code -> generate_tests -> lint_fix -> run_tests -> validate_code -> acceptance, with a
loop-back gate on run_tests and report-only gates on lint_fix, validate_code and acceptance. No
step names a file: each finds the task's own (TECH-078 FR-1).
"""

from __future__ import annotations

import pytest

from specweaver.core.flow.engine.models import (
    GateCondition,
    GateType,
    OnFailAction,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.parser import list_bundled_pipelines, load_bundled_pipeline


@pytest.fixture(scope="module")
def pipe():
    return load_bundled_pipeline("implement_spec")


def test_it_is_a_bundled_pipeline() -> None:
    assert "implement_spec" in list_bundled_pipelines()


def test_pipeline_has_six_steps_in_order(pipe) -> None:
    assert [s.name for s in pipe.steps] == [
        "generate_code",
        "generate_tests",
        "lint_fix",
        "run_tests",
        "validate_code",
        "acceptance",
    ]


def test_generate_steps(pipe) -> None:
    gen_code, gen_tests = pipe.steps[0], pipe.steps[1]
    assert (gen_code.action, gen_code.target) == (StepAction.GENERATE, StepTarget.CODE)
    assert (gen_tests.action, gen_tests.target) == (StepAction.GENERATE, StepTarget.TESTS)


def test_lint_fix_is_report_only_with_three_reflections(pipe) -> None:
    lf = pipe.get_step("lint_fix")
    assert (lf.action, lf.target) == (StepAction.LINT_FIX, StepTarget.CODE)
    assert lf.params["max_reflections"] == 3
    assert lf.gate is not None and lf.gate.on_fail == OnFailAction.CONTINUE


def test_run_tests_runs_unit_tests_with_coverage(pipe) -> None:
    run_tests = pipe.get_step("run_tests")
    assert (run_tests.action, run_tests.target) == (StepAction.VALIDATE, StepTarget.TESTS)
    assert run_tests.params["kind"] == "unit"
    assert run_tests.params["coverage"] is True


def test_run_tests_loops_back_twice_at_most(pipe) -> None:
    gate = pipe.get_step("run_tests").gate
    assert gate is not None
    assert gate.type == GateType.AUTO
    assert gate.condition == GateCondition.ALL_PASSED
    assert gate.on_fail == OnFailAction.LOOP_BACK
    assert gate.loop_target == "generate_code"
    assert gate.max_retries == 2


def test_validate_code_and_acceptance_are_report_only(pipe) -> None:
    vc, acceptance = pipe.get_step("validate_code"), pipe.get_step("acceptance")
    assert (vc.action, vc.target) == (StepAction.VALIDATE, StepTarget.CODE)
    assert vc.gate is not None and vc.gate.on_fail == OnFailAction.CONTINUE
    assert acceptance.params["kind"] == "acceptance"
    assert acceptance.gate is not None and acceptance.gate.on_fail == OnFailAction.CONTINUE


def test_no_step_names_a_file(pipe) -> None:
    assert all("target" not in step.params for step in pipe.steps)


def test_qa_steps_defer_to_isolation_policy(pipe) -> None:
    assert pipe.get_step("run_tests").use_worktree is None
    assert pipe.get_step("validate_code").use_worktree is None
