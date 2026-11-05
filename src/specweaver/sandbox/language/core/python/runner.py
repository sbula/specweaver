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
import sys
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from specweaver.commons import json
from specweaver.sandbox.execution.container_executor import (
    ContainerEngineUnavailableError,
    ContainerSubprocessExecutor,
)
from specweaver.sandbox.language.core.python.toolchain_absence import (
    supplied_note as _supplied_note,
)
from specweaver.sandbox.language.core.python.toolchain_absence import why_it_did_not_run
from specweaver.sandbox.language.core.run_targets import no_test_ran, parse_target
from specweaver.sandbox.language.core.toolchain import (
    failed_complexity,
    failed_lint,
    timed_out,
)
from specweaver.sandbox.qa_runner.core.interface import (
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
# Parsing helpers live in pytest_output.py. Re-exported here for existing importers.
# ---------------------------------------------------------------------------

from specweaver.sandbox.language.core.python.pytest_output import (  # noqa: E402
    _parse_pytest_output,
    file_coverage,
)

# ---------------------------------------------------------------------------
# PythonQARunner
# ---------------------------------------------------------------------------


def _did_not_run(nodeid: str, message: str, duration: float) -> TestRunResult:
    """A test run that never got to run its tests: one error, naming why."""
    return TestRunResult(
        passed=0,
        failed=0,
        errors=1,
        skipped=0,
        total=1,
        failures=[TestFailure(nodeid=nodeid, message=message)],
        duration_seconds=duration,
    )


class PythonQARunner(QARunnerInterface):
    """Python test runner using pytest and ruff.

    Delegates all subprocess execution to SubprocessExecutor for unified
    timeout handling, credential stripping, and resource limits.

    Args:
        cwd: Project root directory.
        executor: Where the tools run, host or container; the caller chooses.
    """

    _DEFAULT_TIMEOUT: int = 120
    _BUILD_TIMEOUT: int = 300

    def __init__(self, cwd: Path, executor: SubprocessExecutor) -> None:
        self._cwd = cwd
        self._executor = executor

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
        coverage_source: str = "",
        source: str = "",
    ) -> TestRunResult:
        """Run pytest with the given parameters."""
        logger.debug("PythonQARunner.run_tests: target=%s kind=%s scope=%s", target, kind, scope)
        cmd = ["python", "-m", "pytest", target, "--tb=short", "-q"]

        # A marker filter can only deselect a test named outright.
        if kind and parse_target(target).kind != "test":
            cmd.extend(["-m", kind])

        if scope:
            cmd.extend(["-k", scope])

        if coverage:
            # Coverage measures a folder; one file's figure is read from its own report row.
            measured = str(PurePosixPath(coverage_source).parent) if coverage_source else target
            cmd.extend(["--cov", measured, "--cov-report", "term"])

        try:
            # A test imports its module by name (`from greet import hi`): make its folder importable.
            env = {"PYTHONPATH": str(PurePosixPath(source).parent)} if source else None
            result = self._executor.execute(cmd, timeout_seconds=timeout, extra_env=env)
        except ContainerEngineUnavailableError as exc:
            logger.warning(
                "PythonQARunner: container engine unavailable (target=%s): %s", target, exc
            )
            return _did_not_run("<sandbox>", str(exc), 0.0)

        if result.timed_out:
            logger.warning(
                "PythonQARunner: pytest timed out after %ds (target=%s)", timeout, target
            )
            return _did_not_run(
                "<timeout>", f"Test execution timed out after {timeout}s", result.duration_seconds
            )

        parsed = _parse_pytest_output(result.stdout)

        reason = why_it_did_not_run(result, "pytest")
        if reason:
            return _did_not_run("<toolchain>", reason, result.duration_seconds)
        if not parsed["total"]:
            said = f"none carries the marker '{kind}'" if "-m" in cmd[3:] else ""
            return _did_not_run("<no tests>", no_test_ran(target, said), result.duration_seconds)

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
            coverage_pct=(
                file_coverage(result.stdout, coverage_source)
                if coverage_source
                else parsed["coverage_pct"]
            ),
            duration_seconds=parsed.get("duration", result.duration_seconds),
            toolchain_note=_supplied_note(self._executor),
        )

    def run_linter(
        self,
        target: str,
        fix: bool = False,
    ) -> LintRunResult:
        """Run ruff linter with optional auto-fix."""
        logger.debug("PythonQARunner.run_linter: target=%s fix=%s", target, fix)
        fixed_count = 0

        try:
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
                    fix_data = self._parse_ruff_json(fix_result.stdout) or {}
                    fixed_count = len(fix_data.get("fixed", []))

            # Run final check to get current state
            result = self._executor.execute(
                ["python", "-m", "ruff", "check", target, "--output-format=json"],
                timeout_seconds=self._DEFAULT_TIMEOUT,
            )
        except ContainerEngineUnavailableError as exc:
            logger.warning(
                "PythonQARunner: container engine unavailable (target=%s): %s", target, exc
            )
            return failed_lint(f"ruff did not run: {exc}")

        if result.timed_out:
            logger.warning("PythonQARunner: ruff linting timed out (target=%s)", target)
            return failed_lint(f"ruff timed out after {self._DEFAULT_TIMEOUT} s")

        reason = why_it_did_not_run(result, "ruff")
        if reason:
            return failed_lint(reason)

        return self._build_lint_result(result.stdout, fixed_count)

    def _parse_ruff_json(self, stdout: str) -> dict[str, list[dict[str, object]]] | None:
        """Ruff's `--output-format=json` findings; None when the output is not that list."""
        try:
            data = json.loads(stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("ruff's report is not valid JSON: %s", exc)
            return None
        if not isinstance(data, list):
            logger.warning("ruff's report is not a list of findings: %.200s", stdout)
            return None
        return {"errors": data}

    def _build_lint_result(self, stdout: str, fixed_count: int) -> LintRunResult:
        """Build LintRunResult from ruff JSON output."""
        parsed = self._parse_ruff_json(stdout)
        if parsed is None:
            return failed_lint(f"ruff's report could not be read: {stdout.strip()[:200]}")
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
        try:
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
        except ContainerEngineUnavailableError as exc:
            logger.warning(
                "PythonQARunner: container engine unavailable (target=%s): %s", target, exc
            )
            return failed_complexity(f"ruff did not run: {exc}", max_complexity)

        if result.timed_out:
            logger.warning("PythonQARunner: complexity check timed out (target=%s)", target)
            return failed_complexity(
                f"ruff timed out after {self._DEFAULT_TIMEOUT} s", max_complexity
            )

        reason = why_it_did_not_run(result, "ruff")
        if reason:
            return failed_complexity(reason, max_complexity)

        return self._build_complexity_result(result.stdout, max_complexity)

    def _build_complexity_result(
        self,
        stdout: str,
        max_complexity: int,
    ) -> ComplexityRunResult:
        """Build ComplexityRunResult from ruff --select C90 JSON output."""
        parsed = self._parse_ruff_json(stdout)
        if parsed is None:
            return failed_complexity(
                f"ruff's report could not be read: {stdout.strip()[:200]}", max_complexity
            )
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
        # sys.executable is the HOST interpreter, meaningless in a container: use bare "python" there.
        python_bin = (
            "python" if isinstance(self._executor, ContainerSubprocessExecutor) else sys.executable
        )
        cmd = [python_bin, entrypoint]
        logger.debug("Running Python debugger wrapper: %s", shlex.join(cmd))

        try:
            result = self._executor.execute(cmd, timeout_seconds=self._BUILD_TIMEOUT)
        except ContainerEngineUnavailableError as exc:
            logger.warning(
                "PythonQARunner: container engine unavailable (entrypoint=%s): %s",
                entrypoint,
                exc,
            )
            return DebugRunResult(
                exit_code=124,
                duration_seconds=0.0,
                events=[OutputEvent(category="stderr", output=str(exc))],
            )

        reason = timed_out(result, entrypoint, self._BUILD_TIMEOUT)
        if reason:
            return DebugRunResult(
                exit_code=124,
                duration_seconds=result.duration_seconds,
                events=[OutputEvent(category="stderr", output=reason)],
            )

        return DebugRunResult(
            exit_code=result.exit_code,
            duration_seconds=result.duration_seconds,
            events=result.events,
        )
