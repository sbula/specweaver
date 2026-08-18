# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Kotlin test runner using Maven and Gradle.

Implements QARunnerInterface for Kotlin projects.
Delegates subprocess execution to SubprocessExecutor.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

from specweaver.commons import json
from specweaver.commons.enums.dal import DALLevel  # noqa: TC001
from specweaver.sandbox.language.core.junit_reports import harvest_junit, report_search_paths
from specweaver.sandbox.language.core.sarif import lint_errors_from_sarif
from specweaver.sandbox.language.core.toolchain import (
    build_failed_without_results,
    did_not_run,
    failed_complexity,
    failed_lint,
    failed_tests,
)
from specweaver.sandbox.qa_runner.core.interface import (
    ArchitectureRunResult,
    CompileError,
    CompileRunResult,
    ComplexityRunResult,
    ComplexityViolation,
    DebugRunResult,
    LintError,
    LintRunResult,
    OutputEvent,
    QARunnerInterface,
    TestRunResult,
)
from specweaver.workspace.ast.parsers.kotlin.parsers import parse_detekt_complexity

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.sandbox.execution.executor import SubprocessExecutor

logger = logging.getLogger(__name__)


class KotlinRunner(QARunnerInterface):
    """Kotlin compilation, testing, and linting pipeline."""

    def __init__(self, cwd: Path, executor: SubprocessExecutor | None = None) -> None:
        from specweaver.sandbox.execution.executor import SubprocessExecutor as _Executor

        self._cwd = cwd
        self._executor = executor or _Executor(cwd=cwd)

    @property
    def language_name(self) -> str:
        """Canonical language identifier."""
        return "kotlin"

    def _get_build_tool(self) -> str:
        if (self._cwd / "build.gradle").exists() or (self._cwd / "build.gradle.kts").exists():
            return "gradle"
        if (self._cwd / "pom.xml").exists():
            return "maven"
        return "gradle"

    def run_tests(
        self,
        target: str,
        kind: str = "unit",
        scope: str = "",
        timeout: int = 120,
        coverage: bool = False,
        coverage_threshold: int = 70,
    ) -> TestRunResult:
        cmd, search_path = self._test_command()
        result = self._executor.execute(cmd, timeout_seconds=timeout)
        reason = did_not_run(result, "the Kotlin build tool")
        if reason:
            return failed_tests(reason)

        harvest = harvest_junit(search_path)
        # A compile failure exits non-zero, prints freely, and leaves the report directory
        # empty — so it passes `did_not_run` and would harvest as an empty suite.
        broken_build = build_failed_without_results(result, "the Kotlin build tool", harvest.total)
        if broken_build:
            return failed_tests(broken_build)

        return TestRunResult(
            passed=harvest.passed,
            failed=harvest.failed,
            errors=0,
            skipped=harvest.skipped,
            total=harvest.total,
            failures=harvest.failures,
            coverage_pct=0.0,
            duration_seconds=0.0,
        )

    #: Per build tool: the wrapper script, its fallback on PATH, the goal, and where reports land.
    _TEST_INVOCATIONS: ClassVar[dict[str, tuple[tuple[str, ...], str, str, tuple[str, ...]]]] = {
        "gradle": (("gradlew", "gradlew.bat"), "gradle", "test", ("build", "test-results")),
        "maven": (("mvnw", "mvnw.cmd"), "mvn", "test", ("target", "surefire-reports")),
    }

    def _test_command(self) -> tuple[list[str], list[Path]]:
        """The test command for this project's build tool, and where its reports will land.

        The two build tools differed only in four values, so they are a table rather than two
        branches — which is what took this past the complexity ceiling once a toolchain guard was
        added above it.
        """
        wrappers, fallback, goal, report_dir = self._TEST_INVOCATIONS[
            "gradle" if self._get_build_tool() == "gradle" else "maven"
        ]
        launcher = wrappers[0] if any((self._cwd / w).exists() for w in wrappers) else fallback
        # Both places the reports can land: inside the project on a host run, or mounted out to
        # scratch when the sandbox gave the build an overlay workspace it then discarded.
        search_paths = report_search_paths(self._cwd, "/".join(report_dir))
        for path in search_paths:
            self._clear_stale_reports(path)
        return [launcher, goal], search_paths

    @staticmethod
    def _clear_stale_reports(search_path: Path) -> None:
        """Delete previous reports — the harvest globs whatever it finds, so they would be counted."""
        if not search_path.exists():
            return
        for stale_xml in search_path.rglob("*.xml"):
            stale_xml.unlink(missing_ok=True)

    def _parse_junit_results(self, search_path: Path) -> tuple[int, int]:
        import junitparser

        passed = 0
        failed = 0

        if search_path.exists():
            for xml_file in search_path.rglob("*.xml"):
                try:
                    xml = junitparser.JUnitXml.fromfile(str(xml_file))
                    failed += xml.failures + xml.errors
                    passed += xml.tests - (xml.failures + xml.errors + xml.skipped)
                except Exception:
                    pass
        return passed, failed

    def run_linter(self, target: str, fix: bool = False) -> LintRunResult:
        tool = self._get_build_tool()
        errors: list[LintError] = []

        if tool == "gradle":
            cmd = ["gradlew", "detekt"]
            if not (self._cwd / "gradlew").exists() and not (self._cwd / "gradlew.bat").exists():
                cmd[0] = "gradle"
            sarif_path = self._cwd / "build" / "reports" / "detekt" / "detekt.sarif"
        else:
            cmd = ["mvnw", "antrun:run@detekt"]
            if not (self._cwd / "mvnw").exists() and not (self._cwd / "mvnw.cmd").exists():
                cmd[0] = "mvn"
            sarif_path = self._cwd / "target" / "detekt.sarif"

        result = self._executor.execute(cmd)
        reason = did_not_run(result, "detekt")
        if reason:
            return failed_lint(reason)

        if sarif_path.exists():
            try:
                data = json.loads(sarif_path.read_text("utf-8"))
                errors.extend(lint_errors_from_sarif(data, skip_rules_containing="complex"))
            except json.JSONDecodeError:
                pass

        return LintRunResult(
            error_count=len(errors),
            fixable_count=0,
            fixed_count=0,
            errors=errors,
        )

    def run_complexity(self, target: str, max_complexity: int = 10) -> ComplexityRunResult:
        tool = self._get_build_tool()
        violations: list[ComplexityViolation] = []

        if tool == "gradle":
            cmd = ["gradlew", "detekt"]
            if not (self._cwd / "gradlew").exists() and not (self._cwd / "gradlew.bat").exists():
                cmd[0] = "gradle"
            sarif_path = self._cwd / "build" / "reports" / "detekt" / "detekt.sarif"
        else:
            cmd = ["mvnw", "antrun:run@detekt"]
            if not (self._cwd / "mvnw").exists() and not (self._cwd / "mvnw.cmd").exists():
                cmd[0] = "mvn"
            sarif_path = self._cwd / "target" / "detekt.sarif"

        result = self._executor.execute(cmd)
        reason = did_not_run(result, "detekt")
        if reason:
            return failed_complexity(reason, max_complexity)

        if sarif_path.exists():
            try:
                data = json.loads(sarif_path.read_text("utf-8"))
                violations.extend(parse_detekt_complexity(data, max_complexity))
            except json.JSONDecodeError:
                pass

        return ComplexityRunResult(
            violation_count=len(violations),
            max_complexity=max_complexity,
            violations=violations,
        )

    def run_compiler(self, target: str) -> CompileRunResult:
        tool = self._get_build_tool()

        if tool == "gradle":
            cmd = ["gradlew", "compileKotlin"]
            if not (self._cwd / "gradlew").exists() and not (self._cwd / "gradlew.bat").exists():
                cmd[0] = "gradle"
        else:
            cmd = ["mvnw", "compile"]
            if not (self._cwd / "mvnw").exists() and not (self._cwd / "mvnw.cmd").exists():
                cmd[0] = "mvn"

        result = self._executor.execute(cmd)

        errors: list[CompileError] = []
        if result.exit_code != 0:
            errors.append(
                CompileError(file="", line=0, column=0, code="COMPILE_ERROR", message=result.stderr)
            )

        return CompileRunResult(
            error_count=len(errors),
            warning_count=0,
            errors=errors,
        )

    def run_debugger(self, target: str, entrypoint: str) -> DebugRunResult:
        tool = self._get_build_tool()

        if tool == "gradle":
            cmd = ["gradlew", "run", "--debug-jvm"]
            if not (self._cwd / "gradlew").exists() and not (self._cwd / "gradlew.bat").exists():
                cmd[0] = "gradle"
        else:
            cmd = ["mvnw", "exec:java", f"-Dexec.mainClass={entrypoint}"]
            if not (self._cwd / "mvnw").exists() and not (self._cwd / "mvnw.cmd").exists():
                cmd[0] = "mvn"

        result = self._executor.execute(cmd, timeout_seconds=300)

        return DebugRunResult(
            exit_code=result.exit_code,
            duration_seconds=result.duration_seconds,
            events=[
                OutputEvent(category="stdout", output=f"Starting Kotlin debugger on {entrypoint}"),
                OutputEvent(category="stderr", output=result.stderr[:200]),
            ],
        )

    def run_architecture_check(
        self,
        target: str,
        dal_level: DALLevel | None = None,
    ) -> ArchitectureRunResult:
        """Run architectural checks (Deferred to Feature 3.20b)."""
        return ArchitectureRunResult(violation_count=0, violations=[])
