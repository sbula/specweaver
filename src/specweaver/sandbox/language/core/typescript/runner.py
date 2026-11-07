# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""TypeScript runner implementation."""

import json
import logging
import os
import re
import shlex
import shutil
from pathlib import Path

from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.language.core.run_targets import no_test_ran, npm_test_args, parse_target
from specweaver.sandbox.language.core.toolchain import (
    did_not_run,
    failed_compile,
    failed_complexity,
    failed_lint,
    failed_tests,
    timed_out,
)
from specweaver.sandbox.language.core.typescript.npm_output import (
    TestCounts,
    eslint_findings,
    summary_counts,
)
from specweaver.sandbox.language.core.typescript.tsc_output import extract_tsc_errors
from specweaver.sandbox.qa_runner.core.interface import (
    CompileRunResult,
    ComplexityRunResult,
    DebugRunResult,
    LintError,
    LintRunResult,
    OutputEvent,
    QARunnerInterface,
    TestRunResult,
)

logger = logging.getLogger(__name__)

_TSC_TIMEOUT_SECONDS = 120
_DEBUG_TIMEOUT_SECONDS = 300


_NO_TESTS = re.compile(r"No tests? (files )?found", re.IGNORECASE)


def _ran_nothing(counts: TestCounts | None, output: str) -> bool:
    """Jest or Vitest ran no test: every test skipped by the name filter, or none found."""
    if counts is not None:
        return counts.passed + counts.failed == 0
    return bool(_NO_TESTS.search(output))


