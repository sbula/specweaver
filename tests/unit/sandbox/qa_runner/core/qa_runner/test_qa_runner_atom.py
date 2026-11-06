# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for QARunnerAtom — engine-level intent dispatch."""

from __future__ import annotations

from contextlib import contextmanager, suppress
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from specweaver.core.config.settings import SandboxSettings
from specweaver.sandbox.base import AtomStatus
from specweaver.sandbox.execution.container_executor import ContainerSubprocessExecutor
from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.language.core.runner_factory import qa_atom
from specweaver.sandbox.qa_runner.core.interface import (
    ComplexityRunResult,
    ComplexityViolation,
    LintError,
    LintRunResult,
    TestFailure,
    TestRunResult,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


# ---------------------------------------------------------------------------
# Atom basics
# ---------------------------------------------------------------------------


class TestAtomBasics:
    """Tests for QARunnerAtom construction and intent dispatch."""

    def test_missing_intent(self, tmp_path: Path) -> None:
        atom = qa_atom(cwd=tmp_path, language="python")
        result = atom.run({})
        assert result.status == AtomStatus.FAILED
        assert "intent" in result.message.lower()

    def test_unknown_intent(self, tmp_path: Path) -> None:
        atom = qa_atom(cwd=tmp_path, language="python")
        result = atom.run({"intent": "fly_to_moon"})
        assert result.status == AtomStatus.FAILED
        assert "fly_to_moon" in result.message

    def test_known_intents(self, tmp_path: Path) -> None:
        atom = qa_atom(cwd=tmp_path, language="python")
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
        atom = qa_atom(cwd=tmp_path, language="python")
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
        atom = qa_atom(cwd=tmp_path, language="python")
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
        atom = qa_atom(cwd=tmp_path, language="python")
        result = atom.run({"intent": "run_tests"})
        assert result.status == AtomStatus.FAILED
        assert "target" in result.message.lower()

    def test_run_tests_with_coverage(self, tmp_path: Path) -> None:
        atom = qa_atom(cwd=tmp_path, language="python")
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
        atom = qa_atom(cwd=tmp_path, language="python")

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
        atom = qa_atom(cwd=tmp_path, language="python")

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
        atom = qa_atom(cwd=tmp_path, language="python")
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
        atom = qa_atom(cwd=tmp_path, language="python")

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
        atom = qa_atom(cwd=tmp_path, language="python")

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
        atom = qa_atom(cwd=tmp_path, language="python")
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
        atom = qa_atom(cwd=tmp_path, language="python")
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
        atom = qa_atom(cwd=tmp_path, language="python")
        result = atom.run({"intent": "run_linter"})
        assert result.status == AtomStatus.FAILED
        assert "target" in result.message.lower()

    def test_linter_with_stale_nodes_target_rewriting(self, tmp_path: Path) -> None:
        """SF-4 Edge Case: lint target rewriting."""
        atom = qa_atom(cwd=tmp_path, language="python")

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
        atom = qa_atom(cwd=tmp_path, language="python")
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
        atom = qa_atom(cwd=tmp_path, language="python")
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
        atom = qa_atom(cwd=tmp_path, language="python")
        result = atom.run({"intent": "run_complexity"})
        assert result.status == AtomStatus.FAILED
        assert "target" in result.message.lower()

    def test_complexity_custom_threshold(self, tmp_path: Path) -> None:
        atom = qa_atom(cwd=tmp_path, language="python")
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
        atom = qa_atom(cwd=tmp_path, language="python")
        from specweaver.sandbox.qa_runner.core.interface import CompileRunResult

        mock_result = CompileRunResult(error_count=0, warning_count=0, errors=[])
        with patch.object(atom._runner, "run_compiler", return_value=mock_result):
            result = atom.run({"intent": "run_compiler", "target": "src/"})

        assert result.status == AtomStatus.SUCCESS
        assert result.exports["error_count"] == 0

    def test_run_compiler_errors(self, tmp_path: Path) -> None:
        atom = qa_atom(cwd=tmp_path, language="python")
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
        atom = qa_atom(cwd=tmp_path, language="python")
        result = atom.run({"intent": "run_compiler"})
        assert result.status == AtomStatus.FAILED
        assert "target" in result.message.lower()


# ---------------------------------------------------------------------------
# run_debugger intent
# ---------------------------------------------------------------------------


class TestAtomRunDebugger:
    """Tests for the run_debugger intent."""

    def test_run_debugger_success(self, tmp_path: Path) -> None:
        atom = qa_atom(cwd=tmp_path, language="python")
        from specweaver.sandbox.qa_runner.core.interface import DebugRunResult

        mock_result = DebugRunResult(exit_code=0, duration_seconds=1.0, events=[])
        with patch.object(atom._runner, "run_debugger", return_value=mock_result):
            result = atom.run({"intent": "run_debugger", "target": "src/", "entrypoint": "main.py"})

        assert result.status == AtomStatus.SUCCESS
        assert result.exports["exit_code"] == 0

    def test_run_debugger_failure(self, tmp_path: Path) -> None:
        atom = qa_atom(cwd=tmp_path, language="python")
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
        atom = qa_atom(cwd=tmp_path, language="python")
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
    """The run_architecture intent runs the check `qa_atom` gave it (TECH-082: the shared check)."""

    def test_architecture_clean(self, tmp_path: Path) -> None:
        from specweaver.sandbox.qa_runner.core.interface import ArchitectureRunResult

        atom = qa_atom(cwd=tmp_path, language="python")
        clean = ArchitectureRunResult(violation_count=0, violations=[], unmapped=2)
        with patch.object(atom, "_architecture", return_value=clean) as check:
            result = atom.run({"intent": "run_architecture", "target": "src/a.py"})

        assert result.status == AtomStatus.SUCCESS
        assert (result.exports["violation_count"], result.exports["unmapped"]) == (0, 2)
        check.assert_called_once_with(tmp_path, "src/a.py")

    def test_architecture_violations(self, tmp_path: Path) -> None:
        from specweaver.sandbox.qa_runner.core.interface import (
            ArchitectureRunResult,
            ArchitectureViolation,
        )

        atom = qa_atom(cwd=tmp_path, language="python")
        found = ArchitectureRunResult(
            violation_count=1,
            violations=[ArchitectureViolation("src/foo.py", "E01", "bad import", "uri")],
        )
        with patch.object(atom, "_architecture", return_value=found):
            result = atom.run({"intent": "run_architecture", "target": "src/foo.py"})

        assert result.status == AtomStatus.FAILED
        assert result.exports["violation_count"] == 1
        assert len(result.exports["violations"]) == 1

    def test_each_extra_is_exported(self, tmp_path: Path) -> None:
        from specweaver.commons.qa import ExtraRun
        from specweaver.sandbox.qa_runner.core.interface import ArchitectureRunResult

        atom = qa_atom(cwd=tmp_path, language="python")
        verdict = ArchitectureRunResult(0, [], extras=[ExtraRun("tach", ran=False, reason="gone")])
        with patch.object(atom, "_architecture", return_value=verdict):
            result = atom.run({"intent": "run_architecture", "target": "src/a.py"})

        assert result.exports["extras"] == [
            {"tool": "tach", "ran": False, "reason": "gone", "violation_count": 0}
        ]

    def test_architecture_missing_target(self, tmp_path: Path) -> None:
        atom = qa_atom(cwd=tmp_path, language="python")
        result = atom.run({"intent": "run_architecture"})
        assert result.status == AtomStatus.FAILED
        assert "target" in result.message.lower()

    def test_an_atom_given_no_check_fails(self, tmp_path: Path) -> None:
        from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

        atom = QARunnerAtom(tmp_path, runner=object())  # type: ignore[arg-type]
        result = atom.run({"intent": "run_architecture", "target": "a.py"})

        assert result.status == AtomStatus.FAILED

    def test_an_unreadable_target_fails(self, tmp_path: Path) -> None:
        atom = qa_atom(cwd=tmp_path, language="python")
        with patch.object(
            atom, "_architecture", side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "x")
        ):
            result = atom.run({"intent": "run_architecture", "target": "a.py"})

        assert result.status == AtomStatus.FAILED
        assert "Cannot read a.py" in result.message


