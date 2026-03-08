# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""S01: One-Sentence Test — detects specs with multiple responsibilities."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from specweaver.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path

# Conjunctions that signal multiple responsibilities in Purpose section
_CONJUNCTIONS = [
    "and also",
    "additionally",
    "furthermore",
    "as well as",
    "along with",
    "in addition to",
    "on top of that",
]


def _extract_purpose(spec_text: str) -> str:
    """Extract the Purpose section (## 1. Purpose) content."""
    match = re.search(
        r"##\s*1\.?\s*Purpose\b(.*?)(?=\n##\s|\Z)",
        spec_text,
        re.DOTALL | re.IGNORECASE,
    )
    return match.group(1).strip() if match else ""


class OneSentenceRule(Rule):
    """Detect specs that try to do too many things at once."""

    @property
    def rule_id(self) -> str:
        return "S01"

    @property
    def name(self) -> str:
        return "One-Sentence Test"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        purpose = _extract_purpose(spec_text)
        findings: list[Finding] = []

        if not purpose:
            return self._warn(
                "No Purpose section found",
                [
                    Finding(
                        message="Could not find '## 1. Purpose' section", severity=Severity.WARNING
                    )
                ],
            )

        # Count conjunctions in Purpose
        conjunction_count = 0
        purpose_lower = purpose.lower()
        for conj in _CONJUNCTIONS:
            count = purpose_lower.count(conj)
            if count > 0:
                conjunction_count += count
                findings.append(
                    Finding(
                        message=f"Found conjunction '{conj}' ({count}x) in Purpose section",
                        severity=Severity.ERROR,
                        suggestion=(
                            "Each conjunction may indicate a "
                            "separate responsibility. Consider splitting."
                        ),
                    )
                )

        # Count H2 sections in entire spec
        h2_count = len(re.findall(r"\n##\s", spec_text))

        if h2_count > 8:
            findings.append(
                Finding(
                    message=f"Spec has {h2_count} H2 sections (max recommended: 8)",
                    severity=Severity.WARNING,
                    suggestion=(
                        "Many sections may indicate multiple "
                        "concerns. Consider decomposition."
                    ),
                )
            )

        if conjunction_count > 2:
            return self._fail(
                f"Purpose has {conjunction_count} responsibility conjunctions",
                findings,
            )

        if conjunction_count > 0 or h2_count > 8:
            return self._warn(
                f"Conjunctions: {conjunction_count}, H2 sections: {h2_count}",
                findings,
            )

        return self._pass(f"Purpose is focused (conjunctions: {conjunction_count}, H2: {h2_count})")
