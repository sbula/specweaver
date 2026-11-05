# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Java test runner using Maven and Gradle.

Implements QARunnerInterface for Java projects.
Delegates subprocess execution to SubprocessExecutor.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.sandbox.language.core.junit_reports import report_search_paths
from specweaver.sandbox.language.core.jvm.build_output import program_output
from specweaver.sandbox.language.core.jvm.runner import JvmRunner
from specweaver.sandbox.language.core.run_targets import build_launcher, jvm_test_args, parse_target
from specweaver.sandbox.language.core.sarif import parse_sarif_complexity
from specweaver.sandbox.qa_runner.core.interface import (
    DebugRunResult,
)

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from specweaver.commons.qa import ComplexityViolation
    from specweaver.sandbox.execution.executor import SubprocessExecutor


logger = logging.getLogger(__name__)


class JavaRunner(JvmRunner):
    """Java compilation, testing, and linting pipeline."""

    _DEFAULT_TIMEOUT: int = 120
    _BUILD_TIMEOUT: int = 300
    _BUILD_TOOL_NAME = "the Java build tool"
    _ANALYZER = "pmd"
    _COMPLEXITY_RULES = "complexity"

    def __init__(self, cwd: Path, executor: SubprocessExecutor) -> None:
        super().__init__(cwd, executor)
        self._build_tool: str | None = None

    @property
    def language_name(self) -> str:
        """Canonical language identifier."""
        return "java"

    def _get_build_tool(self) -> str:
        if self._build_tool is not None:
            return self._build_tool

        maven_file = self._cwd / "pom.xml"

        if any((self._cwd / name).exists() for name in ("build.gradle", "build.gradle.kts")):
            self._build_tool = "gradle"
        elif maven_file.exists():
            self._build_tool = "maven"
        else:
            self._build_tool = "maven"

        return self._build_tool

    def _test_command(self, target: str) -> tuple[list[str], list[Path]]:
        tool = self._get_build_tool()
        filters = jvm_test_args(parse_target(target), "java", tool)
        if tool == "gradle":
            cmd = [build_launcher(self._cwd, "gradle"), "test"]
            stale, reports = "build/test-results/test/*.xml", "build/test-results"
        else:
            cmd = [build_launcher(self._cwd, "maven"), "test"]
            stale, reports = "target/surefire-reports/*.xml", "target/surefire-reports"
        for stale_xml in self._cwd.rglob(stale):
            stale_xml.unlink(missing_ok=True)
        return cmd + filters, report_search_paths(self._cwd, reports)

    def _analysis_command(self, tool: str) -> tuple[list[str], Path]:
        if tool == "gradle":
            return [
                build_launcher(self._cwd, "gradle"),
                "pmdMain",
            ], self._cwd / "build" / "reports" / "pmd" / "main.sarif"
        return [
            build_launcher(self._cwd, "maven"),
            "pmd:pmd",
            "-Dpmd.format=sarif",
        ], self._cwd / "target" / "pmd.sarif"

    def _compile_command(self, tool: str) -> list[str]:
        if tool == "gradle":
            return [build_launcher(self._cwd, "gradle"), "compileJava"]
        return [build_launcher(self._cwd, "maven"), "compile"]

    def _complexity_violations(
        self, report: dict[str, Any], max_complexity: int
    ) -> list[ComplexityViolation]:
        return parse_sarif_complexity(
            report,
            max_complexity,
            rule_markers=("complexity", "ncss"),
            drift_hint="Missing compiler version drift?",
        )

    def run_debugger(self, target: str, entrypoint: str) -> DebugRunResult:
        tool = self._get_build_tool()
        if tool == "gradle":
            cmd = [build_launcher(self._cwd, "gradle"), "build"]
        else:
            cmd = [
                build_launcher(self._cwd, "maven"),
                "compile",
                "exec:java",
                f"-Dexec.mainClass={entrypoint}",
            ]

        result = self._executor.execute(cmd, timeout_seconds=self._BUILD_TIMEOUT)

        from specweaver.sandbox.qa_runner.core.interface import OutputEvent

        # The program's own output, not the build log around it. Returning the whole stream buried
        # the one line a program printed under Maven's chatter and the JVM's deprecation warnings.
        printed = program_output(result.stdout)
        return DebugRunResult(
            exit_code=result.exit_code,
            duration_seconds=result.duration_seconds,
            events=[
                OutputEvent(category="stdout", output=line) for line in printed.splitlines() if line
            ],
        )
