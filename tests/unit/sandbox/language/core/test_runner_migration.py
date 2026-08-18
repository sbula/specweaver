# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Migration verification tests for language runners → SubprocessExecutor.

Verifies each runner:
1. Accepts an optional executor parameter (DI)
2. Creates a default executor when none provided
3. Has private _cwd attribute (consistency)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from specweaver.sandbox.execution.executor import SubprocessExecutor

if TYPE_CHECKING:
    from pathlib import Path


class TestPythonRunnerMigration:
    """Verify PythonQARunner accepts and uses SubprocessExecutor."""

    def test_accepts_executor(self, tmp_path: Path) -> None:
        """PythonQARunner(cwd, executor=mock) stores the provided executor."""
        from specweaver.sandbox.language.core.python.runner import PythonQARunner

        mock_executor = MagicMock(spec=SubprocessExecutor)
        runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)
        assert runner._executor is mock_executor

    def test_creates_default_executor(self, tmp_path: Path) -> None:
        """PythonQARunner(cwd) auto-creates a SubprocessExecutor."""
        from specweaver.sandbox.language.core.python.runner import PythonQARunner

        runner = PythonQARunner(cwd=tmp_path)
        assert isinstance(runner._executor, SubprocessExecutor)

    def test_has_private_cwd(self, tmp_path: Path) -> None:
        """PythonQARunner uses _cwd (private) attribute."""
        from specweaver.sandbox.language.core.python.runner import PythonQARunner

        runner = PythonQARunner(cwd=tmp_path)
        assert runner._cwd == tmp_path


class TestTypeScriptRunnerMigration:
    """Verify TypeScriptRunner accepts and uses SubprocessExecutor."""

    def test_accepts_executor(self, tmp_path: Path) -> None:
        from specweaver.sandbox.language.core.typescript.runner import TypeScriptRunner

        mock_executor = MagicMock(spec=SubprocessExecutor)
        runner = TypeScriptRunner(cwd=tmp_path, executor=mock_executor)
        assert runner._executor is mock_executor

    def test_creates_default_executor(self, tmp_path: Path) -> None:
        from specweaver.sandbox.language.core.typescript.runner import TypeScriptRunner

        runner = TypeScriptRunner(cwd=tmp_path)
        assert isinstance(runner._executor, SubprocessExecutor)

    def test_has_private_cwd(self, tmp_path: Path) -> None:
        from specweaver.sandbox.language.core.typescript.runner import TypeScriptRunner

        runner = TypeScriptRunner(cwd=tmp_path)
        assert runner._cwd == tmp_path


class TestRustRunnerMigration:
    """Verify RustRunner accepts and uses SubprocessExecutor."""

    def test_accepts_executor(self, tmp_path: Path) -> None:
        from specweaver.sandbox.language.core.rust.runner import RustRunner

        mock_executor = MagicMock(spec=SubprocessExecutor)
        runner = RustRunner(cwd=tmp_path, executor=mock_executor)
        assert runner._executor is mock_executor

    def test_creates_default_executor(self, tmp_path: Path) -> None:
        from specweaver.sandbox.language.core.rust.runner import RustRunner

        runner = RustRunner(cwd=tmp_path)
        assert isinstance(runner._executor, SubprocessExecutor)

    def test_has_private_cwd(self, tmp_path: Path) -> None:
        from specweaver.sandbox.language.core.rust.runner import RustRunner

        runner = RustRunner(cwd=tmp_path)
        assert runner._cwd == tmp_path


