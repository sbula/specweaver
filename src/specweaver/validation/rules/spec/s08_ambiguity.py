# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""S08: Ambiguity Test — detects weasel words that leave decisions unmade."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar

from specweaver.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path

# Weasel word taxonomy from completeness_tests.md
_WEASEL_WORDS: dict[str, list[str]] = {
    "vague_obligation": ["should", "might", "could", "may"],
    "deferred_decisions": ["tbd", "todo", "to be determined", "to be decided", "later"],
    "subjective_judgment": [
        "as appropriate",
        "as needed",
        "reasonable",
        "sufficient",
        "adequate",
    ],
    "hand_waving": [
        "properly",
        "correctly",
        "efficiently",
        "seamlessly",
        "appropriately",
    ],
    "hidden_options": ["optionally", "possibly", "alternatively", "consider"],
}

# Maximum weasel words before FAIL (L2 component level = strict)
_MAX_WEASEL_WARN = 1
_MAX_WEASEL_FAIL = 3


def _is_inside_code_block(text: str, position: int) -> bool:
    """Check if a position in text is inside a fenced code block."""
    preceding = text[:position]
    # Count triple-backtick markers before this position
    markers = len(re.findall(r"```", preceding))
    # Odd count means we're inside a code block
    return markers % 2 == 1


class AmbiguityRule(Rule):
    """Detect weasel words that leave implementation decisions unmade."""

    PARAM_MAP: ClassVar[dict[str, str]] = {
        "warn_threshold": "warn_threshold",
        "fail_threshold": "fail_threshold",
    }

    def __init__(
        self,
        warn_threshold: int = _MAX_WEASEL_WARN,
        fail_threshold: int = _MAX_WEASEL_FAIL,
    ) -> None:
        self._warn_threshold = warn_threshold
        self._fail_threshold = fail_threshold

    @property
    def rule_id(self) -> str:
        return "S08"

    @property
    def name(self) -> str:
        return "Ambiguity Test"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        findings: list[Finding] = []
        total_weasels = 0
        spec_lower = spec_text.lower()

        for category, words in _WEASEL_WORDS.items():
            for word in words:
                # Find all occurrences
                for match in re.finditer(re.escape(word), spec_lower):
                    # Skip matches inside code blocks
                    if _is_inside_code_block(spec_text, match.start()):
                        continue

                    # Find line number
                    line_num = spec_text[: match.start()].count("\n") + 1

                    total_weasels += 1
                    findings.append(
                        Finding(
                            message=f"Weasel word '{word}' ({category})",
                            line=line_num,
                            severity=Severity.WARNING
                            if total_weasels <= self._warn_threshold
                            else Severity.ERROR,
                            suggestion="Replace with a concrete, measurable statement.",
                        )
                    )

        if total_weasels > self._fail_threshold:
            return self._fail(
                f"Found {total_weasels} weasel words (max: {self._fail_threshold})",
                findings,
            )

        if total_weasels > self._warn_threshold:
            return self._warn(
                f"Found {total_weasels} weasel words (warning at >{self._warn_threshold})",
                findings,
            )

        return self._pass(f"Weasel words: {total_weasels}")