def test_resolve_runner_languages(tmp_path: Path) -> None:
    from specweaver.sandbox.language.core.java.runner import JavaRunner
    from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner
    from specweaver.sandbox.language.core.python.runner import PythonQARunner
    from specweaver.sandbox.language.core.runner_factory import resolve_runner
    from specweaver.sandbox.language.core.rust.runner import RustRunner
    from specweaver.sandbox.language.core.typescript.runner import TypeScriptRunner

    # TECH-079 FR-14: the run's language picks the runner; build files no longer do.
    expected = {
        "python": PythonQARunner,
        "typescript": TypeScriptRunner,
        "java": JavaRunner,
        "kotlin": KotlinRunner,
        "rust": RustRunner,
    }
    for language, runner_type in expected.items():
        runner = resolve_runner(tmp_path, SubprocessExecutor(cwd=tmp_path), language)
        assert isinstance(runner, runner_type)


def test_resolve_runner_multi_language_dynamic_namespace_stability(tmp_path: Path) -> None:
    """
    Edge Case: Namespace routing stability under concurrent / rapid dynamic paths (Implicit Namespace).
    Proves consecutive dynamic traversals over the proxy-less PEP 420 `sandbox.qa_runner.*`
    paths do not fail from sys.path thrashing or incorrect __package__ resolution.
    """
    from specweaver.sandbox.language.core.runner_factory import resolve_runner

    for language in ["typescript", "java", "kotlin", "rust"]:
        runner = resolve_runner(tmp_path, SubprocessExecutor(cwd=tmp_path), language)
        assert runner is not None


