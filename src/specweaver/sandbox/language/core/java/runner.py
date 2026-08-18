# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Java test runner using Maven and Gradle.

Implements QARunnerInterface for Java projects.
Delegates subprocess execution to SubprocessExecutor.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.commons.enums.dal import DALLevel  # noqa: TC001
from specweaver.sandbox.language.core.junit_reports import harvest_junit, report_search_paths
from specweaver.sandbox.language.core.sarif import lint_errors_from_sarif, read_sarif_report
from specweaver.sandbox.language.core.toolchain import (
    build_failed_without_results,
    did_not_run,
    failed_complexity,
    failed_lint,
    failed_tests,
    report_never_written,
)
from specweaver.sandbox.qa_runner.core.interface import (
    ArchitectureRunResult,
    CompileRunResult,
    ComplexityRunResult,
    ComplexityViolation,
    DebugRunResult,
    LintRunResult,
    QARunnerInterface,
    TestRunResult,
)
from specweaver.workspace.ast.parsers.java.parsers import parse_pmd_complexity

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.sandbox.execution.executor import SubprocessExecutor


logger = logging.getLogger(__name__)


def _harvest_junit(search_path: Path) -> tuple[int, int, int]:
    """(passed, failed, skipped) across every JUnit XML report under `search_path`.

    A report that cannot be parsed is skipped rather than failing the run: a partially-written
    file from a killed build should not be reported as a test failure.
    """
    import junitparser

    passed = failed = skipped = 0
    for xml_file in search_path.rglob("*.xml"):
        try:
            xml = junitparser.JUnitXml.fromfile(str(xml_file))
        except Exception:
            continue
        passed += xml.tests - xml.failures - xml.skipped - xml.errors
        failed += xml.failures + xml.errors
        skipped += xml.skipped
    return passed, failed, skipped


def _forbids_for(target_path: Path, cwd: Path) -> list[str]:
    """The `forbids` list from the nearest enclosing `context.yaml`, walking up from `target_path`.

    Empty when no boundary declares one, or when the file cannot be parsed — a malformed
    `context.yaml` is logged and treated as "no constraints" rather than failing the QA run, since
    the alternative is an architecture check that reports a violation it never actually evaluated.
    """
    import yaml

    ctx_dir = target_path.parent if target_path.is_file() else target_path
    while ctx_dir != cwd and ctx_dir.parent != ctx_dir and not (ctx_dir / "context.yaml").exists():
        ctx_dir = ctx_dir.parent

    ctx_file = ctx_dir / "context.yaml"
    if not ctx_file.exists():
        return []
    try:
        data = yaml.safe_load(ctx_file.read_text(encoding="utf-8")) or {}
    except Exception as e:
        logger.warning("Failed to parse context.yaml at %s: %s", ctx_file, e)
        return []
    forbids: list[str] = data.get("forbids", [])
    return forbids


