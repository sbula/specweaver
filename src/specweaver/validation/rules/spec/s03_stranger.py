# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""S03: Stranger Test — checks if a spec is self-contained.

An LLM-dependent rule: can a developer unfamiliar with the project
understand and implement this spec by reading only this document?

Requires an LLM adapter to judge quality of cross-references.
In static mode, this rule SKIPS.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from specweaver.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path

# Pattern: markdown links to other files
_EXT_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

# Undefined term patterns: backtick references that look like
# they refer to external concepts without definition
_UNDEFINED_TERM_RE = re.compile(r"`([A-Z][a-zA-Z_]{3,})`")

# Max cross-references before static heuristic warns
_WARN_THRESHOLD = 5
_FAIL_THRESHOLD = 10


class StrangerTestRule(Rule):
    """Detect specs that are not self-contained enough for a stranger to implement."""

    def __init__(
        self,
        warn_threshold: int = _WARN_THRESHOLD,
        fail_threshold: int = _FAIL_THRESHOLD,
    ) -> None:
        self._warn_threshold = warn_threshold
        self._fail_threshold = fail_threshold

    @property
    def rule_id(self) -> str:
        return "S03"

    @property
    def name(self) -> str:
        return "Stranger Test"

    @property
    def requires_llm(self) -> bool:
        """Full analysis needs LLM, but static heuristic runs without."""
        return False

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        """Static heuristic: count external links and undefined terms."""
        # Strip code blocks to avoid false positives
        cleaned = _strip_code_blocks(spec_text)

        findings: list[Finding] = []

        # 1. Count external links (to other files/URLs)
        ext_links = _EXT_LINK_RE.findall(cleaned)
        external_count = 0
        for text, href in ext_links:
            # Skip anchors within current doc and simple URLs
            if href.startswith("#") or href.startswith("http"):
                continue
            external_count += 1
            line_num = _find_line(spec_text, href)
            findings.append(
                Finding(
                    message=f"External reference: [{text}]({href})",
                    line=line_num,
                    severity=Severity.INFO,
                )
            )

        # 2. Count undefined backtick terms
        # A "defined" term appears in a header or is preceded by a definition pattern
        all_terms = set(_UNDEFINED_TERM_RE.findall(cleaned))
        defined_terms = _get_defined_terms(spec_text)
        undefined = all_terms - defined_terms

        for term in sorted(undefined):
            line_num = _find_line(spec_text, term)
            findings.append(
                Finding(
                    message=f"Term `{term}` used but not defined in this spec",
                    line=line_num,
                    severity=Severity.WARNING,
                )
            )

        total_issues = external_count + len(undefined)

        if total_issues > self._fail_threshold:
            return self._fail(
                f"{total_issues} external dependencies found. "
                "A stranger would need to read too many other documents.",
                findings,
            )

        if total_issues > self._warn_threshold:
            return self._warn(
                f"{total_issues} external dependencies found. "
                "Consider defining referenced concepts inline.",
                findings,
            )

        return self._pass(f"{total_issues} external dependencies (within threshold)")


def _strip_code_blocks(text: str) -> str:
    """Remove fenced code blocks to avoid false positives."""
    return re.sub(r"```[\s\S]*?```", "", text)


def _find_line(text: str, needle: str) -> int | None:
    """Find the 1-based line number of the first occurrence of needle."""
    for i, line in enumerate(text.split("\n"), 1):
        if needle in line:
            return i
    return None


def _get_defined_terms(text: str) -> set[str]:
    """Extract terms that are defined within the spec via headers or definitions."""
    defined: set[str] = set()

    # Terms in headers (## SomeComponent)
    for match in re.finditer(r"^#{1,4}\s+.*?`([A-Z][a-zA-Z_]{3,})`", text, re.MULTILINE):
        defined.add(match.group(1))

    # Terms after "is a", "refers to", ":"
    for match in re.finditer(
        r"`([A-Z][a-zA-Z_]{3,})`\s*(?:is|refers|:|—)", text, re.MULTILINE
    ):
        defined.add(match.group(1))

    return defined
