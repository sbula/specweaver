# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reading complexity violations out of a SARIF report.

PMD (Java), Clippy (Rust) and detekt (Kotlin) all emit SARIF, and differ in exactly two values:
which rule ids count as complexity rules, and the hint appended to the hard-fail message. One
nested walk, because it sits at the complexity ceiling on its own.

The hard failure is deliberate and preserved exactly. A complexity result whose SARIF properties
carry no complexity *number* means the tool's property mapping has drifted — reporting zero
violations there would be a silent false pass, which is the failure mode this repo has spent a lot
of effort removing elsewhere.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.commons.qa import ComplexityViolation

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)

#: `ComplexityViolation` comes from the L0 `commons.qa` leaf, not through `sandbox`'s interface —
#: `workspace` may not reach into `sandbox`, and `tach` caught the first attempt to.

#: Property names a tool may use for the number itself. Checked in order.
_COMPLEXITY_PROPERTIES = ("complexity", "CyclomaticComplexity")


def _findings(report: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Every finding in the report, flattening the runs that contain them."""
    for run in report.get("runs", []):
        yield from run.get("results", [])


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