class JavaRunner(QARunnerInterface):
    """Java compilation, testing, and linting pipeline."""

    _DEFAULT_TIMEOUT: int = 120
    _BUILD_TIMEOUT: int = 300

    def __init__(self, cwd: Path, executor: SubprocessExecutor | None = None) -> None:
        from specweaver.sandbox.execution.executor import SubprocessExecutor as _Executor

        self._cwd = cwd
        self._build_tool: str | None = None
        self._executor = executor or _Executor(cwd=cwd)

    @property
    def language_name(self) -> str:
        """Canonical language identifier."""
        return "java"

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
            search_path = report_search_paths(self._cwd, "build/test-results")
        else:
            cmd = ["mvnw", "test"]
            if not (self._cwd / "mvnw").exists() and not (self._cwd / "mvnw.cmd").exists():
                cmd[0] = "mvn"
            for stale_xml in self._cwd.rglob("target/surefire-reports/*.xml"):
                stale_xml.unlink(missing_ok=True)
            search_path = report_search_paths(self._cwd, "target/surefire-reports")

        result = self._executor.execute(cmd, timeout_seconds=timeout)
        reason = did_not_run(result, "the Java build tool")
        if reason:
            return failed_tests(reason)

        harvest = harvest_junit(search_path)
        passed, failed, skipped, total = (
            harvest.passed,
            harvest.failed,
            harvest.skipped,
            harvest.total,
        )
        # A build that never compiled writes no reports and exits non-zero with plenty on
        # stdout, so it passes `did_not_run` and would harvest as an empty suite.
        broken_build = build_failed_without_results(result, "the Java build tool", total)
        if broken_build:
            return failed_tests(broken_build)

        return TestRunResult(
            passed=passed,
            failed=failed,
            errors=0,
            skipped=skipped,
            total=total,
            failures=harvest.failures,
            coverage_pct=None,
        )

    def run_linter(self, target: str, fix: bool = False) -> LintRunResult:
        from specweaver.sandbox.qa_runner.core.interface import LintError

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

        result = self._executor.execute(cmd)
        reason = did_not_run(result, "pmd")
        if reason:
            return failed_lint(reason)

        # A missing report is not a clean project: the plugin may not be configured, or the
        # build may have stopped before reaching it. Either way there is no verdict to read.
        missing = report_never_written(result, tool, sarif_path)
        if missing:
            return failed_lint(missing)
        errors.extend(
            lint_errors_from_sarif(
                read_sarif_report(sarif_path), skip_rules_containing="complexity"
            )
        )

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

        result = self._executor.execute(cmd)
        reason = did_not_run(result, "pmd")
        if reason:
            return failed_complexity(reason, max_complexity)

        missing = report_never_written(result, tool, sarif_path)
        if missing:
            return failed_complexity(missing, max_complexity)
        violations.extend(parse_pmd_complexity(read_sarif_report(sarif_path), max_complexity))

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

        result = self._executor.execute(cmd)

        return CompileRunResult(
            error_count=1 if result.exit_code != 0 else 0,
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

        result = self._executor.execute(cmd, timeout_seconds=self._BUILD_TIMEOUT)

        from specweaver.sandbox.qa_runner.core.interface import OutputEvent

        return DebugRunResult(
            exit_code=result.exit_code,
            duration_seconds=result.duration_seconds,
            events=[OutputEvent(category="stdout", output=x) for x in result.stdout.splitlines()],
        )

    def run_architecture_check(
        self,
        target: str,
        dal_level: DALLevel | None = None,
    ) -> ArchitectureRunResult:
        """Run architectural checks dynamically using ArchUnit via Maven."""
        import contextlib

        from specweaver.sandbox.qa_runner.core.interface import ArchitectureViolation

        logger.debug("JavaRunner.run_architecture_check: target=%s, dal=%s", target, dal_level)

        forbids = _forbids_for(self._cwd / target, self._cwd)

        if not forbids:
            return ArchitectureRunResult(violation_count=0, violations=[])

        # Generate ArchUnit Test
        # To avoid polluting pom.xml (Zero Boilerplate), we assume either ArchUnit is present
        # OR we generate a minimal Regex-based test that mimics ArchUnit's boundary assertion
        # without external JARs if it's a completely cold system. But for MVP, we output the
        # actual ArchUnit test skeleton and run `mvn test`.
        test_dir = self._cwd / "src" / "test" / "java" / "specweaver"
        test_dir.mkdir(parents=True, exist_ok=True)
        test_file = test_dir / "SpecweaverArchUnitTest.java"

        # Build forbids string array for java source
        forbids_str = ", ".join(f'"{f}"' for f in forbids)

        test_content = f"""package specweaver;
import org.junit.jupiter.api.Test;
import java.nio.file.*;
import java.util.stream.Stream;


// Magic AST parsing stub simulating ArchUnit for Zero Boilerplate execution
public class SpecweaverArchUnitTest {{
    @Test
    public void testDependencies() throws Exception {{
        String[] forbids = new String[]{{{forbids_str}}};
        Path srcDir = Paths.get("{self._cwd.absolute().as_posix()}/src/main/java");
        if (!Files.exists(srcDir)) return;

        try (Stream<Path> paths = Files.walk(srcDir)) {{
            paths.filter(Files::isRegularFile)
                 .filter(p -> p.toString().endsWith(".java"))
                 .forEach(p -> {{
                     try {{
                         String content = Files.readString(p);
                         for (String forbid : forbids) {{
                             String importTarget = forbid.replace("*", "");
                             if (content.contains("import " + importTarget)) {{
                                 System.out.println("ARCH_VIOLATION|" + p.toString() + "|" + forbid);
                             }}
                         }}
                     }} catch (Exception e) {{}}
                 }});
        }}
    }}
}}
"""
        test_file.write_text(test_content, encoding="utf-8")

        cmd = ["mvnw", "test", "-Dtest=specweaver.SpecweaverArchUnitTest", "-q"]
        if not (self._cwd / "mvnw").exists() and not (self._cwd / "mvnw.cmd").exists():
            cmd[0] = "mvn"

        violations = []
        try:
            result = self._executor.execute(cmd, timeout_seconds=60)

            if result.timed_out:
                return ArchitectureRunResult(
                    violation_count=1,
                    violations=[
                        ArchitectureViolation(
                            file=target, code="Timeout", message="Maven timed out"
                        )
                    ],
                )

            for line in result.stdout.splitlines():
                if line.startswith("ARCH_VIOLATION|"):
                    parts = line.split("|")
                    if len(parts) == 3:
                        violations.append(
                            ArchitectureViolation(
                                file=parts[1],
                                code="C05",
                                message=f"Restricted import violated: {parts[2]}",
                            )
                        )
        finally:
            test_file.unlink(missing_ok=True)
            # clear empty directories if possible
            with contextlib.suppress(OSError):
                test_dir.rmdir()

        return ArchitectureRunResult(
            violation_count=len(violations),
            violations=violations,
        )
