# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""INT-US-03 SF-01 (T2): the `sw implement` pipeline pipes generation into QA.

`_build_implement_pipeline(stem)` returns the 4-step autonomous loop:
generate_code -> generate_tests -> run_tests -> validate_code, with a loop-back
gate on run_tests and a report-only (continue) gate on validate_code, targeting
this run's freshly generated files.
"""

from __future__ import annotations

from specweaver.core.flow.engine.models import (
    GateCondition,
    GateType,
    OnFailAction,
    StepAction,
    StepTarget,
)
from specweaver.workflows.implementation.interfaces.cli import _build_implement_pipeline

# --- Happy path -----------------------------------------------------------


def test_pipeline_has_five_steps_in_order() -> None:
    pipe = _build_implement_pipeline("greeter")
    assert [s.name for s in pipe.steps] == [
        "generate_code",
        "generate_tests",
        "lint_fix",
        "run_tests",
        "validate_code",
    ]


def test_lint_fix_runs_before_run_tests() -> None:
    """SF-02 (Q2): lint_fix precedes run_tests so tests + C01-C08 validate the fixed code."""
    pipe = _build_implement_pipeline("greeter")
    names = [s.name for s in pipe.steps]
    assert names.index("lint_fix") < names.index("run_tests")


def test_lint_fix_targets_generated_code_report_only() -> None:
    pipe = _build_implement_pipeline("greeter")
    lf = pipe.get_step("lint_fix")
    assert (lf.action, lf.target) == (StepAction.LINT_FIX, StepTarget.CODE)
    assert lf.params["target"] == "src/greeter.py"
    assert lf.params["max_reflections"] == 3
    assert lf.gate is not None
    assert lf.gate.on_fail == OnFailAction.CONTINUE


def test_generate_steps_unchanged() -> None:
    pipe = _build_implement_pipeline("greeter")
    gen_code, gen_tests = pipe.steps[0], pipe.steps[1]
    assert (gen_code.action, gen_code.target) == (StepAction.GENERATE, StepTarget.CODE)
    assert (gen_tests.action, gen_tests.target) == (StepAction.GENERATE, StepTarget.TESTS)


def test_run_tests_targets_generated_test_file_with_coverage() -> None:
    pipe = _build_implement_pipeline("greeter")
    run_tests = pipe.get_step("run_tests")
    assert (run_tests.action, run_tests.target) == (StepAction.VALIDATE, StepTarget.TESTS)
    assert run_tests.params["target"] == "tests/test_greeter.py"
    assert run_tests.params["kind"] == "unit"
    assert run_tests.params["coverage"] is True


def test_run_tests_has_loopback_gate() -> None:
    pipe = _build_implement_pipeline("greeter")
    gate = pipe.get_step("run_tests").gate
    assert gate is not None
    assert gate.type == GateType.AUTO
    assert gate.condition == GateCondition.ALL_PASSED
    assert gate.on_fail == OnFailAction.LOOP_BACK
    assert gate.loop_target == "generate_code"
    assert gate.max_retries == 2


def test_validate_code_targets_generated_code_report_only() -> None:
    pipe = _build_implement_pipeline("greeter")
    vc = pipe.get_step("validate_code")
    assert (vc.action, vc.target) == (StepAction.VALIDATE, StepTarget.CODE)
    assert vc.params["target"] == "src/greeter.py"
    # Report-only: a C01-C08 miss must not abort an otherwise-passing run.
    assert vc.gate is not None
    assert vc.gate.on_fail == OnFailAction.CONTINUE


# --- Boundary -------------------------------------------------------------


def test_stem_with_underscores_interpolates_targets() -> None:
    pipe = _build_implement_pipeline("auth_service")
    assert pipe.get_step("run_tests").params["target"] == "tests/test_auth_service.py"
    assert pipe.get_step("validate_code").params["target"] == "src/auth_service.py"


def test_qa_steps_defer_to_isolation_policy() -> None:
    """SF-01 is host-mode: QA steps leave use_worktree unset (None) so SF-03 can
    later thread the US-9 policy without changing this pipeline."""
    pipe = _build_implement_pipeline("greeter")
    assert pipe.get_step("run_tests").use_worktree is None
    assert pipe.get_step("validate_code").use_worktree is None
