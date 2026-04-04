# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for QARunnerAtom — engine-level intent dispatch."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from specweaver.loom.atoms.base import AtomStatus
from specweaver.loom.atoms.qa_runner.atom import QARunnerAtom
from specweaver.loom.commons.qa_runner.interface import (
    ComplexityRunResult,
    ComplexityViolation,
    LintError,
    LintRunResult,
    TestRunResult,
)

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Atom basics
# ---------------------------------------------------------------------------


class TestAtomBasics:
    """Tests for QARunnerAtom construction and intent dispatch."""

    def test_missing_intent(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        result = atom.run({})
        assert result.status == AtomStatus.FAILED
        assert "intent" in result.message.lower()

    def test_unknown_intent(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        result = atom.run({"intent": "fly_to_moon"})
        assert result.status == AtomStatus.FAILED
        assert "fly_to_moon" in result.message

    def test_known_intents(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        result = atom.run({"intent": "fly_to_moon"})
        # Error message should list known intents
        assert "run_tests" in result.message
        assert "run_linter" in result.message
        assert "run_complexity" in result.message

    def test_unsupported_language(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unsupported language"):
            QARunnerAtom(cwd=tmp_path, language="cobol")


# ---------------------------------------------------------------------------
# run_tests intent
# ---------------------------------------------------------------------------


class TestAtomRunTests:
    """Tests for the run_tests intent."""

    def test_run_tests_success(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        mock_result = TestRunResult(
            passed=5,
            failed=0,
            errors=0,
            skipped=0,
            total=5,
            failures=[],
            coverage_pct=None,
            duration_seconds=0.5,
        )

        with patch.object(atom._runner, "run_tests", return_value=mock_result):
            result = atom.run(
                {
                    "intent": "run_tests",
                    "target": "tests/",
                    "kind": "unit",
                }
            )

        assert result.status == AtomStatus.SUCCESS
        assert result.exports["passed"] == 5
        assert result.exports["failed"] == 0

    def test_run_tests_failures(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        mock_result = TestRunResult(
            passed=3,
            failed=2,
            errors=0,
            skipped=0,
            total=5,
            failures=[],
            coverage_pct=None,
            duration_seconds=1.0,
        )

        with patch.object(atom._runner, "run_tests", return_value=mock_result):
            result = atom.run(
                {
                    "intent": "run_tests",
                    "target": "tests/",
                }
            )

        assert result.status == AtomStatus.FAILED
        assert result.exports["failed"] == 2

    def test_run_tests_missing_target(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        result = atom.run({"intent": "run_tests"})
        assert result.status == AtomStatus.FAILED
        assert "target" in result.message.lower()

    def test_run_tests_with_coverage(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        mock_result = TestRunResult(
            passed=5,
            failed=0,
            errors=0,
            skipped=0,
            total=5,
            failures=[],
            coverage_pct=85.0,
            duration_seconds=1.0,
        )

        with patch.object(atom._runner, "run_tests", return_value=mock_result):
            result = atom.run(
                {
                    "intent": "run_tests",
                    "target": "tests/",
                    "coverage": True,
                }
            )

        assert result.status == AtomStatus.SUCCESS
        assert result.exports["coverage_pct"] == 85.0


# ---------------------------------------------------------------------------
# run_linter intent
# ---------------------------------------------------------------------------


class TestAtomRunLinter:
    """Tests for the run_linter intent."""

    def test_linter_clean(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        mock_result = LintRunResult(
            error_count=0,
            fixable_count=0,
            fixed_count=0,
            errors=[],
        )

        with patch.object(atom._runner, "run_linter", return_value=mock_result):
            result = atom.run(
                {
                    "intent": "run_linter",
                    "target": "src/",
                }
            )

        assert result.status == AtomStatus.SUCCESS
        assert result.exports["error_count"] == 0

    def test_linter_errors(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        mock_result = LintRunResult(
            error_count=2,
            fixable_count=1,
            fixed_count=0,
            errors=[
                LintError(file="foo.py", line=10, code="E501", message="Line too long"),
                LintError(file="bar.py", line=5, code="F401", message="Unused import"),
            ],
        )

        with patch.object(atom._runner, "run_linter", return_value=mock_result):
            result = atom.run(
                {
                    "intent": "run_linter",
                    "target": "src/",
                }
            )

        assert result.status == AtomStatus.FAILED
        assert result.exports["error_count"] == 2
        assert len(result.exports["errors"]) == 2

    def test_linter_missing_target(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        result = atom.run({"intent": "run_linter"})
        assert result.status == AtomStatus.FAILED
        assert "target" in result.message.lower()


# ---------------------------------------------------------------------------
# run_complexity intent
# ---------------------------------------------------------------------------


class TestAtomRunComplexity:
    """Tests for the run_complexity intent."""

    def test_complexity_clean(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        mock_result = ComplexityRunResult(
            violation_count=0,
            max_complexity=10,
        )

        with patch.object(atom._runner, "run_complexity", return_value=mock_result):
            result = atom.run(
                {
                    "intent": "run_complexity",
                    "target": "src/",
                }
            )

        assert result.status == AtomStatus.SUCCESS
        assert result.exports["violation_count"] == 0
        assert "threshold" in result.message.lower()

    def test_complexity_violations(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        mock_result = ComplexityRunResult(
            violation_count=2,
            max_complexity=10,
            violations=[
                ComplexityViolation(
                    file="a.py",
                    line=5,
                    function="big_func",
                    complexity=15,
                    message="`big_func` is too complex (15 > 10)",
                ),
                ComplexityViolation(
                    file="b.py",
                    line=20,
                    function="huge_func",
                    complexity=12,
                    message="`huge_func` is too complex (12 > 10)",
                ),
            ],
        )

        with patch.object(atom._runner, "run_complexity", return_value=mock_result):
            result = atom.run(
                {
                    "intent": "run_complexity",
                    "target": "src/",
                }
            )

        assert result.status == AtomStatus.FAILED
        assert result.exports["violation_count"] == 2
        assert len(result.exports["violations"]) == 2
        assert result.exports["violations"][0]["function"] == "big_func"

    def test_complexity_missing_target(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        result = atom.run({"intent": "run_complexity"})
        assert result.status == AtomStatus.FAILED
        assert "target" in result.message.lower()

    def test_complexity_custom_threshold(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        mock_result = ComplexityRunResult(
            violation_count=0,
            max_complexity=5,
        )

        with patch.object(atom._runner, "run_complexity", return_value=mock_result) as mock_fn:
            result = atom.run(
                {
                    "intent": "run_complexity",
                    "target": "src/",
                    "max_complexity": 5,
                }
            )

        assert result.status == AtomStatus.SUCCESS
        mock_fn.assert_called_once_with(target="src/", max_complexity=5)


# ---------------------------------------------------------------------------
# run_compiler intent
# ---------------------------------------------------------------------------


class TestAtomRunCompiler:
    """Tests for the run_compiler intent."""

    def test_run_compiler_clean(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        from specweaver.loom.commons.qa_runner.interface import CompileRunResult

        mock_result = CompileRunResult(error_count=0, warning_count=0, errors=[])
        with patch.object(atom._runner, "run_compiler", return_value=mock_result):
            result = atom.run({"intent": "run_compiler", "target": "src/"})

        assert result.status == AtomStatus.SUCCESS
        assert result.exports["error_count"] == 0

    def test_run_compiler_errors(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        from specweaver.loom.commons.qa_runner.interface import CompileError, CompileRunResult

        mock_result = CompileRunResult(
            error_count=1,
            warning_count=0,
            errors=[
                CompileError(
                    file="foo.py", line=10, column=0, code="E1", message="Err", is_warning=False
                )
            ],
        )
        with patch.object(atom._runner, "run_compiler", return_value=mock_result):
            result = atom.run({"intent": "run_compiler", "target": "src/"})

        assert result.status == AtomStatus.FAILED
        assert result.exports["error_count"] == 1

    def test_run_compiler_missing_target(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        result = atom.run({"intent": "run_compiler"})
        assert result.status == AtomStatus.FAILED
        assert "target" in result.message.lower()


# ---------------------------------------------------------------------------
# run_debugger intent
# ---------------------------------------------------------------------------


class TestAtomRunDebugger:
    """Tests for the run_debugger intent."""

    def test_run_debugger_success(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        from specweaver.loom.commons.qa_runner.interface import DebugRunResult

        mock_result = DebugRunResult(exit_code=0, duration_seconds=1.0, events=[])
        with patch.object(atom._runner, "run_debugger", return_value=mock_result):
            result = atom.run({"intent": "run_debugger", "target": "src/", "entrypoint": "main.py"})

        assert result.status == AtomStatus.SUCCESS
        assert result.exports["exit_code"] == 0

    def test_run_debugger_failure(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        from specweaver.loom.commons.qa_runner.interface import DebugRunResult, OutputEvent

        mock_result = DebugRunResult(
            exit_code=1,
            duration_seconds=1.0,
            events=[OutputEvent(category="stderr", output="Segfault")],
        )
        with patch.object(atom._runner, "run_debugger", return_value=mock_result):
            result = atom.run({"intent": "run_debugger", "target": "src/", "entrypoint": "main.py"})

        assert result.status == AtomStatus.FAILED
        assert result.exports["exit_code"] == 1

    def test_run_debugger_missing_args(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        result = atom.run({"intent": "run_debugger", "target": "src/"})
        assert result.status == AtomStatus.FAILED
        assert "entrypoint" in result.message.lower()

        result2 = atom.run({"intent": "run_debugger", "entrypoint": "main.py"})
        assert result2.status == AtomStatus.FAILED
        assert "target" in result2.message.lower()


def test_resolve_runner_languages(tmp_path: Path) -> None:
    import pytest

    from specweaver.loom.atoms.qa_runner.atom import _resolve_runner
    from specweaver.loom.commons.qa_runner.java.runner import JavaRunner
    from specweaver.loom.commons.qa_runner.kotlin.runner import KotlinRunner
    from specweaver.loom.commons.qa_runner.typescript.runner import TypeScriptRunner

    with pytest.raises(ValueError, match="Unsupported language"):
        _resolve_runner("ruby", tmp_path)

    ts_runner = _resolve_runner("typescript", tmp_path)
    assert isinstance(ts_runner, TypeScriptRunner)

    java_runner = _resolve_runner("java", tmp_path)
    assert isinstance(java_runner, JavaRunner)

    kotlin_runner = _resolve_runner("kotlin", tmp_path)
    assert isinstance(kotlin_runner, KotlinRunner)

    from specweaver.loom.commons.qa_runner.rust.runner import RustRunner

    rust_runner = _resolve_runner("rust", tmp_path)
    assert isinstance(rust_runner, RustRunner)
