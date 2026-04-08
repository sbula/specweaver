# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""S10: Done Definition Test — checks for unambiguous completion criteria."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from specweaver.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path

# Patterns that indicate a done definition exists
_DONE_SECTION_PATTERNS = [
    r"##\s*Done\s*Definition",
    r"##\s*Completion\s*Criteria",
    r"##\s*Acceptance\s*Criteria",
    r"##\s*Definition\s*of\s*Done",
    r"##\s*DoD\b",
]

# Patterns for verifiable criteria (checkboxes, test commands, coverage)
_VERIFIABLE_PATTERNS = [
    r"\[[ x]\]",  # Markdown checkboxes
    r"coverage\s*[>>=]+\s*\d+",  # Coverage threshold
    r"test.*pass",  # Tests pass
    r"pytest",  # Specific test runner
    r"sw\s+check",  # SpecWeaver check command
]


class DoneDefinitionRule(Rule):
    """Detect specs without a clear, verifiable done definition."""

    @property
    def rule_id(self) -> str:
        return "S10"

    @property
    def name(self) -> str:
        return "Done Definition"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        findings: list[Finding] = []

        # Look for a Done Definition section
        has_done_section = any(
            re.search(pattern, spec_text, re.IGNORECASE) for pattern in _DONE_SECTION_PATTERNS
        )

        if not has_done_section:
            findings.append(
                Finding(
                    message="No 'Done Definition' section found",
                    severity=Severity.ERROR,
                    suggestion=(
                        "Add a '## Done Definition' section with verifiable completion criteria."
                    ),
                )
            )
            return self._fail("Missing Done Definition section", findings)

        # Extract the Done Definition section content
        done_match = None
        for pattern in _DONE_SECTION_PATTERNS:
            done_match = re.search(
                pattern + r"(.*?)(?=\n##\s|\Z)",
                spec_text,
                re.DOTALL | re.IGNORECASE,
            )
            if done_match:
                break

        done_content = done_match.group(1).strip() if done_match else ""

        if not done_content:
            findings.append(
                Finding(
                    message="Done Definition section is empty",
                    severity=Severity.ERROR,
                    suggestion=(
                        "Add specific, verifiable criteria (e.g., checkboxes, test requirements)."
                    ),
                )
            )
            return self._fail("Done Definition section is empty", findings)

        # Check for verifiable criteria
        has_verifiable = any(
            re.search(pattern, done_content, re.IGNORECASE) for pattern in _VERIFIABLE_PATTERNS
        )

        if not has_verifiable:
            findings.append(
                Finding(
                    message="Done Definition lacks verifiable criteria",
                    severity=Severity.WARNING,
                    suggestion="Add checkboxes (- [ ]), coverage thresholds, or test commands.",
                )
            )
            return self._warn("Done Definition exists but lacks verifiable criteria", findings)

        # Count criteria items
        criteria_count = len(re.findall(r"\[[ x]\]", done_content))

        return self._pass(f"Done Definition has {criteria_count} verifiable criteria")
