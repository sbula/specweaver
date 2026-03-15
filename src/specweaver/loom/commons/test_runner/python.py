# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Python test runner — pytest + ruff implementation.

Implements TestRunnerInterface for Python projects.
Uses subprocess to run pytest (tests) and ruff (linting).
"""

from __future__ import annotations

import contextlib
import json
import re
import subprocess
import time
from typing import TYPE_CHECKING

from specweaver.loom.commons.test_runner.interface import (
    ComplexityRunResult,
    ComplexityViolation,
    LintError,
    LintRunResult,
    TestFailure,
    TestRunnerInterface,
    TestRunResult,
)

if TYPE_CHECKING:
    from pathlib import Path


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


def _parse_pytest_output(stdout: str) -> dict:
    """Parse pytest --tb=short -q output into structured data."""
    result: dict = {
        "passed": 0, "failed": 0, "errors": 0, "skipped": 0,
        "total": 0, "duration": 0.0, "failures": [], "coverage_pct": None,
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
# PythonTestRunner
# ---------------------------------------------------------------------------


class PythonTestRunner(TestRunnerInterface):
    """Python test runner using pytest and ruff.

    Args:
        cwd: Project root directory.
    """

    def __init__(self, cwd: Path) -> None:
        self._cwd = cwd

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

        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self._cwd),
            )
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            return TestRunResult(
                passed=0, failed=0, errors=1, skipped=0, total=1,
                failures=[TestFailure(
                    nodeid="<timeout>",
                    message=f"Test execution timed out after {timeout}s",
                )],
                duration_seconds=elapsed,
            )

        elapsed = time.monotonic() - start
        parsed = _parse_pytest_output(proc.stdout)

        return TestRunResult(
            passed=parsed["passed"],
            failed=parsed["failed"],
            errors=parsed["errors"],
            skipped=parsed["skipped"],
            total=parsed["total"],
            failures=parsed["failures"],
            coverage_pct=parsed["coverage_pct"],
            duration_seconds=parsed.get("duration", elapsed),
        )

    def run_linter(
        self,
        target: str,
        fix: bool = False,
    ) -> LintRunResult:
        """Run ruff linter with optional auto-fix."""
        fixed_count = 0

        # If fix=True, run ruff format first, then ruff check --fix
        if fix:
            with contextlib.suppress(subprocess.TimeoutExpired):
                subprocess.run(
                    ["python", "-m", "ruff", "format", target],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=str(self._cwd),
                )

            try:
                fix_result = subprocess.run(
                    ["python", "-m", "ruff", "check", target, "--fix", "--output-format=json"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=str(self._cwd),
                )
                # After fix, count remaining issues
                fix_data = self._parse_ruff_json(fix_result.stdout)
                fixed_count = len(fix_data.get("fixed", []))
            except subprocess.TimeoutExpired:
                pass

        # Run final check to get current state
        try:
            proc = subprocess.run(
                ["python", "-m", "ruff", "check", target, "--output-format=json"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(self._cwd),
            )
        except subprocess.TimeoutExpired:
            return LintRunResult(error_count=0, fixable_count=0, fixed_count=0, errors=[])

        return self._build_lint_result(proc.stdout, fixed_count)

    def _parse_ruff_json(self, stdout: str) -> dict:
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
            errors.append(LintError(
                file=err.get("filename", ""),
                line=loc.get("row", 0),
                code=err.get("code", ""),
                message=err.get("message", ""),
            ))
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
        try:
            proc = subprocess.run(
                [
                    "python", "-m", "ruff", "check", target,
                    "--select", "C90",
                    f"--config=lint.mccabe.max-complexity={max_complexity}",
                    "--output-format=json",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(self._cwd),
            )
        except subprocess.TimeoutExpired:
            return ComplexityRunResult(
                violation_count=0,
                max_complexity=max_complexity,
            )

        return self._build_complexity_result(proc.stdout, max_complexity)

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
            message = err.get("message", "")
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

            violations.append(ComplexityViolation(
                file=err.get("filename", ""),
                line=loc.get("row", 0),
                function=func_name,
                complexity=complexity,
                message=message,
            ))

        return ComplexityRunResult(
            violation_count=len(violations),
            max_complexity=max_complexity,
            violations=violations,
        )
