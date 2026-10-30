# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the Java and Kotlin runners share: Maven or Gradle, JUnit reports, a SARIF analyzer, and
the same compiler output.

A JVM runner names its build tool, its test, analysis and compile commands, and how it reads
complexity; the steps around them are here. Each language keeps its own debugger and architecture
check.
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from typing import TYPE_CHECKING, ClassVar

from specweaver.sandbox.language.core.junit_reports import harvest_junit
from specweaver.sandbox.language.core.jvm.build_output import compile_errors
from specweaver.sandbox.language.core.run_targets import TargetError, no_test_ran
from specweaver.sandbox.language.core.sarif import lint_errors_from_sarif, run_sarif_analysis
from specweaver.sandbox.language.core.toolchain import (
    build_failed_without_results,
    did_not_run,
    failed_complexity,
    failed_lint,
    failed_tests,
)
from specweaver.sandbox.qa_runner.core.interface import (
    CompileError,
    CompileRunResult,
    ComplexityRunResult,
    LintRunResult,
    QARunnerInterface,
    TestRunResult,
)

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from specweaver.commons.qa import ComplexityViolation
    from specweaver.sandbox.execution.executor import SubprocessExecutor

logger = logging.getLogger(__name__)


class JvmRunner(QARunnerInterface):
    """Tests, lint, complexity and compile for a Maven or Gradle project."""

    #: How messages name the build tool, e.g. "the Java build tool".
    _BUILD_TOOL_NAME: ClassVar[str]
    #: The SARIF analyzer lint and complexity read ("pmd", "detekt").
    _ANALYZER: ClassVar[str]
    #: Lint skips the rules whose id contains this; complexity reports them.
    _COMPLEXITY_RULES: ClassVar[str]

    def __init__(self, cwd: Path, executor: SubprocessExecutor | None = None) -> None:
        from specweaver.sandbox.execution.executor import SubprocessExecutor as _Executor

        self._cwd = cwd
        self._executor = executor or _Executor(cwd=cwd)

    @abstractmethod
    def _get_build_tool(self) -> str: ...

    @abstractmethod
    def _test_command(self, target: str) -> tuple[list[str], list[Path]]:
        """The test command filtered to `target`, and where its reports land; stale reports are
        deleted first. Raises `TargetError` for a target the build tool cannot run."""

    @abstractmethod
    def _analysis_command(self, tool: str) -> tuple[list[str], Path]:
        """The analyzer run lint and complexity both read, and the SARIF report it writes."""

    @abstractmethod
    def _compile_command(self, tool: str) -> list[str]: ...

    @abstractmethod
    def _complexity_violations(
        self, report: dict[str, Any], max_complexity: int
    ) -> list[ComplexityViolation]: ...

    def run_tests(
        self,
        target: str,
        kind: str = "unit",
        scope: str = "",
        timeout: int = 120,
        coverage: bool = False,
        coverage_threshold: int = 70,
        coverage_source: str = "",
        source: str = "",
    ) -> TestRunResult:
        try:
            cmd, search_paths = self._test_command(target)
        except TargetError as exc:
            return failed_tests(no_test_ran(target, str(exc)))
        result = self._executor.execute(cmd, timeout_seconds=timeout)
        reason = did_not_run(result, self._BUILD_TOOL_NAME)
        if reason:
            return failed_tests(reason)

        harvest = harvest_junit(search_paths)
        # A build that never compiled writes no reports and exits non-zero with plenty on
        # stdout, so it passes `did_not_run` and would harvest as an empty suite.
        if not harvest.total:
            broken_build = build_failed_without_results(
                result, self._BUILD_TOOL_NAME, harvest.total
            )
            return failed_tests(no_test_ran(target, broken_build or ""))

        return TestRunResult(
            passed=harvest.passed,
            failed=harvest.failed,
            errors=0,
            skipped=harvest.skipped,
            total=harvest.total,
            failures=harvest.failures,
            coverage_pct=None,
        )

    def _analysis(self) -> dict[str, Any] | str:
        """Today's SARIF report, or why there is none."""
        tool = self._get_build_tool()
        cmd, report = self._analysis_command(tool)
        return run_sarif_analysis(
            self._executor, cmd, report, analyzer=self._ANALYZER, build_tool=tool
        )

    def run_linter(self, target: str, fix: bool = False) -> LintRunResult:
        read = self._analysis()
        if isinstance(read, str):
            return failed_lint(read)
        errors = lint_errors_from_sarif(read, skip_rules_containing=self._COMPLEXITY_RULES)
        return LintRunResult(
            error_count=len(errors),
            fixable_count=0,
            fixed_count=0,
            errors=errors,
        )

    def run_complexity(self, target: str, max_complexity: int = 10) -> ComplexityRunResult:
        read = self._analysis()
        if isinstance(read, str):
            return failed_complexity(read, max_complexity)
        violations = self._complexity_violations(read, max_complexity)
        return ComplexityRunResult(
            violation_count=len(violations),
            max_complexity=max_complexity,
            violations=violations,
        )

    def run_compiler(self, target: str) -> CompileRunResult:
        cmd = self._compile_command(self._get_build_tool())
        result = self._executor.execute(cmd)
        # The count alone said a build failed, which the exit code already said. These carry the
        # file, line and message, which is the part a caller can act on. Gradle writes Kotlin's
        # diagnostics to stderr, Maven to stdout.
        diagnostics = [
            CompileError(
                file=d.file,
                line=d.line,
                column=d.column,
                code="",
                message=d.message,
                is_warning=False,
            )
            for d in compile_errors(f"{result.stdout}\n{result.stderr}")
        ]
        if result.exit_code != 0 and not diagnostics:
            # Failed without naming a location — a missing toolchain, a bad goal, a plugin error.
            diagnostics = [
                CompileError(
                    file="<toolchain>",
                    line=0,
                    column=0,
                    code="BuildFailed",
                    message=(
                        f"{cmd[0]} exited {result.exit_code} without a compiler diagnostic: "
                        f"{(result.stderr or result.stdout or '').strip()[-200:]}"
                    ),
                    is_warning=False,
                )
            ]
        return CompileRunResult(error_count=len(diagnostics), warning_count=0, errors=diagnostics)
