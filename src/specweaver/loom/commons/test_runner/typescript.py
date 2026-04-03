# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""TypeScript test runner implementation."""

import logging
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from specweaver.loom.commons.test_runner.interface import (
    CompileError,
    CompileRunResult,
    ComplexityRunResult,
    DebugRunResult,
    LintRunResult,
    OutputEvent,
    TestRunnerInterface,
    TestRunResult,
)

logger = logging.getLogger(__name__)

# Regex fallback for compiling TS errors from tsc stdout.
# Format: <file>(<line>,<col>): error TS<code>: <msg>
TSC_ERROR_REGEX = re.compile(
    r"^(?P<file>[^\(]+)\((?P<line>\d+),(?P<col>\d+)\):\s+error\s+(?P<code>TS\d+):\s+(?P<msg>.*)$"
)


class TypeScriptRunner(TestRunnerInterface):
    """Executes tests, compilation, and debugging for TypeScript projects."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd

    def run_tests(
        self,
        target: str,
        kind: str = "unit",
        scope: str = "",
        timeout: int = 120,
        coverage: bool = False,
        coverage_threshold: int = 70,
    ) -> TestRunResult:
        """Run tests using standard TS runners (npm test). STUB."""
        return TestRunResult(
            total=0,
            passed=0,
            failed=0,
            errors=0,
            skipped=0,
            duration_seconds=0.0,
            failures=[],
            coverage_pct=None,
        )

    def run_linter(self, target: str, fix: bool = False) -> LintRunResult:
        """Run standard ESLint target. STUB."""
        return LintRunResult(
            error_count=0,
            fixable_count=0,
            fixed_count=0,
            errors=[],
        )

    def run_complexity(self, target: str, max_complexity: int = 10) -> ComplexityRunResult:
        """Run standard JS complexity check. STUB."""
        return ComplexityRunResult(
            violation_count=0,
            max_complexity=max_complexity,
            violations=[],
        )

    def run_compiler(self, target: str) -> CompileRunResult:
        """Run TypeScript compiler (tsc --noEmit) and extract diagnostics."""
        npx_bin = shutil.which("npx") or "npx"
        cmd = [npx_bin, "tsc", "--noEmit"]
        if target and target != "." and target != "src/":
            # If a strict file target is provided, append it
            cmd.append(target)

        logger.debug("Running TypeScript compiler: %s", shlex.join(cmd))

        try:
            # We don't use check=True because tsc exits >0 on compilation errors
            proc = subprocess.run(
                cmd,
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except subprocess.TimeoutExpired:
            logger.error("tsc process timed out after 120s")
            return CompileRunResult(
                error_count=1,
                warning_count=0,
                errors=[
                    CompileError(
                        file=target,
                        line=0,
                        column=0,
                        message="Timeout during compilation",
                        code="TIMEOUT",
                        is_warning=False,
                    )
                ],
            )
        except getattr(__builtins__, "FileNotFoundError", OSError):
            logger.error("TypeScript toolchain not found (tsc or npx missing)")
            return CompileRunResult(
                error_count=1,
                warning_count=0,
                errors=[
                    CompileError(
                        file=target,
                        line=0,
                        column=0,
                        message="TypeScript compiler not found in PATH.",
                        code="ENOENT",
                        is_warning=False,
                    )
                ],
            )

        errors: list[CompileError] = []
        for raw_line in proc.stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            match = TSC_ERROR_REGEX.match(line)
            if match:
                errors.append(
                    CompileError(
                        file=match.group("file").strip(),
                        line=int(match.group("line")),
                        column=int(match.group("col")),
                        code=match.group("code").strip(),
                        message=match.group("msg").strip(),
                        is_warning=False,
                    )
                )

        if not errors:
            raise RuntimeError(
                f"DEBUG NO MATCH. STDOUT: {proc.stdout!r} STDERR: {proc.stderr!r} CODE: {proc.returncode}"
            )

        return CompileRunResult(
            error_count=len(errors),
            warning_count=0,  # tsc doesn't easily divide warnings in standard output buffer without verbose
            errors=errors,
        )

    def run_debugger(self, target: str, entrypoint: str) -> DebugRunResult:
        """Execute a process and stream runtime outputs."""
        npx_bin = shutil.which("npx") or "npx"
        node_bin = shutil.which("node") or "node"
        cmd = (
            [npx_bin, "ts-node", entrypoint]
            if entrypoint.endswith(".ts")
            else [node_bin, entrypoint]
        )
        logger.debug("Running TypeScript debugger wrapper: %s", shlex.join(cmd))

        start_time = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return DebugRunResult(
                exit_code=124,
                duration_seconds=300.0,
                events=[OutputEvent(category="stderr", output="Timeout expired")],
            )
        except getattr(__builtins__, "FileNotFoundError", OSError):
            return DebugRunResult(
                exit_code=127,
                duration_seconds=0.0,
                events=[
                    OutputEvent(
                        category="stderr", output="Node/TypeScript runner not found in PATH"
                    )
                ],
            )

        duration = time.monotonic() - start_time

        events: list[OutputEvent] = []
        for line in proc.stdout.splitlines():
            events.append(OutputEvent(category="stdout", output=line))
        for line in proc.stderr.splitlines():
            events.append(OutputEvent(category="stderr", output=line))

        return DebugRunResult(
            exit_code=proc.returncode,
            duration_seconds=duration,
            events=events,
        )
