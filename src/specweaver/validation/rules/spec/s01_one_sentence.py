# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""S01: One-Sentence Test — detects specs with multiple responsibilities."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar

from specweaver.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.validation.spec_kind import SpecKind

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

    PARAM_MAP: ClassVar[dict[str, str]] = {
        "warn_threshold": "warn_conjunctions",
        "fail_threshold": "fail_conjunctions",
        "extra:max_h2": "max_h2",
    }

    def __init__(
        self,
        warn_conjunctions: int = 0,
        fail_conjunctions: int = 2,
        max_h2: int = 8,
        kind: SpecKind | None = None,
        header_pattern: re.Pattern[str] | None = None,
    ) -> None:
        self._warn_conjunctions = warn_conjunctions
        self._fail_conjunctions = fail_conjunctions
        self._max_h2 = max_h2
        self._kind = kind
        # Auto-resolve header pattern from kind if not explicitly set
        self._header_pattern: re.Pattern[str] | None
        if header_pattern is not None:
            self._header_pattern = header_pattern
        elif kind is not None:
            from specweaver.validation.spec_kind import _HEADER_PATTERNS
            self._header_pattern = _HEADER_PATTERNS.get(kind)
        else:
            self._header_pattern = None

    @property
    def rule_id(self) -> str:
        return "S01"

    @property
    def name(self) -> str:
        return "One-Sentence Test"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        purpose = self._extract_purpose(spec_text)
        findings: list[Finding] = []

        if not purpose:
            header_name = "## Intent" if self._kind == "feature" else "## 1. Purpose"
            return self._warn(
                f"No {header_name} section found",
                [
                    Finding(
                        message=f"Could not find '{header_name}' section",
                        severity=Severity.WARNING,
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

        if h2_count > self._max_h2:
            findings.append(
                Finding(
                    message=f"Spec has {h2_count} H2 sections (max recommended: {self._max_h2})",
                    severity=Severity.WARNING,
                    suggestion=(
                        "Many sections may indicate multiple "
                        "concerns. Consider decomposition."
                    ),
                )
            )

        if conjunction_count > self._fail_conjunctions:
            return self._fail(
                f"Purpose has {conjunction_count} responsibility conjunctions",
                findings,
            )

        if conjunction_count > self._warn_conjunctions or h2_count > self._max_h2:
            return self._warn(
                f"Conjunctions: {conjunction_count}, H2 sections: {h2_count}",
                findings,
            )

        return self._pass(f"Purpose is focused (conjunctions: {conjunction_count}, H2: {h2_count})")

    def _extract_purpose(self, spec_text: str) -> str:
        """Extract purpose/intent section using the appropriate header pattern."""
        if self._header_pattern is not None:
            match = self._header_pattern.search(spec_text)
        else:
            match = re.search(
                r"##\s*1\.?\s*Purpose\b(.*?)(?=\n##\s|\Z)",
                spec_text,
                re.DOTALL | re.IGNORECASE,
            )
        return match.group(1).strip() if match else ""