class TypeScriptRunner(QARunnerInterface):
    """Executes tests, compilation, and debugging for TypeScript projects."""

    def __init__(self, cwd: Path, executor: SubprocessExecutor) -> None:
        self._cwd = cwd
        self._executor = executor

    @property
    def language_name(self) -> str:
        """Canonical language identifier."""
        return "typescript"

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
        """The project's own `npm test` — one file after `--` — counted from Jest's or Vitest's
        summary line, else by the exit code alone."""
        if not self._has_test_script():
            return failed_tests("package.json has no test script: npm test cannot run the tests")
        cmd = [shutil.which("npm") or "npm", "test"]
        filters = npm_test_args(parse_target(target))
        if filters:
            cmd += ["--", *filters]
        result = self._executor.execute(cmd, timeout_seconds=timeout)
        reason = did_not_run(result, "npm test")
        if reason:
            return failed_tests(reason, result.duration_seconds)
        # Jest writes its summary to stderr, Vitest to stdout.
        output = f"{result.stdout}\n{result.stderr}"
        counts = summary_counts(output)
        if _ran_nothing(counts, output):
            return failed_tests(no_test_ran(target), result.duration_seconds)
        if counts is None:
            ok = result.exit_code == 0
            counts = TestCounts(passed=int(ok), failed=int(not ok), skipped=0, total=1)
        return TestRunResult(
            total=counts.total,
            passed=counts.passed,
            failed=counts.failed,
            errors=0,
            skipped=counts.skipped,
            duration_seconds=result.duration_seconds,
            failures=[],
            coverage_pct=None,
        )

    def _has_test_script(self) -> bool:
        try:
            manifest = json.loads((self._cwd / "package.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):  # expected: an unreadable manifest declares no script
            return False
        return isinstance(manifest, dict) and bool(manifest.get("scripts", {}).get("test"))

    def run_linter(self, target: str, fix: bool = False) -> LintRunResult:
        """ESLint over `target`, read from its JSON; an ESLint that did not run is never clean."""
        cmd = [shutil.which("npx") or "npx", "eslint", target or ".", "--format", "json"]
        if fix:
            cmd.append("--fix")
        result = self._executor.execute(cmd, timeout_seconds=120)
        read = eslint_findings(result.stdout)
        if read is None:
            return failed_lint(
                did_not_run(result, "eslint")
                or f"eslint did not report (exit {result.exit_code}): {result.stdout.strip()[:200]}"
            )
        findings, fixable = read
        return LintRunResult(
            error_count=len(findings),
            fixable_count=fixable,
            fixed_count=0,
            errors=[
                LintError(file=f.file, line=f.line, code=f.code, message=f.message)
                for f in findings
            ],
        )

    def run_complexity(self, target: str, max_complexity: int = 10) -> ComplexityRunResult:
        """Not built: says so, because a zero here would read as "within threshold"."""
        return failed_complexity("TypeScript complexity checks are not implemented", max_complexity)

    def run_compiler(self, target: str) -> CompileRunResult:
        """Run TypeScript compiler (tsc --noEmit) and extract diagnostics."""
        npx_bin = shutil.which("npx") or "npx"
        cmd = [npx_bin, "tsc", "--noEmit"]
        if target and target != "." and target != "src/":
            # If a strict file target is provided, append it
            cmd.append(target)

        logger.debug("Running TypeScript compiler: %s", shlex.join(cmd))

        result = self._executor.execute(cmd, timeout_seconds=_TSC_TIMEOUT_SECONDS)
        reason = timed_out(result, "tsc", _TSC_TIMEOUT_SECONDS) or did_not_run(result, "tsc")
        if reason:
            return failed_compile(reason)

        errors = extract_tsc_errors(result.stdout)

        return CompileRunResult(
            error_count=len(errors),
            warning_count=0,  # tsc doesn't easily divide warnings in standard output buffer without verbose
            errors=errors,
        )

    def _node_strips_types(self, node_bin: str) -> bool:
        """Whether this Node runs a `.ts` file directly, without a transpiling wrapper.

        Node gained type stripping behind a flag in 22.6 and on by default in 23.6 and 22.18, so on a current
        runtime no wrapper is needed at all. Probed by version rather than by running a scratch
        file: this is called per debug run, and spawning a probe process to decide how to spawn a
        process is a cost with no payoff.
        """
        try:
            probe = self._executor.execute([node_bin, "--version"], timeout_seconds=10)
        except OSError:  # expected: no node at all; the caller falls back and reports it
            # Raising from a capability probe would replace a reported exit code with a traceback.
            return False
        if probe.exit_code != 0:
            return False
        try:
            major, minor = (int(part) for part in probe.stdout.strip().lstrip("v").split(".")[:2])
        except ValueError:  # expected: an unreadable version means no type stripping
            return False
        return (major, minor) >= (23, 6) or (major == 22 and minor >= 18)

    def run_debugger(self, target: str, entrypoint: str) -> DebugRunResult:
        """Execute a process and stream runtime outputs."""
        npx_bin = shutil.which("npx") or "npx"
        node_bin = shutil.which("node") or "node"
        if entrypoint.endswith(".ts"):
            # Three ways to run TypeScript, in descending order of reliability.
            #
            # `tsx` first — maintained, fast, and independent of the installed compiler version.
            #
            # Then Node itself. 23.6+ strips types natively, which needs no package at all and so
            # cannot be broken by a dependency resolution.
            #
            # `ts-node` last, and only as a fallback for older runtimes. Its final release (10.9.2,
            # 2023) reads `ts.sys` from the TypeScript compiler API, which TypeScript 7 no longer
            # exposes — so `npm install typescript ts-node` on a current registry produces a pair
            # that cannot work: `TypeError: Cannot read properties of undefined (reading
            # 'fileExists')`. Measured, with TypeScript 7.0.2 and Node 24.
            local_tsx = (
                self._cwd / "node_modules" / ".bin" / ("tsx.cmd" if os.name == "nt" else "tsx")
            )
            tsx_bin = str(local_tsx) if local_tsx.is_file() else shutil.which("tsx")
            if tsx_bin:
                cmd = [tsx_bin, entrypoint]
            elif self._node_strips_types(node_bin):
                cmd = [node_bin, entrypoint]
            else:
                cmd = [npx_bin, "ts-node", entrypoint]
        else:
            cmd = [node_bin, entrypoint]
        logger.debug("Running TypeScript debugger wrapper: %s", shlex.join(cmd))

        result = self._executor.execute(cmd, timeout_seconds=_DEBUG_TIMEOUT_SECONDS)

        reason = timed_out(result, entrypoint, _DEBUG_TIMEOUT_SECONDS)
        if reason:
            return DebugRunResult(
                exit_code=124,
                duration_seconds=result.duration_seconds,
                events=[OutputEvent(category="stderr", output=reason)],
            )

        events: list[OutputEvent] = []
        for line in result.stdout.splitlines():
            events.append(OutputEvent(category="stdout", output=line))
        for line in result.stderr.splitlines():
            events.append(OutputEvent(category="stderr", output=line))

        return DebugRunResult(
            exit_code=result.exit_code,
            duration_seconds=result.duration_seconds,
            events=events,
        )
