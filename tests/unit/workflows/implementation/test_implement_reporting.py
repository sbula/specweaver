# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""INT-US-03 SF-01: direct branch coverage for `_report_implementation` (FR-7).

Exercises the reporting helper in isolation (rather than only transitively via the
CLI) to cover the coverage-absent, malformed-output, and failed-rule-listing branches.
"""

from __future__ import annotations

import io
from unittest.mock import MagicMock

from rich.console import Console

from specweaver.core.flow.engine.state import StepStatus
from specweaver.workflows.implementation.interfaces import cli as impl_cli


def _rec(name: str, status: StepStatus, output: dict | None, error: str = "") -> MagicMock:
    rec = MagicMock()
    rec.step_name = name
    rec.status = status
    if output is None:
        rec.result = None
    else:
        rec.result = MagicMock()
        rec.result.output = output
    rec.error_message = error
    return rec


def _capture_report(records: list) -> str:
    """Run _report_implementation with a StringIO-backed console and return its text."""
    sio = io.StringIO()
    run_state = MagicMock()
    run_state.step_records = records
    original = impl_cli._core.console
    impl_cli._core.console = Console(file=sio, width=200)
    try:
        impl_cli._report_implementation(run_state)
    finally:
        impl_cli._core.console = original
    return sio.getvalue()


# --- Boundary: coverage absent -------------------------------------------


def test_report_omits_coverage_when_pct_is_none() -> None:
    out = _capture_report([_rec("run_tests", StepStatus.PASSED, {"passed": 1, "failed": 0})])
    assert "1 passed" in out
    assert "0 failed" in out
    assert "coverage" not in out.lower()


def test_report_includes_coverage_when_present() -> None:
    out = _capture_report(
        [_rec("run_tests", StepStatus.PASSED, {"passed": 3, "failed": 0, "coverage_pct": 88})]
    )
    assert "3 passed" in out
    assert "88%" in out


def test_report_shows_zero_coverage_not_dropped() -> None:
    """[Boundary] coverage_pct == 0 is a real reading, not 'absent'. The helper uses
    ``is not None`` so a genuine 0% must still be printed (a naive ``if cov:`` would drop it)."""
    out = _capture_report(
        [_rec("run_tests", StepStatus.PASSED, {"passed": 1, "failed": 1, "coverage_pct": 0})]
    )
    assert "coverage 0%" in out


# --- Hostile: malformed / empty output -----------------------------------


def test_report_tolerates_malformed_and_none_output() -> None:
    """Missing keys and a None result must not raise — defaults are applied."""
    records = [
        _rec("run_tests", StepStatus.PASSED, {}),  # missing all keys
        _rec("validate_code", StepStatus.FAILED, None),  # result is None → out = {}
        _rec("generate_code", StepStatus.PASSED, {}),  # no generated_path → skipped line
    ]
    out = _capture_report(records)  # must not raise
    assert "0 passed" in out  # run_tests defaulted
    assert "0/0 rules passed" in out  # validate_code defaulted


# --- Boundary: failed-rule listing ---------------------------------------


def test_report_lists_only_failed_rule_ids() -> None:
    out = _capture_report(
        [
            _rec(
                "validate_code",
                StepStatus.FAILED,
                {
                    "passed": 6,
                    "failed": 2,
                    "total": 8,
                    "results": [
                        {"rule_id": "C04", "status": "FAIL"},
                        {"rule_id": "C05", "status": "fail"},  # case-insensitive
                        {"rule_id": "C01", "status": "PASS"},
                    ],
                },
            )
        ]
    )
    assert "6/8 rules passed" in out
    assert "C04" in out
    assert "C05" in out
    assert "C01" not in out  # passing rule is not listed among failures


# --- Boundary: the generic fallback branch (elif not passed) --------------


def test_report_prints_error_for_unknown_failed_step() -> None:
    """[Boundary] A step outside the known QA/generate set that FAILED hits the
    ``elif not passed`` fallback (cli.py:128) and surfaces its error_message."""
    out = _capture_report([_rec("mystery_step", StepStatus.FAILED, {}, error="boom happened")])
    assert "mystery_step" in out
    assert "boom happened" in out


def test_report_skips_unknown_passed_step_silently() -> None:
    """[Boundary] An unknown step that PASSED matches no branch and prints nothing."""
    out = _capture_report([_rec("mystery_step", StepStatus.PASSED, {})])
    assert out.strip() == ""


# --- lint_fix reporting (SF-02, FR-2) -------------------------------------


def test_report_lint_fix_auto_fixed_clean() -> None:
    out = _capture_report(
        [
            _rec(
                "lint_fix",
                StepStatus.PASSED,
                {"auto_fixed": True, "reflections_used": 0, "lint_errors_remaining": 0},
            )
        ]
    )
    assert "lint" in out.lower()
    assert "auto-fixed" in out
    assert "0 errors remaining" in out


def test_report_lint_fix_errors_remaining_after_reflections() -> None:
    out = _capture_report(
        [
            _rec(
                "lint_fix",
                StepStatus.FAILED,
                {"reflections_used": 2, "lint_errors_remaining": 3},
            )
        ]
    )
    assert "3 errors remaining" in out
    assert "2 reflection" in out


def test_report_lint_fix_tolerates_empty_output() -> None:
    out = _capture_report([_rec("lint_fix", StepStatus.PASSED, {})])  # must not raise
    assert "0 errors remaining" in out
