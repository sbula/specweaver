# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""RustRunner — Cargo/JUnit/SARIF mapping test and lint execution interface."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.commons.enums.dal import DALLevel  # noqa: TC001
from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.qa_runner.core.interface import (
    ArchitectureRunResult,
    QARunnerInterface,
)
from specweaver.workspace.ast.parsers.rust.parsers import parse_clippy_complexity

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.sandbox.qa_runner.core.interface import (
        CompileRunResult,
        ComplexityRunResult,
        DebugRunResult,
        LintRunResult,
        TestRunResult,
    )

logger = logging.getLogger(__name__)


class RustRunner(QARunnerInterface):
    """Test runner bindings for Rust using cargo, cargo2junit, and clippy-sarif."""

    def __init__(self, cwd: Path, executor: SubprocessExecutor | None = None) -> None:
        self._cwd = cwd
        self._executor = executor or SubprocessExecutor(cwd=cwd)

    @property
    def language_name(self) -> str:
        """Canonical language identifier."""
        return "rust"

    def run_tests(
        self,
        target: str,
        kind: str = "unit",
        scope: str = "",
        timeout: int = 120,
        coverage: bool = False,
        coverage_threshold: int = 70,
    ) -> TestRunResult:
        import time

        import junitparser

        from specweaver.sandbox.qa_runner.core.interface import TestFailure, TestRunResult

        try:
            start_time = time.time()
            cmd = ["cargo", "test", "--format=json", "-q"]

            test_result = self._executor.execute(cmd)

            junit_result = self._executor.execute(
                ["cargo2junit"],
                input_text=test_result.stdout,
            )

            passed = 0
            failed = 0
            errors = 0
            skipped = 0
            failures: list[TestFailure] = []

            xml_str = junit_result.stdout.strip()
            if xml_str:
                xml = junitparser.JUnitXml.fromstring(xml_str)
                for suite in xml:
                    for case in suite:
                        if not hasattr(case, "result"):
                            passed += 1
                        elif isinstance(case.result, junitparser.Failure):
                            failed += 1
                            failures.append(
                                TestFailure(
                                    name=f"{case.classname}::{case.name}",
                                    message=case.result.message or "Failed",
                                )
                            )
                        elif isinstance(case.result, junitparser.Error):
                            errors += 1
                        elif isinstance(case.result, junitparser.Skipped):
                            skipped += 1
                        else:
                            passed += 1

            total = passed + failed + errors + skipped
            return TestRunResult(
                passed=passed,
                failed=failed,
                errors=errors,
                skipped=skipped,
                total=total,
                failures=failures,
                duration_seconds=time.time() - start_time,
                coverage_pct=None,
            )
        except Exception:
            return TestRunResult(
                passed=0,
                failed=1,
                errors=0,
                skipped=0,
                total=1,
                failures=[],
                duration_seconds=0.0,
                coverage_pct=None,
            )

    def run_linter(self, target: str, fix: bool = False) -> LintRunResult:
        from specweaver.commons import json
        from specweaver.sandbox.qa_runner.core.interface import LintError, LintRunResult

        try:
            clippy_cmd = ["cargo", "clippy", "--message-format=json"]
            if fix:
                clippy_cmd.insert(2, "--fix")
                clippy_cmd.insert(3, "--allow-staged")

            clippy_result = self._executor.execute(clippy_cmd)

            sarif_result = self._executor.execute(
                ["clippy-sarif"],
                input_text=clippy_result.stdout,
            )

            errors_list = []
            if sarif_result.stdout.strip():
                try:
                    data = json.loads(sarif_result.stdout)
                    runs = data.get("runs", [])
                    for run in runs:
                        for result in run.get("results", []):
                            msg = result.get("message", {}).get("text", "")
                            rule_id = result.get("ruleId", "")

                            for loc in result.get("locations", []):
                                ploc = loc.get("physicalLocation", {})
                                uri = ploc.get("artifactLocation", {}).get("uri", "")
                                line = ploc.get("region", {}).get("startLine", 0)
                                errors_list.append(
                                    LintError(file=uri, line=line, code=rule_id, message=msg)
                                )
                except json.JSONDecodeError:
                    pass

            return LintRunResult(
                error_count=len(errors_list), fixable_count=0, fixed_count=0, errors=errors_list
            )
        except Exception:
            return LintRunResult(error_count=1, fixable_count=0, fixed_count=0, errors=[])

    def run_complexity(self, target: str, max_complexity: int = 10) -> ComplexityRunResult:
        from specweaver.commons import json
        from specweaver.sandbox.qa_runner.core.interface import ComplexityRunResult

        try:
            clippy_cmd = [
                "cargo",
                "clippy",
                "--message-format=json",
                "--",
                "-W",
                "clippy::cognitive_complexity",
            ]

            clippy_result = self._executor.execute(clippy_cmd)

            sarif_result = self._executor.execute(
                ["clippy-sarif"],
                input_text=clippy_result.stdout,
            )

            violations = []
            if sarif_result.stdout.strip():
                try:
                    data = json.loads(sarif_result.stdout)
                    violations.extend(parse_clippy_complexity(data, max_complexity))
                except json.JSONDecodeError:
                    pass

            return ComplexityRunResult(
                violation_count=len(violations),
                max_complexity=max_complexity,
                violations=violations,
            )
        except Exception:
            return ComplexityRunResult(violation_count=1, max_complexity=10, violations=[])

    def run_compiler(self, target: str) -> CompileRunResult:
        from specweaver.sandbox.qa_runner.core.interface import CompileError, CompileRunResult

        try:
            cmd = ["cargo", "build"]
            if target != "src/":
                cmd.extend(["--bin", target.strip("/")])

            self._executor.execute(cmd)
            return CompileRunResult(error_count=0, warning_count=0, errors=[])
        except Exception as e:
            return CompileRunResult(
                error_count=1,
                warning_count=0,
                errors=[
                    CompileError(
                        file="", line=0, column=0, code="", message=str(e), is_warning=False
                    )
                ],
            )

    def run_debugger(self, target: str, entrypoint: str) -> DebugRunResult:
        from specweaver.sandbox.qa_runner.core.interface import DebugRunResult, OutputEvent

        try:
            cmd = ["cargo", "run"]
            result = self._executor.execute(cmd)
            return DebugRunResult(
                exit_code=result.exit_code,
                duration_seconds=result.duration_seconds,
                events=[OutputEvent(category="stdout", output=result.stdout)]
                if result.stdout
                else [],
            )
        except Exception:
            return DebugRunResult(exit_code=1, duration_seconds=0.0, events=[])

    def run_architecture_check(
        self,
        target: str,
        dal_level: DALLevel | None = None,
    ) -> ArchitectureRunResult:
        """Run architectural checks (Deferred to Feature 3.20b)."""
        return ArchitectureRunResult(violation_count=0, violations=[])
