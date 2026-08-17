# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Telling "the tool reported nothing" apart from "the tool never ran".

Shared by every language runner, because the hole is identical in all of them. Without this, a
toolchain that is not installed reads as a *clean run*: ``python -m pytest`` with no pytest leaves
stdout empty and exits 1, which parses to ``passed=0 failed=0 errors=0`` — indistinguishable from a
project with no tests, and from a caller's view, from success. Ruff's empty stdout parses
identically to its own ``[]``, and an empty tach stdout reads as no violations.

**The QA gate would certify runs that never happened** — a vacuous proof inside the mechanism whose
whole job is to prevent them.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.sandbox.execution.models import SubprocessResult

from specweaver.sandbox.qa_runner.core.interface import (
    ArchitectureRunResult,
    ArchitectureViolation,
    CompileError,
    CompileRunResult,
    ComplexityRunResult,
    ComplexityViolation,
    LintError,
    LintRunResult,
    TestFailure,
    TestRunResult,
)

logger = logging.getLogger(__name__)

#: Truncation for the reported reason — a stderr line can be an entire traceback.
_MAX_REASON = 200


def did_not_run(result: SubprocessResult, tool: str) -> str | None:
    """Why `tool` never executed, or None if it ran and reached a verdict.

    The discriminator is **empty stdout, not the exit code**. Keying on the exit code was tried
    and broke `sw implement` against a fresh project: pytest exits **4** for a `tests/` directory
    that does not exist yet, having run correctly and printed `no tests ran in 0.00s`. Exit 4 and
    exit 5 both mean the tool reached a verdict; only a tool that never started says nothing.
    """
    if result.exit_code == 0 or result.stdout.strip():
        return None

    detail = (result.stderr or "").strip().splitlines()
    reason = detail[-1][:_MAX_REASON] if detail else f"{tool} exited {result.exit_code}"
    logger.error("%s produced no output — %s", tool, reason)
    return f"{tool} did not run: {reason}"


# ---------------------------------------------------------------------------
# The result each QA surface returns when its tool never ran
# ---------------------------------------------------------------------------
#
# Five result shapes, one meaning: "this did not run, do not read the zeros as a
# pass." Factories rather than an inline literal at each of a dozen call sites, so the reported
# shape cannot drift between languages — which is how the Python runner ended up being the only
# one that reported it at all.


def failed_tests(reason: str, duration_seconds: float = 0.0) -> TestRunResult:
    return TestRunResult(
        passed=0,
        failed=0,
        errors=1,
        skipped=0,
        total=1,
        failures=[TestFailure(nodeid="<toolchain>", message=reason)],
        coverage_pct=None,
        duration_seconds=duration_seconds,
    )


def failed_lint(reason: str) -> LintRunResult:
    return LintRunResult(
        error_count=1,
        fixable_count=0,
        fixed_count=0,
        errors=[LintError(file="<toolchain>", line=0, code="ToolchainUnavailable", message=reason)],
    )


def failed_complexity(reason: str, max_complexity: int) -> ComplexityRunResult:
    return ComplexityRunResult(
        violation_count=1,
        max_complexity=max_complexity,
        violations=[
            ComplexityViolation(
                file="<toolchain>", line=0, function="<toolchain>", complexity=0, message=reason
            )
        ],
    )


def failed_architecture(reason: str) -> ArchitectureRunResult:
    return ArchitectureRunResult(
        violation_count=1,
        violations=[
            ArchitectureViolation(file="<toolchain>", code="ToolchainUnavailable", message=reason)
        ],
    )


def failed_compile(reason: str) -> CompileRunResult:
    return CompileRunResult(
        error_count=1,
        warning_count=0,
        errors=[
            CompileError(
                file="<toolchain>",
                line=0,
                column=0,
                code="ToolchainUnavailable",
                message=reason,
                is_warning=False,
            )
        ],
    )
