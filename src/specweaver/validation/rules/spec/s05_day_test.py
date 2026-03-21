# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""S05: Day Test — detects specs too large for one implementation session."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar

from specweaver.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path

# Thresholds (from static_spec_readiness_analysis.md)
_FAIL_THRESHOLD = 40.0
_WARN_THRESHOLD = 25.0

# Weights for composite score
_WEIGHT_SIZE = 0.30
_WEIGHT_SECTIONS = 0.20
_WEIGHT_BRANCHES = 0.20
_WEIGHT_STATES = 0.15
_WEIGHT_CODE_BLOCKS = 0.15


class DayTestRule(Rule):
    """Detect specs that are too complex for a single implementation session."""

    PARAM_MAP: ClassVar[dict[str, str]] = {
        "warn_threshold": "warn_threshold",
        "fail_threshold": "fail_threshold",
    }

    def __init__(
        self,
        warn_threshold: float = _WARN_THRESHOLD,
        fail_threshold: float = _FAIL_THRESHOLD,
    ) -> None:
        self._warn_threshold = warn_threshold
        self._fail_threshold = fail_threshold

    @property
    def rule_id(self) -> str:
        return "S05"

    @property
    def name(self) -> str:
        return "Day Test"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        size_kb = len(spec_text.encode("utf-8")) / 1024
        sections = spec_text.count("\n## ") + spec_text.count("\n### ")
        branch_keywords = ["if ", "when ", "unless ", "except ", "otherwise"]
        branches = sum(spec_text.lower().count(kw) for kw in branch_keywords)
        states = len(set(re.findall(r"`[A-Z][A-Z_]+`", spec_text)))
        code_blocks = spec_text.count("```") // 2  # pairs

        score = (
            size_kb * _WEIGHT_SIZE
            + sections * _WEIGHT_SECTIONS
            + branches * _WEIGHT_BRANCHES
            + states * _WEIGHT_STATES
            + code_blocks * _WEIGHT_CODE_BLOCKS
        )

        detail = (
            f"size={size_kb:.1f}KB, sections={sections}, "
            f"branches={branches}, states={states}, code_blocks={code_blocks}"
        )

        findings = [
            Finding(
                message=f"Complexity score: {score:.1f} ({detail})",
                severity=Severity.ERROR if score > self._fail_threshold else Severity.WARNING,
                suggestion="Consider splitting into smaller component specs."
                if score > self._warn_threshold
                else None,
            )
        ]

        if score > self._fail_threshold:
            return self._fail(
                f"Complexity score {score:.1f} exceeds {self._fail_threshold}",
                findings,
            )

        if score > self._warn_threshold:
            return self._warn(f"Complexity score {score:.1f} is borderline", findings)

        return self._pass(f"Complexity score: {score:.1f}")
