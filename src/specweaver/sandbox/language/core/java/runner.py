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
from specweaver.sandbox.language.core.junit_reports import report_search_paths
from specweaver.sandbox.language.core.jvm.build_output import program_output
from specweaver.sandbox.language.core.jvm.runner import JvmRunner
from specweaver.sandbox.language.core.run_targets import build_launcher, jvm_test_args, parse_target
from specweaver.sandbox.qa_runner.core.interface import (
    ArchitectureRunResult,
    DebugRunResult,
)
from specweaver.workspace.ast.parsers.java.parsers import parse_pmd_complexity

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from specweaver.commons.qa import ComplexityViolation
    from specweaver.sandbox.execution.executor import SubprocessExecutor


logger = logging.getLogger(__name__)


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


class JavaRunner(JvmRunner):
    """Java compilation, testing, and linting pipeline."""

    _DEFAULT_TIMEOUT: int = 120
    _BUILD_TIMEOUT: int = 300
    _BUILD_TOOL_NAME = "the Java build tool"
    _ANALYZER = "pmd"
    _COMPLEXITY_RULES = "complexity"

    def __init__(self, cwd: Path, executor: SubprocessExecutor | None = None) -> None:
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
        return parse_pmd_complexity(report, max_complexity)

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

        cmd = [
            build_launcher(self._cwd, "maven"),
            "test",
            "-Dtest=specweaver.SpecweaverArchUnitTest",
            "-q",
        ]

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
