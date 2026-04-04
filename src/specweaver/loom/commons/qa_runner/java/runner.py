# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Java test runner using Maven and Gradle."""

from __future__ import annotations

import json
import logging
import subprocess
from typing import TYPE_CHECKING

from specweaver.loom.commons.qa_runner.interface import (
    ArchitectureRunResult,
    CompileRunResult,
    ComplexityRunResult,
    ComplexityViolation,
    DebugRunResult,
    LintRunResult,
    QARunnerInterface,
    TestRunResult,
)
from specweaver.loom.commons.qa_runner.java.parsers import parse_pmd_complexity

if TYPE_CHECKING:
    from pathlib import Path


logger = logging.getLogger(__name__)


class JavaRunner(QARunnerInterface):
    """Java compilation, testing, and linting pipeline."""

    def __init__(self, cwd: Path) -> None:
        self._cwd = cwd
        self._build_tool: str | None = None

    def _get_build_tool(self) -> str:
        if self._build_tool is not None:
            return self._build_tool

        gradle_file = self._cwd / "build.gradle"
        maven_file = self._cwd / "pom.xml"

        if gradle_file.exists():
            self._build_tool = "gradle"
        elif maven_file.exists():
            self._build_tool = "maven"
        else:
            self._build_tool = "maven"

        return self._build_tool

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
        passed = 0
        failed = 0
        skipped = 0

        if tool == "gradle":
            cmd = ["gradlew", "test"]
            if not (self._cwd / "gradlew").exists() and not (self._cwd / "gradlew.bat").exists():
                cmd[0] = "gradle"
            for stale_xml in self._cwd.rglob("build/test-results/test/*.xml"):
                stale_xml.unlink(missing_ok=True)
            search_path = self._cwd / "build" / "test-results"
        else:
            cmd = ["mvnw", "test"]
            if not (self._cwd / "mvnw").exists() and not (self._cwd / "mvnw.cmd").exists():
                cmd[0] = "mvn"
            for stale_xml in self._cwd.rglob("target/surefire-reports/*.xml"):
                stale_xml.unlink(missing_ok=True)
            search_path = self._cwd / "target" / "surefire-reports"

        subprocess.run(cmd, cwd=self._cwd, capture_output=True, text=True, check=False)

        import junitparser
        for xml_file in search_path.rglob("*.xml"):
            try:
                xml = junitparser.JUnitXml.fromfile(str(xml_file))
                passed += xml.tests - xml.failures - xml.skipped - xml.errors
                failed += xml.failures + xml.errors
                skipped += xml.skipped
            except Exception:
                pass

        return TestRunResult(
            passed=passed,
            failed=failed,
            errors=0,
            skipped=skipped,
            total=passed + failed + skipped,
            failures=[],
            coverage_pct=None,
        )

    def run_linter(self, target: str, fix: bool = False) -> LintRunResult:
        from specweaver.loom.commons.qa_runner.interface import LintError

        tool = self._get_build_tool()
        errors: list[LintError] = []

        if tool == "gradle":
            cmd = ["gradlew", "pmdMain"]
            if not (self._cwd / "gradlew").exists() and not (self._cwd / "gradlew.bat").exists():
                cmd[0] = "gradle"
            sarif_path = self._cwd / "build" / "reports" / "pmd" / "main.sarif"
        else:
            cmd = ["mvnw", "pmd:pmd", "-Dpmd.format=sarif"]
            if not (self._cwd / "mvnw").exists() and not (self._cwd / "mvnw.cmd").exists():
                cmd[0] = "mvn"
            sarif_path = self._cwd / "target" / "pmd.sarif"

        subprocess.run(cmd, cwd=self._cwd, capture_output=True, check=False)

        if sarif_path.exists():
            try:
                data = json.loads(sarif_path.read_text("utf-8"))
                for run in data.get("runs", []):
                    for result in run.get("results", []):
                        rule_id = result.get("ruleId", "")
                        if "complexity" in rule_id.lower():
                            continue

                        msg = result.get("message", {}).get("text", "")
                        for loc in result.get("locations", []):
                            ploc = loc.get("physicalLocation", {})
                            uri = ploc.get("artifactLocation", {}).get("uri", "")
                            line = ploc.get("region", {}).get("startLine", 0)
                            errors.append(LintError(
                                file=uri,
                                line=line,
                                code=rule_id,
                                message=msg,
                            ))
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
            cmd = ["gradlew", "pmdMain"]
            if not (self._cwd / "gradlew").exists() and not (self._cwd / "gradlew.bat").exists():
                cmd[0] = "gradle"
            sarif_path = self._cwd / "build" / "reports" / "pmd" / "main.sarif"
        else:
            cmd = ["mvnw", "pmd:pmd", "-Dpmd.format=sarif"]
            if not (self._cwd / "mvnw").exists() and not (self._cwd / "mvnw.cmd").exists():
                cmd[0] = "mvn"
            sarif_path = self._cwd / "target" / "pmd.sarif"

        subprocess.run(cmd, cwd=self._cwd, capture_output=True, check=False)

        if sarif_path.exists():
            try:
                data = json.loads(sarif_path.read_text("utf-8"))
                # Hand off parsing explicitly without regex bindings inside the monolithic logic
                violations.extend(parse_pmd_complexity(data, max_complexity))
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
            cmd = ["gradlew", "compileJava"]
            if not (self._cwd / "gradlew").exists() and not (self._cwd / "gradlew.bat").exists():
                cmd[0] = "gradle"
        else:
            cmd = ["mvnw", "compile"]
            if not (self._cwd / "mvnw").exists() and not (self._cwd / "mvnw.cmd").exists():
                cmd[0] = "mvn"

        proc = subprocess.run(cmd, cwd=self._cwd, capture_output=True, text=True, check=False)

        return CompileRunResult(
            error_count=1 if proc.returncode != 0 else 0,
            warning_count=0,
            errors=[],
        )

    def run_debugger(self, target: str, entrypoint: str) -> DebugRunResult:
        tool = self._get_build_tool()
        if tool == "gradle":
            cmd = ["gradlew", "build"]
            if not (self._cwd / "gradlew").exists() and not (self._cwd / "gradlew.bat").exists():
                cmd[0] = "gradle"
        else:
            cmd = ["mvnw", "compile", "exec:java", f"-Dexec.mainClass={entrypoint}"]
            if not (self._cwd / "mvnw").exists() and not (self._cwd / "mvnw.cmd").exists():
                cmd[0] = "mvn"

        proc = subprocess.run(cmd, cwd=self._cwd, capture_output=True, text=True, check=False)

        from specweaver.loom.commons.qa_runner.interface import OutputEvent
        return DebugRunResult(
            exit_code=proc.returncode,
            duration_seconds=0.0,
            events=[OutputEvent(category="stdout", output=x) for x in proc.stdout.splitlines()],
        )

    def run_architecture_check(
        self,
        target: str,
    ) -> ArchitectureRunResult:
        """Run architectural checks (Deferred to Feature 3.20b)."""
        return ArchitectureRunResult(violation_count=0, violations=[])
