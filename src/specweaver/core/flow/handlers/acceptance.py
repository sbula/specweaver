# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The acceptance step: every fresh kept scenario set runs against the current code.

Its report is for the person only. The step always passes, so the handover — which keeps failed
steps' errors — holds nothing of it, and it writes nothing to `feedback`.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import _now_iso
from specweaver.sandbox.qa_runner.core.atom import container_available

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from specweaver.core.flow.handlers.run_context import RunContext

logger = logging.getLogger(__name__)

_TEST_DEF = re.compile(r"^def (test_\w+)\(.*$", re.MULTILINE)
_TRACE = re.compile(r"@trace\(([^)]+)\)")


def _requirements_of(test_file: Path) -> dict[str, list[str]]:
    """Each test function's requirement ids, from its `@trace` tags."""
    try:
        text = test_file.read_text(encoding="utf-8")
    except OSError:
        return {}
    return {m.group(1): _TRACE.findall(m.group(0)) for m in _TEST_DEF.finditer(text)}


def _failed_requirements(failures: list[dict[str, Any]], tests: Path) -> list[str]:
    ids: set[str] = set()
    for failure in failures:
        file_part, _, test_part = str(failure.get("nodeid", "")).partition("::")
        function = test_part.split("[", 1)[0]
        ids.update(_requirements_of(tests / file_part.rsplit("/", 1)[-1]).get(function, []))
    return sorted(ids)


def _passed(report: dict[str, Any], started: str) -> StepResult:
    return StepResult(
        status=StepStatus.PASSED,
        output={"acceptance": report},
        started_at=started,
        completed_at=_now_iso(),
    )


def run_acceptance(context: RunContext, atom: Callable[[], Any]) -> StepResult:
    """Run the fresh kept sets; list the stale ones; never fail."""
    from specweaver.core.flow.handlers.reviewed_spec import kept_sets
    from specweaver.core.flow.handlers.scenario_store import scenario_store

    started = _now_iso()
    sets = kept_sets(context)
    store = scenario_store(context)
    if not sets or store is None:
        return _passed({}, started)
    stale = [str(s["spec"]) for s in sets if not s["fresh"]]
    files = [f for s in sets if s["fresh"] for f in str(s["tests"]).split()]
    if not files:
        return _passed({"stale": stale}, started)
    if not container_available(context.project_path):
        return _passed({"stale": stale, "not_run": "no container engine answers here"}, started)
    result = atom().run(
        {
            "intent": "run_tests",
            "target": "/scenarios/generated",
            "targets": [f"/scenarios/generated/{name}" for name in files],
            "kind": "",
            "timeout": 120,
        }
    )
    exports = result.exports or {}
    report = {
        "passed": exports.get("passed", 0),
        "failed": exports.get("failed", 0) + exports.get("errors", 0),
        "failed_requirements": _failed_requirements(
            exports.get("failures") or [], store / "generated"
        ),
        "stale": stale,
    }
    logger.info("Acceptance: %s", report)
    return _passed(report, started)


def acceptance_lines(report: dict[str, Any]) -> list[str]:
    """The report as console lines: what passed, which requirements failed, which sets are stale."""
    from rich.markup import escape

    if not report:
        return []
    lines = ["[bold]Kept scenario checks[/bold]"]
    if report.get("not_run"):
        lines.append(f"  not run: {escape(str(report['not_run']))}")
    if "passed" in report:
        lines.append(f"  {report['passed']} passed, {report.get('failed', 0)} failed")
    lines += [
        f"  [red]failed[/red] {escape(str(rid))}" for rid in report.get("failed_requirements") or []
    ]
    lines += [
        f"  stale: {escape(str(spec))} changed; a dual run makes its set again"
        for spec in report.get("stale") or []
    ]
    return lines
