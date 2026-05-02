# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Kotlin test runner using Maven and Gradle."""

from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING

from specweaver.commons import json
from specweaver.commons.enums.dal import DALLevel  # noqa: TC001
from specweaver.core.loom.commons.qa_runner.interface import (
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

logger = logging.getLogger(__name__)


class KotlinRunner(QARunnerInterface):
    """Kotlin compilation, testing, and linting pipeline."""

    def __init__(self, cwd: Path) -> None:
        self._cwd = cwd

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
        tool = self._get_build_tool()

        if tool == "gradle":
            cmd = ["gradlew", "test"]
            if not (self._cwd / "gradlew").exists() and not (self._cwd / "gradlew.bat").exists():
                cmd[0] = "gradle"

            search_path = self._cwd / "build" / "test-results"
            if search_path.exists():
                for stale_xml in search_path.rglob("*.xml"):
                    stale_xml.unlink(missing_ok=True)
        else:
            cmd = ["mvnw", "test"]
            if not (self._cwd / "mvnw").exists() and not (self._cwd / "mvnw.cmd").exists():
                cmd[0] = "mvn"

            search_path = self._cwd / "target" / "surefire-reports"
            if search_path.exists():
                for stale_xml in search_path.rglob("*.xml"):
                    stale_xml.unlink(missing_ok=True)

        subprocess.run(cmd, cwd=self._cwd, capture_output=True, text=True, check=False)

        passed, failed = self._parse_junit_results(search_path)

        return TestRunResult(
            passed=passed,
            failed=failed,
            errors=0,
            skipped=0,
            total=passed + failed,
            failures=[],
            coverage_pct=0.0,
            duration_seconds=0.0,
        )

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

        subprocess.run(cmd, cwd=self._cwd, capture_output=True, check=False)

        if sarif_path.exists():
            try:
                data = json.loads(sarif_path.read_text("utf-8"))
                for run in data.get("runs", []):
                    for result in run.get("results", []):
                        rule_id = result.get("ruleId", "")
                        if "complex" in rule_id.lower():
                            continue

                        msg = result.get("message", {}).get("text", "")
                        for loc in result.get("locations", []):
                            ploc = loc.get("physicalLocation", {})
                            uri = ploc.get("artifactLocation", {}).get("uri", "")
                            line = ploc.get("region", {}).get("startLine", 0)
                            errors.append(
                                LintError(
                                    file=uri,
                                    line=line,
                                    code=rule_id,
                                    message=msg,
                                )
                            )
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

        subprocess.run(cmd, cwd=self._cwd, capture_output=True, check=False)

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

        proc = subprocess.run(cmd, cwd=self._cwd, capture_output=True, text=True, check=False)

        errors: list[CompileError] = []
        if proc.returncode != 0:
            errors.append(
                CompileError(file="", line=0, column=0, code="COMPILE_ERROR", message=proc.stderr)
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

        proc = subprocess.run(cmd, cwd=self._cwd, capture_output=True, text=True, check=False)

        return DebugRunResult(
            exit_code=proc.returncode,
            duration_seconds=0.0,
            events=[
                OutputEvent(category="stdout", output=f"Starting Kotlin debugger on {entrypoint}"),
                OutputEvent(category="stderr", output=proc.stderr[:200]),
            ],
        )

    def run_architecture_check(
        self,
        target: str,
        dal_level: DALLevel | None = None,
    ) -> ArchitectureRunResult:
        """Run architectural checks (Deferred to Feature 3.20b)."""
        return ArchitectureRunResult(violation_count=0, violations=[])