class TestJavaRunnerMigration:
    """Verify JavaRunner accepts and uses SubprocessExecutor."""

    def test_accepts_executor(self, tmp_path: Path) -> None:
        """JavaRunner(cwd, executor=mock) stores the provided executor."""
        from specweaver.sandbox.language.core.java.runner import JavaRunner

        mock_executor = MagicMock(spec=SubprocessExecutor)
        runner = JavaRunner(cwd=tmp_path, executor=mock_executor)
        assert runner._executor is mock_executor

    def test_creates_default_executor(self, tmp_path: Path) -> None:
        """JavaRunner(cwd) auto-creates a SubprocessExecutor."""
        from specweaver.sandbox.language.core.java.runner import JavaRunner

        runner = JavaRunner(cwd=tmp_path)
        assert isinstance(runner._executor, SubprocessExecutor)

    def test_has_private_cwd(self, tmp_path: Path) -> None:
        """JavaRunner uses _cwd (private) attribute."""
        from specweaver.sandbox.language.core.java.runner import JavaRunner

        runner = JavaRunner(cwd=tmp_path)
        assert runner._cwd == tmp_path


class TestKotlinRunnerMigration:
    """Verify KotlinRunner accepts and uses SubprocessExecutor."""

    def test_accepts_executor(self, tmp_path: Path) -> None:
        """KotlinRunner(cwd, executor=mock) stores the provided executor."""
        from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner

        mock_executor = MagicMock(spec=SubprocessExecutor)
        runner = KotlinRunner(cwd=tmp_path, executor=mock_executor)
        assert runner._executor is mock_executor

    def test_creates_default_executor(self, tmp_path: Path) -> None:
        """KotlinRunner(cwd) auto-creates a SubprocessExecutor."""
        from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner

        runner = KotlinRunner(cwd=tmp_path)
        assert isinstance(runner._executor, SubprocessExecutor)

    def test_has_private_cwd(self, tmp_path: Path) -> None:
        """KotlinRunner uses _cwd (private) attribute."""
        from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner

        runner = KotlinRunner(cwd=tmp_path)
        assert runner._cwd == tmp_path


class TestBuildFailedWithoutResults:
    """A build that fails before it can write test reports is not an empty suite.

    `did_not_run` keys on **empty stdout**, which is right for a tool that never started. A JVM build
    tool that fails to compile prints a great deal to stdout and exits non-zero, so it slips past that
    check — and then a JUnit report directory with no XML in it harvests as `0 passed, 0 failed`.

    Measured 2026-08-18 against real Maven: a Kotlin project whose compiler rejected the JDK produced
    `BUILD FAILURE`, exit 1, and `TestRunResult(passed=0, failed=0, errors=0, total=0)`. That is the
    same vacuous success `TECH-032` removed from the other direction.

    Proves: TECH-031 FR-14
    """

    @staticmethod
    def _result(exit_code: int, stdout: str = "", stderr: str = ""):
        from specweaver.sandbox.execution.models import SubprocessResult

        return SubprocessResult(
            exit_code=exit_code, stdout=stdout, stderr=stderr, duration_seconds=0.1
        )

    def test_a_failed_build_with_no_results_is_a_failure(self) -> None:
        from specweaver.sandbox.language.core.toolchain import build_failed_without_results

        reason = build_failed_without_results(
            self._result(1, stdout="[INFO] BUILD FAILURE", stderr="Compilation failure"),
            "maven",
            total=0,
        )

        assert reason is not None
        assert "maven" in reason and "no test results" in reason
        assert "Compilation failure" in reason, reason

    def test_a_failed_build_that_did_report_results_is_left_alone(self) -> None:
        """The control that matters most: Maven exits non-zero when *tests* fail.

        Treating that as a build failure would convert every red suite into a toolchain error and
        lose the failure counts the reports do contain.
        """
        from specweaver.sandbox.language.core.toolchain import build_failed_without_results

        assert (
            build_failed_without_results(
                self._result(1, stdout="Tests run: 1, Failures: 1"), "maven", total=1
            )
            is None
        )

    def test_a_successful_build_with_no_tests_is_a_real_zero(self) -> None:
        """A project with no tests is not an error, and exit 0 says the tool got that far."""
        from specweaver.sandbox.language.core.toolchain import build_failed_without_results

        assert build_failed_without_results(self._result(0), "gradle", total=0) is None
