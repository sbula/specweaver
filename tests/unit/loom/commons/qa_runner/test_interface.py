# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Unit tests for the QARunnerInterface data models."""

import pytest

from specweaver.loom.commons.qa_runner.interface import (
    CompileError,
    CompileRunResult,
    DebugRunResult,
    LintError,
    OutputEvent,
    QARunnerInterface,
    TestFailure,
)


def test_test_failure_model_supports_stacktrace_and_rule() -> None:
    """Test that TestFailure accepts stacktrace and rule_uri per the new SARIF/DAP standards."""
    failure = TestFailure(
        nodeid="test_foo.py::test_bar",
        message="AssertionError: out of bounds",
        stdout="Console log output",
        stacktrace="Traceback (most recent call last):\n  File 'test_foo.py', line 10",
        rule_uri="https://eslint.org/docs/rules/eqeqeq",
    )
    assert failure.nodeid == "test_foo.py::test_bar"
    assert failure.message == "AssertionError: out of bounds"
    assert failure.stacktrace.startswith("Traceback")
    assert failure.rule_uri == "https://eslint.org/docs/rules/eqeqeq"


def test_test_failure_default_values() -> None:
    """Test that TestFailure handles defaults gracefully for backward compatibility."""
    failure = TestFailure(
        nodeid="test_foo.py::test_bar",
        message="AssertionError",
    )
    assert failure.stacktrace == ""
    assert failure.rule_uri == ""
    assert failure.stdout == ""


def test_lint_error_model_supports_rule_uri() -> None:
    """Test that LintError accepts rule_uri per the new SARIF standards."""
    error = LintError(
        file="src/foo.py",
        line=10,
        code="E501",
        message="Line too long",
        rule_uri="https://docs.astral.sh/ruff/rules/line-too-long/",
    )
    assert error.code == "E501"
    assert error.rule_uri == "https://docs.astral.sh/ruff/rules/line-too-long/"


def test_lint_error_default_values() -> None:
    """Test that LintError handles defaults gracefully for backward compatibility."""
    error = LintError(
        file="src/foo.py",
        line=10,
        code="E501",
        message="Line too long",
    )
    assert error.rule_uri == ""


def test_compile_error_model() -> None:
    """Test CompileError structure supports SARIF lines/cols."""
    err = CompileError(
        file="src/main.rs",
        line=42,
        column=12,
        code="E0432",
        message="unresolved import",
        is_warning=False,
    )
    assert err.file == "src/main.rs"
    assert err.column == 12
    assert not err.is_warning


def test_compile_run_result_model() -> None:
    """Test CompileRunResult container."""
    res = CompileRunResult(
        error_count=1,
        warning_count=0,
        errors=[CompileError("main.ts", 1, 0, "TS1005", "expected ';'", False)],
    )
    assert res.error_count == 1
    assert len(res.errors) == 1


def test_output_event_model() -> None:
    """Test DAP-compliant OutputEvent mapping."""
    event = OutputEvent(
        category="stderr",
        output="Node process crashed",
        file="index.js",
        line=1,
    )
    assert event.category == "stderr"
    assert event.output == "Node process crashed"
    assert event.file == "index.js"
    assert event.line == 1


def test_debug_run_result_model() -> None:
    """Test DebugRunResult container."""
    res = DebugRunResult(exit_code=1, duration_seconds=1.5, events=[OutputEvent("stderr", "crash")])
    assert res.exit_code == 1
    assert len(res.events) == 1


def test_interface_demands_compile_and_debug() -> None:
    """Test that QARunnerInterface correctly defines run_compiler and run_debugger as abstract."""
    from typing import Any

    class IncompleteRunner(QARunnerInterface):
        # Only implementing the old ones
        def run_tests(
            self, target: str, kind: str = "unit", scope: str = "", timeout: int = 120, coverage: bool = False, coverage_threshold: int = 70
        ) -> Any:
            raise NotImplementedError

        def run_linter(self, target: str, fix: bool = False) -> Any:
            raise NotImplementedError

        def run_complexity(self, target: str, max_complexity: int = 10) -> Any:
            raise NotImplementedError

    with pytest.raises(
        TypeError,
        match=r"Can't instantiate abstract class IncompleteRunner without an implementation for abstract method.*run_compiler",
    ):
        IncompleteRunner()  # type: ignore[abstract]
