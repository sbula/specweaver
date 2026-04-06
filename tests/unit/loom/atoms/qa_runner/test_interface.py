# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for the test runner interface and Python implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from specweaver.loom.commons.language.python.runner import PythonQARunner
from specweaver.loom.commons.qa_runner.interface import (
    ComplexityRunResult,
    ComplexityViolation,
    LintError,
    LintRunResult,
    QARunnerInterface,
    TestFailure,
    TestRunResult,
)

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


class TestResultTypes:
    """Tests for TestRunResult, LintRunResult, and ComplexityRunResult."""

    def test_test_run_result_construction(self) -> None:
        result = TestRunResult(
            passed=8,
            failed=2,
            errors=0,
            skipped=1,
            total=11,
            failures=[TestFailure(nodeid="test_foo.py::test_bar", message="assert 1 == 2")],
            coverage_pct=85.0,
            duration_seconds=1.5,
        )
        assert result.passed == 8
        assert result.failed == 2
        assert result.total == 11
        assert len(result.failures) == 1
        assert result.failures[0].nodeid == "test_foo.py::test_bar"
        assert result.coverage_pct == 85.0

    def test_test_run_result_no_coverage(self) -> None:
        result = TestRunResult(
            passed=5,
            failed=0,
            errors=0,
            skipped=0,
            total=5,
            failures=[],
            coverage_pct=None,
            duration_seconds=0.5,
        )
        assert result.coverage_pct is None

    def test_lint_run_result_construction(self) -> None:
        result = LintRunResult(
            error_count=3,
            fixable_count=2,
            fixed_count=0,
            errors=[LintError(file="foo.py", line=10, code="E501", message="Line too long")],
        )
        assert result.error_count == 3
        assert result.fixable_count == 2
        assert len(result.errors) == 1
        assert result.errors[0].code == "E501"

    def test_lint_run_result_clean(self) -> None:
        result = LintRunResult(error_count=0, fixable_count=0, fixed_count=0, errors=[])
        assert result.error_count == 0
        assert result.errors == []

    def test_test_failure_fields(self) -> None:
        f = TestFailure(nodeid="tests/test_a.py::test_x", message="boom", stdout="output")
        assert f.nodeid == "tests/test_a.py::test_x"
        assert f.message == "boom"
        assert f.stdout == "output"

    def test_test_failure_default_stdout(self) -> None:
        f = TestFailure(nodeid="t::t", message="x")
        assert f.stdout == ""

    def test_complexity_violation_fields(self) -> None:
        v = ComplexityViolation(
            file="foo.py",
            line=10,
            function="bar",
            complexity=15,
            message="`bar` is too complex (15 > 10)",
        )
        assert v.file == "foo.py"
        assert v.line == 10
        assert v.function == "bar"
        assert v.complexity == 15

    def test_complexity_run_result_clean(self) -> None:
        result = ComplexityRunResult(violation_count=0, max_complexity=10)
        assert result.violation_count == 0
        assert result.violations == []

    def test_complexity_run_result_with_violations(self) -> None:
        v = ComplexityViolation(
            file="a.py",
            line=5,
            function="big",
            complexity=12,
            message="`big` is too complex (12 > 10)",
        )
        result = ComplexityRunResult(violation_count=1, max_complexity=10, violations=[v])
        assert result.violation_count == 1
        assert result.violations[0].function == "big"


# ---------------------------------------------------------------------------
# Interface contract
# ---------------------------------------------------------------------------


