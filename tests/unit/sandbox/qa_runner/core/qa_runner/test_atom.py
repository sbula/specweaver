# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for QARunnerAtom — engine-level intent dispatch."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from specweaver.sandbox.base import AtomStatus
from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom
from specweaver.sandbox.qa_runner.core.interface import (
    ComplexityRunResult,
    ComplexityViolation,
    LintError,
    LintRunResult,
    TestFailure,
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
        assert "run_architecture" in result.message


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

    def test_run_tests_prevents_path_traversal(self, tmp_path: Path) -> None:
        """NFR-3 Edge Case: Must prevent execution if target traverses outside cwd."""
        atom = QARunnerAtom(cwd=tmp_path)

        result = atom.run(
            {
                "intent": "run_tests",
                "target": "../../../etc/passwd",
            }
        )

        # We expect a failure due to sandbox violation
        assert result.status == AtomStatus.FAILED
        assert (
            "traversal" in result.message.lower()
            or "outside" in result.message.lower()
            or "sandbox" in result.message.lower()
        )

    def test_run_tests_enforces_timeout(self, tmp_path: Path) -> None:
        """NFR-4 Edge Case: Must handle sub-process timeouts gracefully."""
        atom = QARunnerAtom(cwd=tmp_path)

        with patch.object(
            atom._runner, "run_tests", side_effect=TimeoutError("Process timed out after 120s")
        ):
            result = atom.run(
                {
                    "intent": "run_tests",
                    "target": "tests/",
                }
            )

        assert result.status == AtomStatus.FAILED
        assert "time" in result.message.lower()

    def test_run_tests_with_stale_nodes_target_rewriting(self, tmp_path: Path) -> None:
        """SF-4 Edge Case: test target rewriting dynamically bounds runs."""
        atom = QARunnerAtom(cwd=tmp_path)
        # Mock results
        result1 = TestRunResult(
            passed=2,
            failed=0,
            errors=0,
            skipped=0,
            total=2,
            failures=[],
            coverage_pct=None,
            duration_seconds=0.1,
        )
        result2 = TestRunResult(
            passed=3,
            failed=1,
            errors=0,
            skipped=0,
            total=4,
            failures=[TestFailure(nodeid="a", message="fail")],
            coverage_pct=None,
            duration_seconds=0.2,
        )

        with patch.object(atom._runner, "run_tests", side_effect=[result1, result2]) as mock_rt:
            result = atom.run(
                {
                    "intent": "run_tests",
                    "targets": ["src/a.py", "tests/b.py"],
                }
            )

        assert mock_rt.call_count == 2

        called_targets = {call.kwargs.get("target") for call in mock_rt.call_args_list}
        assert called_targets == {"src/a.py", "tests/b.py"}

        assert result.status == AtomStatus.FAILED
        assert result.exports["passed"] == 5
        assert result.exports["failed"] == 1
        assert result.exports["total"] == 6
        assert len(result.exports["failures"]) == 1

    def test_run_tests_with_empty_stale_nodes_shortcuts(self, tmp_path: Path) -> None:
        """SF-4 Edge Case: 0 stale nodes shortcut out."""
        atom = QARunnerAtom(cwd=tmp_path)

        with patch.object(atom._runner, "run_tests") as mock_rt:
            result = atom.run(
                {
                    "intent": "run_tests",
                    "targets": [],
                }
            )

        assert mock_rt.call_count == 0
        assert result.status == AtomStatus.SUCCESS
        assert result.exports["passed"] == 0
        assert result.exports["failed"] == 0
        assert result.exports["total"] == 0

    # ---------------------------------------------------------------------------
    # run_linter intent
    # ---------------------------------------------------------------------------

    def test_run_linter_with_empty_stale_nodes_shortcuts(self, tmp_path: Path) -> None:
        """SF-4 Edge Case: 0 stale nodes shortcut out for linter without errors."""
        atom = QARunnerAtom(cwd=tmp_path)

        with patch.object(atom._runner, "run_linter") as mock_rl:
            result = atom.run(
                {
                    "intent": "run_linter",
                    "targets": [],
                }
            )

        assert mock_rl.call_count == 0
        assert result.status == AtomStatus.SUCCESS
        assert result.exports["error_count"] == 0
        assert result.exports["fixable_count"] == 0
        assert result.exports["fixed_count"] == 0


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

    def test_linter_with_stale_nodes_target_rewriting(self, tmp_path: Path) -> None:
        """SF-4 Edge Case: lint target rewriting."""
        atom = QARunnerAtom(cwd=tmp_path)

        result1 = LintRunResult(
            error_count=1,
            fixable_count=0,
            fixed_count=0,
            errors=[LintError(file="a", line=1, code="1", message="E")],
        )
        result2 = LintRunResult(
            error_count=2,
            fixable_count=0,
            fixed_count=0,
            errors=[
                LintError(file="b", line=1, code="2", message="E"),
                LintError(file="c", line=1, code="3", message="E"),
            ],
        )

        with patch.object(atom._runner, "run_linter", side_effect=[result1, result2]) as mock_rl:
            result = atom.run(
                {
                    "intent": "run_linter",
                    "targets": ["src/c.py", "src/d.py"],
                }
            )

        assert mock_rl.call_count == 2
        assert result.status == AtomStatus.FAILED
        assert result.exports["error_count"] == 3


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
        from specweaver.sandbox.qa_runner.core.interface import CompileRunResult

        mock_result = CompileRunResult(error_count=0, warning_count=0, errors=[])
        with patch.object(atom._runner, "run_compiler", return_value=mock_result):
            result = atom.run({"intent": "run_compiler", "target": "src/"})

        assert result.status == AtomStatus.SUCCESS
        assert result.exports["error_count"] == 0

    def test_run_compiler_errors(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        from specweaver.sandbox.qa_runner.core.interface import CompileError, CompileRunResult

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
        from specweaver.sandbox.qa_runner.core.interface import DebugRunResult

        mock_result = DebugRunResult(exit_code=0, duration_seconds=1.0, events=[])
        with patch.object(atom._runner, "run_debugger", return_value=mock_result):
            result = atom.run({"intent": "run_debugger", "target": "src/", "entrypoint": "main.py"})

        assert result.status == AtomStatus.SUCCESS
        assert result.exports["exit_code"] == 0

    def test_run_debugger_failure(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        from specweaver.sandbox.qa_runner.core.interface import DebugRunResult, OutputEvent

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


# ---------------------------------------------------------------------------
# run_architecture intent
# ---------------------------------------------------------------------------


class TestAtomRunArchitecture:
    """Tests for the run_architecture intent."""

    def test_architecture_clean(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        from specweaver.sandbox.qa_runner.core.interface import ArchitectureRunResult

        mock_result = ArchitectureRunResult(violation_count=0, violations=[])
        with patch.object(atom._runner, "run_architecture_check", return_value=mock_result):
            result = atom.run({"intent": "run_architecture", "target": "src/"})

        assert result.status == AtomStatus.SUCCESS
        assert result.exports["violation_count"] == 0

    def test_architecture_violations(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        from specweaver.sandbox.qa_runner.core.interface import (
            ArchitectureRunResult,
            ArchitectureViolation,
        )

        mock_result = ArchitectureRunResult(
            violation_count=1,
            violations=[ArchitectureViolation("src/foo.py", "E01", "bad import", "uri")],
        )
        with patch.object(atom._runner, "run_architecture_check", return_value=mock_result):
            result = atom.run({"intent": "run_architecture", "target": "src/"})

        assert result.status == AtomStatus.FAILED
        assert result.exports["violation_count"] == 1
        assert len(result.exports["violations"]) == 1

    def test_architecture_missing_target(self, tmp_path: Path) -> None:
        atom = QARunnerAtom(cwd=tmp_path)
        result = atom.run({"intent": "run_architecture"})
        assert result.status == AtomStatus.FAILED
        assert "target" in result.message.lower()


def test_resolve_runner_languages(tmp_path: Path) -> None:
    from specweaver.sandbox.language.core.java.runner import JavaRunner
    from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner
    from specweaver.sandbox.language.core.python.runner import PythonQARunner
    from specweaver.sandbox.language.core.rust.runner import RustRunner
    from specweaver.sandbox.language.core.typescript.runner import TypeScriptRunner
    from specweaver.sandbox.qa_runner.core.factory import resolve_runner

    # Default is python
    runner = resolve_runner(tmp_path)
    assert isinstance(runner, PythonQARunner)

    # TypeScript
    (tmp_path / "package.json").touch()
    runner = resolve_runner(tmp_path)
    assert isinstance(runner, TypeScriptRunner)
    (tmp_path / "package.json").unlink()

    # Java
    (tmp_path / "pom.xml").touch()
    runner = resolve_runner(tmp_path)
    assert isinstance(runner, JavaRunner)
    (tmp_path / "pom.xml").unlink()

    # Kotlin
    (tmp_path / "build.gradle").touch()
    runner = resolve_runner(tmp_path)
    assert isinstance(runner, KotlinRunner)
    (tmp_path / "build.gradle").unlink()

    # Rust
    (tmp_path / "Cargo.toml").touch()
    runner = resolve_runner(tmp_path)
    assert isinstance(runner, RustRunner)
    (tmp_path / "Cargo.toml").unlink()


def test_resolve_runner_multi_language_dynamic_namespace_stability(tmp_path: Path) -> None:
    """
    Edge Case: Namespace routing stability under concurrent / rapid dynamic paths (Implicit Namespace).
    Proves consecutive dynamic traversals over the proxy-less PEP 420 `loom.commons.qa_runner.*`
    paths do not fail from sys.path thrashing or incorrect __package__ resolution.
    """
    from specweaver.sandbox.qa_runner.core.factory import resolve_runner

    markers = ["package.json", "pom.xml", "build.gradle", "Cargo.toml"]
    for marker in markers:
        (tmp_path / marker).touch()
        runner = resolve_runner(tmp_path)
        assert runner is not None
        (tmp_path / marker).unlink()
