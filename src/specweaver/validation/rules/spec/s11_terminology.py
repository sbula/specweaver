# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""S11: Terminology Consistency — detects inconsistent naming and undefined terms.

Scans for backtick-quoted terms and checks:
1. Inconsistent casing: same concept name with different styles
   (e.g., `userId`, `user_id`, `UserID`).
2. Undefined domain terms: PascalCase terms referenced but never defined
   in a heading, code block, or data model section.

Static accuracy: ~70% (from spec_rule_research.md §Gap 3).
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING, ClassVar

from specweaver.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path

# Pattern: backtick-quoted terms (e.g., `userId`, `FlowEngine`)
_BACKTICK_TERM_RE = re.compile(r"`([A-Za-z][A-Za-z0-9_]*)`")

# Pattern: PascalCase identifiers (at least 2 uppercase letters)
_PASCAL_CASE_RE = re.compile(r"^[A-Z][a-zA-Z0-9]*(?:[A-Z][a-zA-Z0-9]*)+$")

# Pattern: fenced code blocks
_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")

# Pattern: heading lines (## or ###)
_HEADING_RE = re.compile(r"^#{1,4}\s+(.+)$", re.MULTILINE)

# Thresholds (following S08 pattern)
_WARN_THRESHOLD = 1  # 1 issue: WARN
_FAIL_THRESHOLD = 3  # 3+ issues: FAIL


def _normalize_term(term: str) -> str:
    """Normalize a term to a canonical lowercase form for grouping.

    Strips underscores, converts to lower case so that:
    userId, user_id, UserID, userid -> "userid"
    """
    return re.sub(r"_", "", term).lower()


def _extract_code_block_content(text: str) -> str:
    """Extract all content inside fenced code blocks."""
    blocks = _CODE_BLOCK_RE.findall(text)
    return "\n".join(blocks)


def _extract_heading_terms(text: str) -> set[str]:
    """Extract backtick-quoted terms from heading lines."""
    terms: set[str] = set()
    for match in _HEADING_RE.finditer(text):
        heading_text = match.group(1)
        for term_match in _BACKTICK_TERM_RE.finditer(heading_text):
            terms.add(term_match.group(1))
    return terms


def _find_line(text: str, needle: str) -> int | None:
    """Find the 1-based line number of the first occurrence of needle."""
    for i, line in enumerate(text.split("\n"), 1):
        if needle in line:
            return i
    return None


class TerminologyRule(Rule):
    """Detect inconsistent naming and undefined domain terms."""

    PARAM_MAP: ClassVar[dict[str, str]] = {
        "warn_threshold": "warn_threshold",
        "fail_threshold": "fail_threshold",
    }

    def __init__(
        self,
        warn_threshold: int = _WARN_THRESHOLD,
        fail_threshold: int = _FAIL_THRESHOLD,
    ) -> None:
        self._warn_threshold = warn_threshold
        self._fail_threshold = fail_threshold

    @property
    def rule_id(self) -> str:
        return "S11"

    @property
    def name(self) -> str:
        return "Terminology Consistency"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        if not spec_text.strip():
            return self._pass("No content to check")

        findings: list[Finding] = []

        # --- 1. Detect inconsistent casing ---
        inconsistent_findings = self._check_inconsistent_casing(spec_text)
        findings.extend(inconsistent_findings)

        # --- 2. Detect undefined domain terms ---
        undefined_findings = self._check_undefined_terms(spec_text)
        findings.extend(undefined_findings)

        total_issues = len(findings)

        if total_issues >= self._fail_threshold:
            return self._fail(
                f"Found {total_issues} terminology issues (threshold: {self._fail_threshold})",
                findings,
            )

        if total_issues >= self._warn_threshold:
            return self._warn(
                f"Found {total_issues} terminology issue(s)",
                findings,
            )

        return self._pass(f"Terminology consistent ({total_issues} issues)")

    def _check_inconsistent_casing(self, spec_text: str) -> list[Finding]:
        """Find terms that refer to the same concept with different casing."""
        # Strip code blocks to focus on prose
        cleaned = _CODE_BLOCK_RE.sub("", spec_text)

        # Extract all backtick terms from prose
        terms = _BACKTICK_TERM_RE.findall(cleaned)

        # Group by normalized form
        groups: dict[str, set[str]] = defaultdict(set)
        for term in terms:
            normalized = _normalize_term(term)
            # Skip very short terms (1-2 chars) — too generic
            if len(normalized) <= 2:
                continue
            groups[normalized].add(term)

        findings: list[Finding] = []
        for _normalized, variants in sorted(groups.items()):
            if len(variants) > 1:
                sorted_variants = sorted(variants)
                line_num = _find_line(spec_text, sorted_variants[0])
                findings.append(
                    Finding(
                        message=(
                            f"Inconsistent casing: {', '.join(f'`{v}`' for v in sorted_variants)} "
                            "appear to refer to the same term"
                        ),
                        line=line_num,
                        severity=Severity.WARNING,
                        suggestion="Choose one consistent naming convention and use it throughout.",
                    )
                )

        return findings

    def _check_undefined_terms(self, spec_text: str) -> list[Finding]:
        """Find PascalCase terms referenced in prose but never defined."""
        # Collect terms that are "defined" (appear in headings or code blocks)
        defined_terms: set[str] = set()

        # Terms in headings
        defined_terms.update(_extract_heading_terms(spec_text))

        # Terms in code blocks (class names, function names)
        code_content = _extract_code_block_content(spec_text)
        for match in _BACKTICK_TERM_RE.finditer(code_content):
            defined_terms.add(match.group(1))
        # Also scan code blocks for class/def names directly
        for class_match in re.finditer(r"\bclass\s+(\w+)", code_content):
            defined_terms.add(class_match.group(1))
        for func_match in re.finditer(r"\bdef\s+(\w+)", code_content):
            defined_terms.add(func_match.group(1))

        # Strip code blocks to get prose only
        cleaned = _CODE_BLOCK_RE.sub("", spec_text)

        # Find PascalCase terms in prose backticks
        findings: list[Finding] = []
        seen: set[str] = set()

        for match in _BACKTICK_TERM_RE.finditer(cleaned):
            term = match.group(1)

            # Only check PascalCase terms (domain objects)
            if not _PASCAL_CASE_RE.match(term):
                continue

            if term in seen or term in defined_terms:
                continue
            seen.add(term)

            line_num = _find_line(spec_text, term)
            findings.append(
                Finding(
                    message=(
                        f"Undefined domain term: `{term}` is not defined "
                        "in any heading or code block"
                    ),
                    line=line_num,
                    severity=Severity.WARNING,
                    suggestion=(
                        f"Add a definition for `{term}` in a heading (### `{term}`) or code block."
                    ),
                )
            )

        return findings