class TestInterfaceContract:
    """Tests that QARunnerInterface is an ABC and cannot be instantiated."""

    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            QARunnerInterface()  # type: ignore[abstract]

    def test_python_runner_is_instance(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        assert isinstance(runner, QARunnerInterface)


# ---------------------------------------------------------------------------
# PythonQARunner — run_tests
# ---------------------------------------------------------------------------


class TestPythonQARunnerTests:
    """Tests for PythonQARunner.run_tests via subprocess mocking."""

    def test_all_tests_pass(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "5 passed in 0.50s\n"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run_tests(target="tests/unit/", kind="unit")

        assert result.passed == 5
        assert result.failed == 0
        assert result.total == 5
        assert result.failures == []
        # Verify pytest was called with -m unit
        call_args = mock_run.call_args[0][0]
        assert "-m" in call_args
        assert "unit" in call_args

    def test_some_tests_fail(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = (
            "FAILED tests/test_foo.py::test_bar - assert 1 == 2\n3 passed, 2 failed in 1.20s\n"
        )
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = runner.run_tests(target="tests/")

        assert result.passed == 3
        assert result.failed == 2
        assert result.total == 5
        assert len(result.failures) >= 1

    def test_timeout_returns_error(self, tmp_path: Path) -> None:
        import subprocess

        runner = PythonQARunner(cwd=tmp_path)

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pytest", 120)):
            result = runner.run_tests(target="tests/", timeout=120)

        assert result.failed > 0 or result.errors > 0
        assert result.total >= 0

    def test_with_coverage(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "5 passed in 0.50s\nTOTAL                  100     15     85%\n"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run_tests(target="tests/", coverage=True)

        assert result.coverage_pct == 85.0
        call_args = mock_run.call_args[0][0]
        assert "--cov" in call_args

    def test_scope_parameter(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "3 passed in 0.30s\n"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run_tests(target="tests/", kind="unit", scope="flow")

        assert result.passed == 3
        # scope should filter via -k or target path
        call_args = mock_run.call_args[0][0]
        assert "flow" in " ".join(call_args)

    def test_kind_e2e(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "2 passed in 5.00s\n"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            _ = runner.run_tests(target="tests/", kind="e2e")

        call_args = mock_run.call_args[0][0]
        assert "-m" in call_args
        assert "e2e" in call_args


# ---------------------------------------------------------------------------
# PythonQARunner — run_linter
# ---------------------------------------------------------------------------


class TestPythonQARunnerLinter:
    """Tests for PythonQARunner.run_linter via subprocess mocking."""

    def test_linter_clean(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "[]"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = runner.run_linter(target="src/")

        assert result.error_count == 0
        assert result.errors == []

    def test_linter_errors(self, tmp_path: Path) -> None:
        import json

        runner = PythonQARunner(cwd=tmp_path)
        lint_output = json.dumps(
            [
                {
                    "filename": "foo.py",
                    "location": {"row": 10},
                    "code": "E501",
                    "message": "Line too long",
                },
                {
                    "filename": "bar.py",
                    "location": {"row": 5},
                    "code": "F401",
                    "message": "Unused import",
                },
            ]
        )
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = lint_output
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = runner.run_linter(target="src/")

        assert result.error_count == 2
        assert len(result.errors) == 2
        assert result.errors[0].code == "E501"
        assert result.errors[1].file == "bar.py"

    def test_linter_with_fix(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "[]"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run_linter(target="src/", fix=True)

        assert result.error_count == 0
        # With fix=True, should call ruff format then ruff check --fix
        assert mock_run.call_count >= 2

    def test_linter_timeout(self, tmp_path: Path) -> None:
        import subprocess

        runner = PythonQARunner(cwd=tmp_path)

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ruff", 60)):
            result = runner.run_linter(target="src/")

        assert result.error_count >= 0  # Should not crash


# ---------------------------------------------------------------------------
# PythonQARunner — run_complexity
# ---------------------------------------------------------------------------


class TestPythonQARunnerComplexity:
    """Tests for PythonQARunner.run_complexity via subprocess mocking."""

    def test_complexity_clean(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "[]"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = runner.run_complexity(target="src/")

        assert result.violation_count == 0
        assert result.max_complexity == 10
        assert result.violations == []

    def test_complexity_violations(self, tmp_path: Path) -> None:
        import json

        runner = PythonQARunner(cwd=tmp_path)
        ruff_output = json.dumps(
            [
                {
                    "filename": "runner.py",
                    "location": {"row": 124},
                    "code": "C901",
                    "message": "`_execute_loop` is too complex (12 > 10)",
                },
            ]
        )
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ruff_output
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = runner.run_complexity(target="src/", max_complexity=10)

        assert result.violation_count == 1
        assert result.max_complexity == 10
        assert result.violations[0].file == "runner.py"
        assert result.violations[0].line == 124
        assert result.violations[0].function == "_execute_loop"
        assert result.violations[0].complexity == 12

    def test_complexity_custom_threshold(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "[]"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run_complexity(target="src/", max_complexity=5)

        assert result.max_complexity == 5
        # Check the --config flag includes our threshold
        call_args = mock_run.call_args[0][0]
        assert any("max-complexity=5" in str(a) for a in call_args)

    def test_complexity_timeout(self, tmp_path: Path) -> None:
        import subprocess

        runner = PythonQARunner(cwd=tmp_path)

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ruff", 60)):
            result = runner.run_complexity(target="src/")

        assert result.violation_count == 0  # Should not crash
