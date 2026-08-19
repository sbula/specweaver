# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""RustRunner — Cargo/JUnit/SARIF mapping test and lint execution interface."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from specweaver.commons.enums.dal import DALLevel  # noqa: TC001
from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.language.core.rust.cargo_diagnostics import parse_cargo_diagnostics
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

            # Complexity findings belong to `run_complexity`; counting them here reports each twice.
            errors_list = [
                LintError(file=f.file, line=f.line, code=f.code, message=f.message)
                for f in parse_cargo_diagnostics(clippy_result.stdout)
                if "complexity" not in f.code.lower()
            ]
            return LintRunResult(
                error_count=len(errors_list), fixable_count=0, fixed_count=0, errors=errors_list
            )
        except Exception:
            return LintRunResult(error_count=1, fixable_count=0, fixed_count=0, errors=[])

    def run_complexity(self, target: str, max_complexity: int = 10) -> ComplexityRunResult:
        from specweaver.sandbox.qa_runner.core.interface import (
            ComplexityRunResult,
            ComplexityViolation,
        )

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

            violations = [
                ComplexityViolation(
                    file=f.file,
                    line=f.line,
                    function=f.code,
                    # Clippy states the score in the message — `cognitive complexity of (11/10)` —
                    # so the real number is reported rather than the threshold plus one.
                    complexity=_complexity_score(f.message, max_complexity),
                    message=f.message,
                )
                for f in parse_cargo_diagnostics(clippy_result.stdout)
                if "complexity" in f.code.lower()
            ]
            # Clippy's threshold lives in `clippy.toml`, not on the command line, so the caller's
            # `max_complexity` cannot be applied — the number reported is the one clippy used. Saying
            # so beats echoing a threshold that had no effect on the verdict.
            return ComplexityRunResult(
                violation_count=len(violations),
                max_complexity=_CLIPPY_COGNITIVE_THRESHOLD,
                violations=violations,
            )
        except Exception as exc:
            # A phantom violation with no detail is what this returned, so an internal error looked
            # like a complexity finding. It says which error, since the count alone cannot.
            return ComplexityRunResult(
                violation_count=1,
                max_complexity=max_complexity,
                violations=[
                    ComplexityViolation(
                        file="<toolchain>",
                        line=0,
                        function="run_complexity",
                        complexity=max_complexity + 1,
                        message=f"complexity check failed: {type(exc).__name__}: {exc}",
                    )
                ],
            )

    def run_compiler(self, target: str) -> CompileRunResult:
        from specweaver.sandbox.qa_runner.core.interface import CompileError, CompileRunResult

        try:
            # The whole package, and no `--bin`. `--bin` takes a binary *name*, so passing a path
            # produced `no bin target named '.'` for every target but the literal `src/` — cargo
            # compiles the package, and selecting a path within it is not a thing it does.
            cmd = ["cargo", "build", "--message-format=json"]

            result = self._executor.execute(cmd)
            # Judged by exit code, not by empty stdout: cargo writes its progress to stderr, so a
            # perfectly good build looks silent and `did_not_run` called it an absent toolchain.
            diagnostics = parse_cargo_diagnostics(result.stdout)
            errors = [
                CompileError(
                    file=d.file,
                    line=d.line,
                    column=0,
                    code=d.code,
                    message=d.message,
                    is_warning=False,
                )
                for d in diagnostics
                if d.level == "error"
            ]
            warnings = [d for d in diagnostics if d.level == "warning"]
            if result.exit_code != 0 and not errors:
                # Failed, but said nothing a parser could read — a missing toolchain, a bad flag.
                return failed_compile(
                    did_not_run(result, "cargo")
                    or f"cargo build exited {result.exit_code}: "
                    f"{(result.stderr or '').strip()[:200]}"
                )
            return CompileRunResult(
                error_count=len(errors), warning_count=len(warnings), errors=errors
            )
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
        """Report that architectural checks are not implemented for this language.

        It returns a result rather than raising because the QA atom treats an exception as a
        failed step, and the check not existing is not the project's fault. The `note` is not
        optional: without it, this is indistinguishable from a clean verdict.
        """
        return ArchitectureRunResult(
            violation_count=0,
            violations=[],
            note="Rust architecture checks are not implemented; no boundary was examined.",
        )


#: Clippy's own default for `cognitive-complexity-threshold`. It is configured in `clippy.toml`
#: and cannot be set per run, so a caller asking for a stricter number does not get one.
_CLIPPY_COGNITIVE_THRESHOLD = 25


def _complexity_score(message: str, fallback: int) -> int:
    """The score clippy reported, or one past the threshold when its wording changes."""
    match = re.search(r"\((\d+)/\d+\)", message)
    return int(match.group(1)) if match else fallback + 1