# ---------------------------------------------------------------------------
# B-EXEC-01: sandbox_settings -> executor selection
# ---------------------------------------------------------------------------


class TestSandboxSettingsExecutorSelection:
    def test_no_sandbox_settings_defaults_to_host_executor(self, tmp_path: Path) -> None:
        atom = qa_atom(cwd=tmp_path, language="python")
        assert isinstance(atom._runner._executor, SubprocessExecutor)
        assert not isinstance(atom._runner._executor, ContainerSubprocessExecutor)

    def test_explicit_host_mode_uses_host_executor(self, tmp_path: Path) -> None:
        atom = qa_atom(
            cwd=tmp_path, language="python", sandbox_settings=SandboxSettings(execution_mode="host")
        )
        assert isinstance(atom._runner._executor, SubprocessExecutor)
        assert not isinstance(atom._runner._executor, ContainerSubprocessExecutor)

    def test_container_mode_builds_container_executor(self, tmp_path: Path) -> None:
        atom = qa_atom(
            cwd=tmp_path,
            language="python",
            sandbox_settings=SandboxSettings(execution_mode="container"),
            build_tool="uv",
        )
        assert isinstance(atom._runner._executor, ContainerSubprocessExecutor)

    def test_container_mode_derives_mounts_from_cwd(self, tmp_path: Path) -> None:
        atom = qa_atom(
            cwd=tmp_path,
            language="python",
            sandbox_settings=SandboxSettings(execution_mode="container"),
            build_tool="uv",
        )
        mounts = atom._runner._executor._mounts
        assert mounts.source_root == tmp_path
        assert mounts.scratch_root == tmp_path / ".specweaver" / ".sandbox" / "scratch"
        assert mounts.cache_root == tmp_path / ".specweaver" / ".sandbox" / "cache"


# ---------------------------------------------------------------------------
# One path check for every intent
# ---------------------------------------------------------------------------

_INTENTS = [
    "run_tests",
    "run_linter",
    "run_complexity",
    "run_compiler",
    "run_debugger",
    "run_architecture",
]


@contextmanager
def _tools(atom: Any) -> Iterator[MagicMock]:
    """The language runner and the architecture check, as one mock: no call means no tool ran."""
    with patch.object(atom, "_runner") as runner, patch.object(atom, "_architecture") as check:
        tools = MagicMock()
        tools.attach_mock(runner, "runner")
        tools.attach_mock(check, "architecture")
        yield tools


def _context(intent: str, target: object, entrypoint: object = "main.py") -> dict[str, object]:
    context: dict[str, object] = {"intent": intent, "target": target}
    if intent == "run_debugger":
        context["entrypoint"] = entrypoint
    return context


