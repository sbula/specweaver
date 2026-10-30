# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Kotlin test runner using Maven and Gradle.

Implements QARunnerInterface for Kotlin projects.
Delegates subprocess execution to SubprocessExecutor.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

from specweaver.commons.enums.dal import DALLevel  # noqa: TC001
from specweaver.sandbox.language.core.junit_reports import report_search_paths
from specweaver.sandbox.language.core.jvm.runner import JvmRunner
from specweaver.sandbox.language.core.run_targets import build_launcher, jvm_test_args, parse_target
from specweaver.sandbox.qa_runner.core.interface import (
    ArchitectureRunResult,
    DebugRunResult,
    OutputEvent,
)
from specweaver.workspace.ast.parsers.kotlin.parsers import parse_detekt_complexity

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from specweaver.commons.qa import ComplexityViolation

logger = logging.getLogger(__name__)


class KotlinRunner(JvmRunner):
    """Kotlin compilation, testing, and linting pipeline."""

    _BUILD_TOOL_NAME = "the Kotlin build tool"
    _ANALYZER = "detekt"
    _COMPLEXITY_RULES = "complex"

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

    #: Per build tool: where its test reports land.
    _REPORT_DIRS: ClassVar[dict[str, tuple[str, ...]]] = {
        "gradle": ("build", "test-results"),
        "maven": ("target", "surefire-reports"),
    }

    def _test_command(self, target: str) -> tuple[list[str], list[Path]]:
        """The two build tools differ only in where reports land, so that is a table rather than
        two branches."""
        tool = self._get_build_tool()
        filters = jvm_test_args(parse_target(target), "kotlin", tool)
        report_dir = self._REPORT_DIRS[tool]
        launcher = build_launcher(self._cwd, tool)
        # Both places the reports can land: inside the project on a host run, or mounted out to
        # scratch when the sandbox gave the build an overlay workspace it then discarded.
        search_paths = report_search_paths(self._cwd, "/".join(report_dir))
        for path in search_paths:
            self._clear_stale_reports(path)
        return [launcher, "test", *filters], search_paths

    @staticmethod
    def _clear_stale_reports(search_path: Path) -> None:
        """Delete previous reports — the harvest globs whatever it finds, so they would be counted."""
        if not search_path.exists():
            return
        for stale_xml in search_path.rglob("*.xml"):
            stale_xml.unlink(missing_ok=True)

    def _analysis_command(self, tool: str) -> tuple[list[str], Path]:
        if tool == "gradle":
            return [
                build_launcher(self._cwd, "gradle"),
                "detekt",
            ], self._cwd / "build" / "reports" / "detekt" / "detekt.sarif"
        return [
            build_launcher(self._cwd, "maven"),
            "antrun:run@detekt",
        ], self._cwd / "target" / "detekt.sarif"

    def _compile_command(self, tool: str) -> list[str]:
        if tool == "gradle":
            return [build_launcher(self._cwd, "gradle"), "compileKotlin"]
        return [build_launcher(self._cwd, "maven"), "compile"]

    def _complexity_violations(
        self, report: dict[str, Any], max_complexity: int
    ) -> list[ComplexityViolation]:
        return parse_detekt_complexity(report, max_complexity)

    def run_debugger(self, target: str, entrypoint: str) -> DebugRunResult:
        tool = self._get_build_tool()

        if tool == "gradle":
            cmd = [build_launcher(self._cwd, "gradle"), "run", "--debug-jvm"]
        else:
            cmd = [
                build_launcher(self._cwd, "maven"),
                "exec:java",
                f"-Dexec.mainClass={entrypoint}",
            ]

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
        """Report that architectural checks are not implemented for this language.

        It returns a result rather than raising because the QA atom treats an exception as a
        failed step, and the check not existing is not the project's fault. The `note` is not
        optional: without it, this is indistinguishable from a clean verdict.
        """
        return ArchitectureRunResult(
            violation_count=0,
            violations=[],
            note="Kotlin architecture checks are not implemented; no boundary was examined.",
        )
