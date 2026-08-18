# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reading lint findings out of a SARIF report.

PMD (Java) and detekt (Kotlin) both emit SARIF, so both need the same four-deep walk — `runs` →
`results` → `locations` → `physicalLocation` — differing only in the substring used to skip
complexity rules, which each runner reports through its own `run_complexity` instead. One walk,
because it sits at the complexity ceiling and a second copy means paying for it twice.

Note the shadowing this removes. Both runners wrote `for result in run.get("results", [])` inside a
method whose subprocess result was also called `result` — harmless as written, but the kind of
reuse that turns a later edit into a silent bug.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from specweaver.sandbox.qa_runner.core.interface import LintError

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


def _findings(report: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Every finding in the report, flattening the runs that contain them."""
    for run in report.get("runs", []):
        yield from run.get("results", [])


def lint_errors_from_sarif(
    report: dict[str, Any], *, skip_rules_containing: str
) -> list[LintError]:
    """Lint findings from a SARIF report, minus the rules another QA surface owns.

    `skip_rules_containing` drops the complexity rules, which the runners report through
    `run_complexity` — counting them here would report every one of them twice.
    """
    errors: list[LintError] = []
    for finding in _findings(report):
        rule_id = finding.get("ruleId", "")
        if skip_rules_containing in rule_id.lower():
            continue

        message = finding.get("message", {}).get("text", "")
        for location in finding.get("locations", []):
            physical = location.get("physicalLocation", {})
            errors.append(
                LintError(
                    file=physical.get("artifactLocation", {}).get("uri", ""),
                    line=physical.get("region", {}).get("startLine", 0),
                    code=rule_id,
                    message=message,
                )
            )
    return errors


def read_sarif_report(path: Path) -> dict[str, Any]:
    """A SARIF report as a mapping, or an empty one when it cannot be read.

    Callers check `report_never_written` first, so reaching here with an unreadable file means the
    tool wrote something malformed — which is its problem to fix and not a lint verdict either way.
    """
    try:
        report = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return report if isinstance(report, dict) else {}
