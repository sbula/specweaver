# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reading lint findings and complexity violations out of a SARIF report.

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
import logging
from typing import TYPE_CHECKING, Any

from specweaver.commons.qa import ComplexityViolation
from specweaver.sandbox.language.core.toolchain import (
    clear_old_report,
    did_not_run,
    report_never_written,
    timed_out,
    unreadable_report,
)
from specweaver.sandbox.qa_runner.core.interface import LintError

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from specweaver.sandbox.execution.executor import SubprocessExecutor

logger = logging.getLogger(__name__)


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


def read_sarif_report(path: Path) -> dict[str, Any] | None:
    """A SARIF report as a mapping, or None when it cannot be read as one.

    Callers check `report_never_written` first, so None means the tool wrote something malformed.
    That is no verdict, and the caller reports the check as not run.
    """
    try:
        report = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("%s cannot be read: %s", path, exc)
        return None
    if not isinstance(report, dict):
        logger.warning("%s is not a SARIF object", path)
        return None
    return report


def run_sarif_analysis(
    executor: SubprocessExecutor, cmd: list[str], report: Path, *, analyzer: str, build_tool: str
) -> dict[str, Any] | str:
    """Today's SARIF report from one analysis run, or why there is none.

    A string means the check did not run: the old report could not be cleared, the run timed out
    or never started, it wrote no report, or the report cannot be read. The old report is removed
    first, so a run that writes none cannot be judged by an earlier run's verdict.
    """
    cleared = clear_old_report(report)
    if cleared:
        return cleared
    result = executor.execute(cmd)
    reason = (
        timed_out(result, analyzer)
        or did_not_run(result, analyzer)
        or report_never_written(result, build_tool, report)
    )
    if reason:
        return reason
    data = read_sarif_report(report)
    return unreadable_report(analyzer, report) if data is None else data


# --- complexity ------------------------------------------------------------
#
# PMD (Java) and detekt (Kotlin) differ in two values: which rule ids count as complexity rules,
# and the hint appended to the hard-fail message. A complexity finding whose SARIF properties carry
# no complexity number means the tool's property mapping has drifted; reporting zero violations
# there would be a silent false pass, so it fails hard.

#: Property names a tool may use for the number itself. Checked in order.
_COMPLEXITY_PROPERTIES = ("complexity", "CyclomaticComplexity")


def _complexity_of(finding: dict[str, Any], drift_hint: str) -> int:
    """The complexity a finding reports, or a hard failure if it carries none.

    Structural JSON lookup only — never a regex over the message text, which is what lets this
    survive a tool's wording changing.
    """
    props = finding.get("properties", {})
    for name in _COMPLEXITY_PROPERTIES:
        if name in props:
            return int(props[name])

    logger.error(
        "SARIF property 'complexity' or 'CyclomaticComplexity' missing in complexity violation node"
    )
    msg = (
        "HARD FAIL: SARIF property 'complexity' or 'CyclomaticComplexity' missing in complexity "
        f"violation node. {drift_hint}"
    )
    raise ValueError(msg)


def _first_location(finding: dict[str, Any]) -> tuple[str, int]:
    """The first physical location a finding names, as `(uri, line)`.

    Conservative by design: a finding may carry several locations, and the first is the one the
    tool considered primary.
    """
    for location in finding.get("locations", []):
        physical = location.get("physicalLocation", {})
        return (
            physical.get("artifactLocation", {}).get("uri", ""),
            physical.get("region", {}).get("startLine", 0),
        )
    return "", 0


def parse_sarif_complexity(
    report: dict[str, Any],
    max_complexity: int,
    *,
    rule_markers: tuple[str, ...],
    drift_hint: str,
) -> list[ComplexityViolation]:
    """Complexity violations above `max_complexity`, from any SARIF-emitting tool.

    `rule_markers` are matched case-insensitively against the rule id, and stay per-tool because
    each names its complexity rules differently — PMD says `ncss`, Clippy says
    `cognitive_complexity`, detekt just `complex`.
    """
    violations: list[ComplexityViolation] = []
    for finding in _findings(report):
        rule_id = finding.get("ruleId", "").lower()
        if not any(marker in rule_id for marker in rule_markers):
            continue

        complexity = _complexity_of(finding, drift_hint)
        if complexity <= max_complexity:
            continue

        uri, line = _first_location(finding)
        violations.append(
            ComplexityViolation(
                file=uri,
                line=line,
                function="unknown",
                complexity=complexity,
                message=finding.get("message", {}).get("text", ""),
            )
        )
    return violations
