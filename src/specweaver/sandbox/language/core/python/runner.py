# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Python test runner — pytest + ruff implementation.

Implements QARunnerInterface for Python projects.
Delegates subprocess execution to SubprocessExecutor.
"""

from __future__ import annotations

import logging
import re
import shlex
import shutil
import sys
from typing import TYPE_CHECKING, TypedDict

from specweaver.commons import json
from specweaver.commons.enums.dal import DALLevel  # noqa: TC001
from specweaver.sandbox.qa_runner.core.interface import (
    ArchitectureRunResult,
    ArchitectureViolation,
    CompileRunResult,
    ComplexityRunResult,
    ComplexityViolation,
    DebugRunResult,
    LintError,
    LintRunResult,
    OutputEvent,
    QARunnerInterface,
    TestFailure,
    TestRunResult,
)

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.sandbox.execution.executor import SubprocessExecutor

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

# Matches pytest summary lines like "5 passed in 0.50s" or "3 passed, 2 failed in 1.20s"
_SUMMARY_RE = re.compile(
    r"(?:(\d+)\s+passed)?"
    r"(?:,?\s*(\d+)\s+failed)?"
    r"(?:,?\s*(\d+)\s+error)?"
    r"(?:,?\s*(\d+)\s+skipped)?"
    r"\s+in\s+([\d.]+)s",
)

# Matches "FAILED tests/test_foo.py::test_bar - <message>"
_FAILURE_RE = re.compile(r"FAILED\s+(\S+)\s*-\s*(.*)")

# Matches "TOTAL  100  15  85%"
_COVERAGE_RE = re.compile(r"TOTAL\s+\d+\s+\d+\s+(\d+)%")


class _ParsedOutput(TypedDict):
    passed: int
    failed: int
    errors: int
    skipped: int
    total: int
    duration: float
    failures: list[TestFailure]
    coverage_pct: float | None


def _parse_pytest_output(stdout: str) -> _ParsedOutput:
    """Parse pytest --tb=short -q output into structured data."""
    result: _ParsedOutput = {
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "total": 0,
        "duration": 0.0,
        "failures": [],
        "coverage_pct": None,
    }

    # Parse summary line
    for match in _SUMMARY_RE.finditer(stdout):
        result["passed"] = int(match.group(1) or 0)
        result["failed"] = int(match.group(2) or 0)
        result["errors"] = int(match.group(3) or 0)
        result["skipped"] = int(match.group(4) or 0)
        result["duration"] = float(match.group(5))

    result["total"] = result["passed"] + result["failed"] + result["errors"] + result["skipped"]

    # Parse failure lines
    for match in _FAILURE_RE.finditer(stdout):
        result["failures"].append(
            TestFailure(nodeid=match.group(1), message=match.group(2).strip()),
        )

    # Parse coverage
    cov_match = _COVERAGE_RE.search(stdout)
    if cov_match:
        result["coverage_pct"] = float(cov_match.group(1))

    return result


# ---------------------------------------------------------------------------
# PythonQARunner
# ---------------------------------------------------------------------------


class PythonQARunner(QARunnerInterface):
    """Python test runner using pytest and ruff.

    Delegates all subprocess execution to SubprocessExecutor for unified
    timeout handling, credential stripping, and resource limits.

    Args:
        cwd: Project root directory.
        executor: Optional SubprocessExecutor instance (DI). Creates one from cwd if None.
    """

    _DEFAULT_TIMEOUT: int = 120
    _BUILD_TIMEOUT: int = 300

    def __init__(self, cwd: Path, executor: SubprocessExecutor | None = None) -> None:
        from specweaver.sandbox.execution.executor import SubprocessExecutor as _Executor

        self._cwd = cwd
        self._executor = executor or _Executor(cwd=cwd)

    @property
    def language_name(self) -> str:
        """Canonical language identifier."""
        return "python"

    def run_tests(
        self,
        target: str,
        kind: str = "unit",
        scope: str = "",
        timeout: int = 120,
        coverage: bool = False,
        coverage_threshold: int = 70,
    ) -> TestRunResult:
        """Run pytest with the given parameters."""
        logger.debug(
            "PythonQARunner.run_tests: target=%s kind=%s scope=%s timeout=%d coverage=%s",
            target,
            kind,
            scope,
            timeout,
            coverage,
        )
        cmd = ["python", "-m", "pytest", target, "--tb=short", "-q"]

        # Add marker filter
        if kind:
            cmd.extend(["-m", kind])

        # Add scope filter
        if scope:
            cmd.extend(["-k", scope])

        # Add coverage
        if coverage:
            cmd.extend(["--cov", target, "--cov-report", "term"])

        result = self._executor.execute(cmd, timeout_seconds=timeout)

        if result.timed_out:
            logger.warning(
                "PythonQARunner: pytest timed out after %ds (target=%s)", timeout, target
            )
            return TestRunResult(
                passed=0,
                failed=0,
                errors=1,
                skipped=0,
                total=1,
                failures=[
                    TestFailure(
                        nodeid="<timeout>",
                        message=f"Test execution timed out after {timeout}s",
                    )
                ],
                duration_seconds=result.duration_seconds,
            )

        parsed = _parse_pytest_output(result.stdout)
        logger.info(
            "PythonQARunner: tests complete — passed=%d failed=%d errors=%d skipped=%d (%.2fs)",
            parsed["passed"],
            parsed["failed"],
            parsed["errors"],
            parsed["skipped"],
            result.duration_seconds,
        )

        return TestRunResult(
            passed=parsed["passed"],
            failed=parsed["failed"],
            errors=parsed["errors"],
            skipped=parsed["skipped"],
            total=parsed["total"],
            failures=parsed["failures"],
            coverage_pct=parsed["coverage_pct"],
            duration_seconds=parsed.get("duration", result.duration_seconds),
        )

    def run_linter(
        self,
        target: str,
        fix: bool = False,
    ) -> LintRunResult:
        """Run ruff linter with optional auto-fix."""
        logger.debug("PythonQARunner.run_linter: target=%s fix=%s", target, fix)
        fixed_count = 0

        # If fix=True, run ruff format first, then ruff check --fix
        if fix:
            self._executor.execute(
                ["python", "-m", "ruff", "format", target],
                timeout_seconds=self._DEFAULT_TIMEOUT,
            )
            # Ignore timeout on format — best-effort

            fix_result = self._executor.execute(
                ["python", "-m", "ruff", "check", target, "--fix", "--output-format=json"],
                timeout_seconds=self._DEFAULT_TIMEOUT,
            )
            if not fix_result.timed_out:
                fix_data = self._parse_ruff_json(fix_result.stdout)
                fixed_count = len(fix_data.get("fixed", []))

        # Run final check to get current state
        result = self._executor.execute(
            ["python", "-m", "ruff", "check", target, "--output-format=json"],
            timeout_seconds=self._DEFAULT_TIMEOUT,
        )
        if result.timed_out:
            logger.warning("PythonQARunner: ruff linting timed out (target=%s)", target)
            return LintRunResult(error_count=0, fixable_count=0, fixed_count=0, errors=[])

        return self._build_lint_result(result.stdout, fixed_count)

    def _parse_ruff_json(self, stdout: str) -> dict[str, list[dict[str, object]]]:
        """Parse ruff --output-format=json output."""
        try:
            data = json.loads(stdout)
            return {"errors": data if isinstance(data, list) else []}
        except (json.JSONDecodeError, TypeError):
            return {"errors": []}

    def _build_lint_result(self, stdout: str, fixed_count: int) -> LintRunResult:
        """Build LintRunResult from ruff JSON output."""
        parsed = self._parse_ruff_json(stdout)
        raw_errors = parsed.get("errors", [])

        errors: list[LintError] = []
        fixable_count = 0

        for err in raw_errors:
            loc = err.get("location", {})
            loc_dict = loc if isinstance(loc, dict) else {}
            errors.append(
                LintError(
                    file=str(err.get("filename", "")),
                    line=int(str(loc_dict.get("row", 0))),
                    code=str(err.get("code", "")),
                    message=str(err.get("message", "")),
                )
            )
            if err.get("fix"):
                fixable_count += 1

        return LintRunResult(
            error_count=len(errors),
            fixable_count=fixable_count,
            fixed_count=fixed_count,
            errors=errors,
        )

    def run_complexity(
        self,
        target: str,
        max_complexity: int = 10,
    ) -> ComplexityRunResult:
        """Run complexity check via ruff --select C90.

        Uses the ruff C901 rule with a configurable threshold.
        """
        result = self._executor.execute(
            [
                "python",
                "-m",
                "ruff",
                "check",
                target,
                "--select",
                "C90",
                f"--config=lint.mccabe.max-complexity={max_complexity}",
                "--output-format=json",
            ],
            timeout_seconds=self._DEFAULT_TIMEOUT,
        )
        if result.timed_out:
            logger.warning("PythonQARunner: complexity check timed out (target=%s)", target)
            return ComplexityRunResult(
                violation_count=0,
                max_complexity=max_complexity,
            )

        return self._build_complexity_result(result.stdout, max_complexity)

    def _build_complexity_result(
        self,
        stdout: str,
        max_complexity: int,
    ) -> ComplexityRunResult:
        """Build ComplexityRunResult from ruff --select C90 JSON output."""
        parsed = self._parse_ruff_json(stdout)
        raw_errors = parsed.get("errors", [])

        violations: list[ComplexityViolation] = []
        for err in raw_errors:
            loc = err.get("location", {})
            message = str(err.get("message", ""))
            # Extract complexity score from ruff message like:
            # "`func` is too complex (12 > 10)"
            func_name = ""
            complexity = 0
            if "`" in message:
                func_name = message.split("`")[1] if "`" in message else ""
            # Parse "(N > M)" pattern
            match = re.search(r"\((\d+)", message)
            if match:
                complexity = int(match.group(1))

            loc_dict = loc if isinstance(loc, dict) else {}
            violations.append(
                ComplexityViolation(
                    file=str(err.get("filename", "")),
                    line=int(str(loc_dict.get("row", 0))),
                    function=func_name,
                    complexity=complexity,
                    message=message,
                )
            )

        return ComplexityRunResult(
            violation_count=len(violations),
            max_complexity=max_complexity,
            violations=violations,
        )

    def run_compiler(
        self,
        target: str,
    ) -> CompileRunResult:
        """Run compilation/build and return structured results (Python is a no-op)."""
        return CompileRunResult(error_count=0, warning_count=0, errors=[])

    def run_debugger(
        self,
        target: str,
        entrypoint: str,
    ) -> DebugRunResult:
        """Execute a process and stream runtime outputs using DAP OutputEvents."""
        cmd = [sys.executable, entrypoint]
        logger.debug("Running Python debugger wrapper: %s", shlex.join(cmd))

        result = self._executor.execute(cmd, timeout_seconds=self._BUILD_TIMEOUT)

        if result.timed_out:
            return DebugRunResult(
                exit_code=124,
                duration_seconds=result.duration_seconds,
                events=[OutputEvent(category="stderr", output="Timeout expired")],
            )

        return DebugRunResult(
            exit_code=result.exit_code,
            duration_seconds=result.duration_seconds,
            events=result.events,
        )

    def run_architecture_check(
        self,
        target: str,
        dal_level: DALLevel | None = None,
    ) -> ArchitectureRunResult:
        """Run architectural boundary checks via tach + context.yaml forbids.

        Combines two checks:
        1. Global tach boundary check (existing behavior)
        2. Per-file context.yaml forbids check (new — parity with TS/Java)

        Args:
            target: File or directory to check (relative to cwd).
            dal_level: Active DAL for the target boundary.
        """
        logger.debug(
            "PythonQARunner.run_architecture_check: target=%s, dal=%s", target, dal_level
        )

        target_path = self._cwd / target

        # --- Phase 1: context.yaml forbids check ---
        from specweaver.sandbox.language.core.python.forbids_checker import (
            check_file_forbids,
        )

        forbids_violations = check_file_forbids(target_path, self._cwd)

        # --- Phase 2: tach boundary check (existing behavior) ---
        tach_result = self._run_tach_check()

        # --- Merge results ---
        all_violations = forbids_violations + tach_result.violations
        return ArchitectureRunResult(
            violation_count=len(all_violations),
            violations=all_violations,
        )

    def _run_tach_check(self) -> ArchitectureRunResult:
        """Run global tach boundary check (extracted from original method)."""
        # H-1 / RED-1.2: Pre-check tool existence before calling executor
        if not shutil.which("tach"):
            logger.warning("PythonQARunner: tach not found")
            return ArchitectureRunResult(
                violation_count=1,
                violations=[
                    ArchitectureViolation(
                        file="<validation_engine>",
                        code="FileNotFoundError",
                        message="Tach architectural linter is not installed or not found in PATH.",
                    )
                ],
            )

        result = self._executor.execute(
            ["python", "-m", "tach", "check", "--output", "json"],
            timeout_seconds=self._DEFAULT_TIMEOUT,
        )

        if result.stderr:
            logger.debug("PythonQARunner: tach check stderr: %s", result.stderr)

        if result.timed_out:
            logger.warning("PythonQARunner: tach check timed out")
            return ArchitectureRunResult(
                violation_count=1,
                violations=[
                    ArchitectureViolation(
                        file="<validation_engine>",
                        code="TimeoutExpired",
                        message="Architecture check timed out while executing tach.",
                    )
                ],
            )

        return self._build_architecture_result(result.stdout)

    def _build_architecture_result(self, stdout: str) -> ArchitectureRunResult:
        """Build ArchitectureRunResult from tach check JSON output."""
        if not stdout.strip() or stdout.strip() == "[]":
            return ArchitectureRunResult(violation_count=0, violations=[])

        try:
            data = json.loads(stdout)
            if not isinstance(data, list):
                # Valid tach error JSON is a list of violation objects
                return ArchitectureRunResult(
                    violation_count=1,
                    violations=[
                        ArchitectureViolation(
                            file="<validation_engine>",
                            code="InvalidOutput",
                            message="Tach output is not a valid JSON list of violations.",
                        )
                    ],
                )
        except (json.JSONDecodeError, TypeError) as e:
            return ArchitectureRunResult(
                violation_count=1,
                violations=[
                    ArchitectureViolation(
                        file="<validation_engine>",
                        code="JSONDecodeError",
                        message=f"Failed to decode tach JSON output: {e}",
                    )
                ],
            )

        violations: list[ArchitectureViolation] = []
        for item in data:
            located = item.get("Located", {})
            file_path = located.get("file_path", "")
            details = located.get("details", {})
            code_block = details.get("Code", {})

            # The structure for undeclared dependency is Code -> UndeclaredDependency -> ...
            ud = code_block.get("UndeclaredDependency")
            if ud:
                dependency = ud.get("dependency", "")
                usage_module = ud.get("usage_module", "")
                definition_module = ud.get("definition_module", "")
                msg = f"Module '{usage_module}' cannot import '{dependency}' from '{definition_module}'"

                violations.append(
                    ArchitectureViolation(
                        file=str(file_path),
                        code="UndeclaredDependency",
                        message=msg,
                    )
                )

        return ArchitectureRunResult(
            violation_count=len(violations),
            violations=violations,
        )
