# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""RustRunner — Cargo/JUnit/SARIF mapping test and lint execution interface."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.commons.enums.dal import DALLevel  # noqa: TC001
from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.language.core.rust.cargo_output import parse_cargo_test
from specweaver.sandbox.language.core.toolchain import (
    did_not_run,
    failed_compile,
    failed_complexity,
    failed_lint,
    failed_tests,
)
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


def _tally_junit(xml_stdout: str) -> tuple[int, int, int, int, list[Any]]:
    """(passed, failed, errors, skipped, failures) from a cargo2junit report.

    A case with no `result` element passed — junitparser only attaches one for a non-success — and
    an unrecognised result type is counted as a pass for the same reason.
    """
    import junitparser

    from specweaver.sandbox.qa_runner.core.interface import TestFailure

    passed = failed = errors = skipped = 0
    failures: list[Any] = []

    xml_str = xml_stdout.strip()
    if not xml_str:
        return passed, failed, errors, skipped, failures

    for suite in junitparser.JUnitXml.fromstring(xml_str):
        for case in suite:
            outcome = getattr(case, "result", None)
            if isinstance(outcome, junitparser.Failure):
                failed += 1
                failures.append(
                    # `nodeid`, not `name`: TestFailure has no `name` field, so this raised
                    # TypeError for every failing Rust test and the bare `except` below reported
                    # a flat `failed=1` instead of the real tally. Pre-existing; surfaced by
                    # moving the loop to module scope where mypy could see it.
                    TestFailure(
                        nodeid=f"{case.classname}::{case.name}",
                        message=outcome.message or "Failed",
                    )
                )
            elif isinstance(outcome, junitparser.Error):
                errors += 1
            elif isinstance(outcome, junitparser.Skipped):
                skipped += 1
            else:
                passed += 1
    return passed, failed, errors, skipped, failures


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

        from specweaver.sandbox.qa_runner.core.interface import TestRunResult

        try:
            start_time = time.time()
            # Cargo's own output, parsed directly. It offers no stable machine-readable form — the
            # JSON libtest format is nightly-only — so asking for one produced a command cargo
            # rejects outright, piped into a converter that was never installed.
            cmd = ["cargo", "test"]

            test_result = self._executor.execute(cmd, timeout_seconds=timeout)
            outcome = parse_cargo_test(test_result.stdout)
            if outcome is None:
                # No summary means no suite ran. `did_not_run` keys on empty stdout, which a cargo
                # compile error does not produce, so the summary is the stronger discriminator here.
                return failed_tests(
                    did_not_run(test_result, "cargo")
                    or f"cargo test reported no suite (exit {test_result.exit_code}): "
                    f"{(test_result.stderr or test_result.stdout).strip()[:200]}"
                )

            return TestRunResult(
                passed=outcome.passed,
                failed=outcome.failed,
                errors=0,
                skipped=outcome.skipped,
                total=outcome.total,
                failures=outcome.failures,
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
            reason = did_not_run(clippy_result, "cargo clippy")
            if reason:
                return failed_lint(reason)

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
            reason = did_not_run(clippy_result, "cargo clippy")
            if reason:
                return failed_complexity(reason, max_complexity)

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

            result = self._executor.execute(cmd)
            reason = did_not_run(result, "cargo")
            if reason:
                return failed_compile(reason)
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