class TestEveryIntentStaysInside:
    """Proves: TECH-075 FR-5, NFR-3, NFR-4.

    One check in `run()`, before any intent: every `target`, each of `targets`, and the debugger's
    `entrypoint` must lie inside `cwd`. A refusal is FAILED and no tool starts.
    """

    @staticmethod
    def _project(tmp_path: Path) -> Path:
        project = tmp_path / "project"
        project.mkdir()
        return project

    @pytest.mark.parametrize("intent", _INTENTS)
    @pytest.mark.parametrize("target", ["../outside.py", "/etc/passwd", "src/\x00.py"])
    def test_a_target_outside_is_refused_before_any_tool(
        self, tmp_path: Path, intent: str, target: str
    ) -> None:
        """[Hostile] climbing out, an absolute path, a null byte — for every intent."""
        atom = qa_atom(cwd=self._project(tmp_path), language="python")
        with _tools(atom) as runner:
            result = atom.run(_context(intent, target))
        assert result.status == AtomStatus.FAILED
        assert "outside" in result.message
        assert runner.method_calls == []

    @pytest.mark.parametrize("intent", _INTENTS)
    def test_a_link_that_points_outside_is_refused(self, tmp_path: Path, intent: str) -> None:
        """[Hostile] links are resolved before the check (NFR-3)."""
        project = self._project(tmp_path)
        (project / "escape").symlink_to(tmp_path, target_is_directory=True)
        atom = qa_atom(cwd=project, language="python")
        with _tools(atom) as runner:
            result = atom.run(_context(intent, "escape/x.py"))
        assert result.status == AtomStatus.FAILED
        assert runner.method_calls == []

    @pytest.mark.parametrize("intent", ["run_tests", "run_linter"])
    def test_one_outside_entry_in_targets_refuses_the_run(
        self, tmp_path: Path, intent: str
    ) -> None:
        """[Hostile] a list is only as safe as its worst entry."""
        atom = qa_atom(cwd=self._project(tmp_path), language="python")
        with _tools(atom) as runner:
            result = atom.run({"intent": intent, "targets": ["tests/a.py", "../b.py"]})
        assert result.status == AtomStatus.FAILED
        assert runner.method_calls == []

    def test_an_entrypoint_outside_is_refused(self, tmp_path: Path) -> None:
        """[Hostile] the debugger runs `python <entrypoint>` (agreed 2026-10-22)."""
        atom = qa_atom(cwd=self._project(tmp_path), language="python")
        with _tools(atom) as runner:
            result = atom.run(_context("run_debugger", "src/", entrypoint="../evil.py"))
        assert result.status == AtomStatus.FAILED
        assert "../evil.py" in result.message
        assert runner.method_calls == []

    def test_a_class_name_entrypoint_passes(self, tmp_path: Path) -> None:
        """[Boundary] Java and Kotlin pass a main class, which lies inside as a name."""
        atom = qa_atom(cwd=self._project(tmp_path), language="python")
        with _tools(atom) as runner, suppress(TypeError):
            atom.run(_context("run_debugger", ".", entrypoint="com.example.Main"))
        assert runner.runner.run_debugger.called

    @pytest.mark.parametrize("target", [123, ["src/"], None.__class__])
    def test_a_target_that_is_not_a_path_string_is_refused(
        self, tmp_path: Path, target: object
    ) -> None:
        """[Hostile] a wrong type never reaches a tool."""
        atom = qa_atom(cwd=self._project(tmp_path), language="python")
        with _tools(atom) as runner:
            result = atom.run(_context("run_linter", target))
        assert result.status == AtomStatus.FAILED
        assert runner.method_calls == []

    @pytest.mark.parametrize("intent", _INTENTS)
    @pytest.mark.parametrize("target", ["src/mod.py", ".", "PROJECT_ABSOLUTE"])
    def test_a_target_inside_reaches_the_tool(
        self, tmp_path: Path, intent: str, target: str
    ) -> None:
        """[Happy] relative, the root itself, and an absolute path inside."""
        project = self._project(tmp_path)
        target = str(project / "src") if target == "PROJECT_ABSOLUTE" else target
        atom = qa_atom(cwd=project, language="python")
        with _tools(atom) as runner, suppress(TypeError):
            atom.run(_context(intent, target))  # the mock's result is not a real one
        assert runner.method_calls != []

    def test_the_scenarios_mount_is_inside_only_in_a_scenario_run(self, tmp_path: Path) -> None:
        """[Boundary] `/scenarios/...` passes with the mount, and is refused without it (NFR-4)."""
        project = self._project(tmp_path)
        context = {"intent": "run_tests", "target": "/scenarios/generated/test_x.py"}
        with (
            patch("specweaver.sandbox.language.core.runner_factory._build_container_executor"),
            patch("specweaver.sandbox.language.core.runner_factory.resolve_runner") as resolve,
        ):
            mounted = qa_atom(
                cwd=project, language="python", scenarios_root=tmp_path / "store", build_tool="uv"
            )
            with suppress(TypeError):
                mounted.run(context)
        assert resolve.return_value.run_tests.called

        plain = qa_atom(cwd=project, language="python")
        with patch.object(plain, "_runner") as runner:
            assert plain.run(context).status == AtomStatus.FAILED
        assert runner.method_calls == []

    @pytest.mark.parametrize("intent", _INTENTS)
    def test_a_missing_target_keeps_its_own_message(self, tmp_path: Path, intent: str) -> None:
        """[Degradation] the check skips empty values, so each intent still names what is missing."""
        atom = qa_atom(cwd=self._project(tmp_path), language="python")
        result = atom.run(_context(intent, ""))
        assert result.status == AtomStatus.FAILED
        assert "Missing" in result.message

    def test_targets_given_as_one_string_is_still_checked(self, tmp_path: Path) -> None:
        """[Hostile] a wrongly shaped `targets` is checked as one path, not skipped."""
        atom = qa_atom(cwd=self._project(tmp_path), language="python")
        with _tools(atom) as runner:
            result = atom.run({"intent": "run_linter", "targets": "../b.py"})
        assert result.status == AtomStatus.FAILED
        assert runner.method_calls == []

    def test_a_whitespace_target_is_refused(self, tmp_path: Path) -> None:
        """[Boundary] blank is not the project root."""
        atom = qa_atom(cwd=self._project(tmp_path), language="python")
        with _tools(atom) as runner:
            result = atom.run({"intent": "run_linter", "target": "   "})
        assert result.status == AtomStatus.FAILED
        assert runner.method_calls == []
