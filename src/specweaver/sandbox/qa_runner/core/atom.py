# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""QARunnerAtom — engine-level test and lint execution.

The Engine uses QARunnerAtom for automated test execution and linting
as part of pipeline steps (e.g., validate+tests, lint-fix reflection).

Uses the language-agnostic QARunnerInterface — currently only Python
is supported, but the interface allows future language support.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from specweaver.sandbox.base import Atom, AtomResult, AtomStatus

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from specweaver.sandbox.qa_runner.core.interface import QARunnerInterface


# ---------------------------------------------------------------------------
# Language resolver
# ---------------------------------------------------------------------------

_LANGUAGE_RUNNERS: dict[str, type] = {}


def _resolve_runner(language: str, cwd: Any) -> QARunnerInterface:
    """Create a runner for the target.

    Forwards resolution to the auto-discovery factory, ignoring the legacy language string.
    """
    from specweaver.sandbox.qa_runner.core.factory import resolve_runner

    return resolve_runner(cwd)


# ---------------------------------------------------------------------------
# QARunnerAtom
# ---------------------------------------------------------------------------


class QARunnerAtom(Atom):
    """Engine-level test runner — stateless, intent-based.

    Delegates to a language-specific QARunnerInterface implementation.

    Args:
        cwd: Project root directory.
        language: Programming language (default: "python").
    """

    __test__ = False

    def __init__(self, cwd: Path, language: str = "python") -> None:
        self._runner = _resolve_runner(language, cwd)
        self._cwd = cwd

    def run(self, context: dict[str, Any]) -> AtomResult:
        """Dispatch to the appropriate intent based on context.

        Context must contain:
            intent: str — "run_tests", "run_linter", or "run_complexity".
        """
        intent = context.get("intent")
        if intent is None:
            logger.error("QARunnerAtom.run: missing 'intent' in context")
            return AtomResult(
                status=AtomStatus.FAILED,
                message="Missing 'intent' in context.",
            )

        logger.info("QARunnerAtom.run: dispatching intent '%s'", intent)

        handler: Callable[[dict[str, Any]], AtomResult] | None = getattr(
            self,
            f"_intent_{intent}",
            None,
        )
        if handler is None:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"Unknown intent: {intent!r}. Known: {sorted(self._known_intents())}",
            )

        return handler(context)

    def _known_intents(self) -> set[str]:
        """Return the set of known intent names."""
        prefix = "_intent_"
        return {name[len(prefix) :] for name in dir(self) if name.startswith(prefix)}

    # -- Intent implementations ----------------------------------------

    def _intent_run_tests(self, context: dict[str, Any]) -> AtomResult:  # noqa: C901
        """Run tests via the language-specific runner.

        Context keys:
            target: str — file or directory to test (required).
            kind: str — test marker/category (default: "unit").
            scope: str — module/service filter (default: "").
            timeout: int — max seconds (default: 120).
            coverage: bool — measure coverage (default: False).
            coverage_threshold: int — minimum % (default: 70).
        """
        targets_kwarg = context.get("targets")
        if targets_kwarg is not None:
            if not targets_kwarg:
                # Explicit empty list means all nodes pristine
                return AtomResult(
                    status=AtomStatus.SUCCESS,
                    message="All nodes pristine.",
                    exports={
                        "passed": 0,
                        "failed": 0,
                        "errors": 0,
                        "skipped": 0,
                        "total": 0,
                        "duration_seconds": 0.0,
                        "failures": [],
                    },
                )
            targets = targets_kwarg
        else:
            target = context.get("target")
            if not target:
                return AtomResult(
                    status=AtomStatus.FAILED,
                    message="Missing 'target' or 'targets' in context for run_tests intent.",
                )
            targets = [target]

        # NFR-3: Path Traversal Protection
        try:
            for t in targets:
                resolved_target = (self._cwd / t).resolve()
                if not resolved_target.is_relative_to(self._cwd.resolve()):
                    return AtomResult(
                        status=AtomStatus.FAILED,
                        message="Target cannot traverse outside of the sandbox directory.",
                    )
        except ValueError:
            return AtomResult(
                status=AtomStatus.FAILED,
                message="Invalid target path provided for sandbox execution.",
            )

        # Execute tests, natively aggregating for multiple dynamically rewritten boundaries
        agg_passed = 0
        agg_failed = 0
        agg_errors = 0
        agg_skipped = 0
        agg_total = 0
        agg_duration = 0.0
        agg_failures = []
        last_coverage_pct = None

        for t in targets:
            try:
                result = self._runner.run_tests(
                    target=t,
                    kind=context.get("kind", "unit"),
                    scope=context.get("scope", ""),
                    timeout=context.get("timeout", 120),
                    coverage=context.get("coverage", False),
                    coverage_threshold=context.get("coverage_threshold", 70),
                )
            except TimeoutError as exc:
                return AtomResult(
                    status=AtomStatus.FAILED,
                    message=f"Process timed out: {exc}",
                )

            agg_passed += result.passed
            agg_failed += result.failed
            agg_errors += result.errors
            agg_skipped += result.skipped
            agg_total += result.total
            agg_duration += result.duration_seconds
            agg_failures.extend(result.failures)
            if result.coverage_pct is not None:
                last_coverage_pct = result.coverage_pct

        exports: dict[str, Any] = {
            "passed": agg_passed,
            "failed": agg_failed,
            "errors": agg_errors,
            "skipped": agg_skipped,
            "total": agg_total,
            "duration_seconds": agg_duration,
            "failures": [__import__("dataclasses").asdict(f) for f in agg_failures],
        }
        if last_coverage_pct is not None:
            exports["coverage_pct"] = last_coverage_pct

        if agg_failed > 0 or agg_errors > 0:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"{agg_failed} failed, {agg_errors} errors out of {agg_total} tests.",
                exports=exports,
            )

        return AtomResult(
            status=AtomStatus.SUCCESS,
            message=f"All {agg_passed} tests passed.",
            exports=exports,
        )

    def _intent_run_linter(self, context: dict[str, Any]) -> AtomResult:
        """Run linter via the language-specific runner.

        Context keys:
            target: str — file or directory to lint (required).
            fix: bool — auto-fix fixable issues (default: False).
        """
        targets_kwarg = context.get("targets")
        if targets_kwarg is not None:
            if not targets_kwarg:
                return AtomResult(
                    status=AtomStatus.SUCCESS,
                    message="All nodes pristine.",
                    exports={"error_count": 0, "fixable_count": 0, "fixed_count": 0, "errors": []},
                )
            targets = targets_kwarg
        else:
            target = context.get("target")
            if not target:
                return AtomResult(
                    status=AtomStatus.FAILED,
                    message="Missing 'target' or 'targets' in context for run_linter intent.",
                )
            targets = [target]

        agg_errs = 0
        agg_fixable = 0
        agg_fixed = 0
        agg_failures = []

        for t in targets:
            result = self._runner.run_linter(
                target=t,
                fix=context.get("fix", False),
            )
            agg_errs += result.error_count
            agg_fixable += result.fixable_count
            agg_fixed += result.fixed_count
            agg_failures.extend(result.errors)

        exports: dict[str, Any] = {
            "error_count": agg_errs,
            "fixable_count": agg_fixable,
            "fixed_count": agg_fixed,
            "errors": [__import__("dataclasses").asdict(e) for e in agg_failures],
        }

        if agg_errs > 0:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"{agg_errs} lint error(s) found.",
                exports=exports,
            )

        return AtomResult(
            status=AtomStatus.SUCCESS,
            message="No lint errors.",
            exports=exports,
        )

    def _intent_run_complexity(self, context: dict[str, Any]) -> AtomResult:
        """Run complexity checks via the language-specific runner.

        Context keys:
            target: str — file or directory to check (required).
            max_complexity: int — McCabe threshold (default: 10).
        """
        target = context.get("target")
        if not target:
            return AtomResult(
                status=AtomStatus.FAILED,
                message="Missing 'target' in context for run_complexity intent.",
            )

        result = self._runner.run_complexity(
            target=target,
            max_complexity=context.get("max_complexity", 10),
        )

        exports: dict[str, Any] = {
            "violation_count": result.violation_count,
            "max_complexity": result.max_complexity,
            "violations": [asdict(v) for v in result.violations],
        }

        if result.violation_count > 0:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"{result.violation_count} function(s) exceed complexity "
                f"threshold of {result.max_complexity}.",
                exports=exports,
            )

        return AtomResult(
            status=AtomStatus.SUCCESS,
            message=f"All functions within complexity threshold of {result.max_complexity}.",
            exports=exports,
        )

    def _intent_run_compiler(self, context: dict[str, Any]) -> AtomResult:
        """Run compilation/build process.

        Context keys:
            target: str — file or directory to compile (required).
        """
        target = context.get("target")
        if not target:
            return AtomResult(
                status=AtomStatus.FAILED,
                message="Missing 'target' in context for run_compiler intent.",
            )

        result = self._runner.run_compiler(target=target)

        exports: dict[str, Any] = {
            "error_count": result.error_count,
            "warning_count": result.warning_count,
            "errors": [asdict(e) for e in result.errors],
        }

        if result.error_count > 0:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"{result.error_count} compile error(s) found.",
                exports=exports,
            )

        return AtomResult(
            status=AtomStatus.SUCCESS,
            message="Compilation successful. No errors.",
            exports=exports,
        )

    def _intent_run_debugger(self, context: dict[str, Any]) -> AtomResult:
        """Run a process in the debugger.

        Context keys:
            target: str — workspace directory or file target (required).
            entrypoint: str — the entrypoint to debug (required).
        """
        target = context.get("target")
        entrypoint = context.get("entrypoint")
        if not target or not entrypoint:
            return AtomResult(
                status=AtomStatus.FAILED,
                message="Missing 'target' or 'entrypoint' in context for run_debugger intent.",
            )

        result = self._runner.run_debugger(target=target, entrypoint=entrypoint)

        exports: dict[str, Any] = {
            "exit_code": result.exit_code,
            "duration_seconds": result.duration_seconds,
            "events": [asdict(e) for e in result.events],
        }

        if result.exit_code != 0:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"Debug process exited with code {result.exit_code}.",
                exports=exports,
            )

        return AtomResult(
            status=AtomStatus.SUCCESS,
            message="Debug process completed successfully.",
            exports=exports,
        )

    def _intent_run_architecture(self, context: dict[str, Any]) -> AtomResult:
        """Run architectural checks.

        Context keys:
            target: str — file or directory to check (required).
        """
        target = context.get("target")
        if not target:
            return AtomResult(
                status=AtomStatus.FAILED,
                message="Missing 'target' in context for run_architecture intent.",
            )

        result = self._runner.run_architecture_check(target=target)

        exports: dict[str, Any] = {
            "violation_count": result.violation_count,
            "violations": [asdict(v) for v in result.violations],
        }

        if result.violation_count > 0:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"{result.violation_count} architectural violation(s) found.",
                exports=exports,
            )

        return AtomResult(
            status=AtomStatus.SUCCESS,
            message="No architectural violations.",
            exports=exports,
        )
