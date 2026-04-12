# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""S03: Stranger Test — checks if a spec is self-contained.

An LLM-dependent rule: can a developer unfamiliar with the project
understand and implement this spec by reading only this document?

Requires an LLM adapter to judge quality of cross-references.
In static mode, this rule SKIPS.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar

from specweaver.assurance.validation.models import Finding, Rule, RuleResult, Severity

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

    PARAM_MAP: ClassVar[dict[str, str]] = {
        "warn_threshold": "warn_threshold",
        "fail_threshold": "fail_threshold",
    }

    def __init__(
        self,
        warn_threshold: int = _WARN_THRESHOLD,
        fail_threshold: int = _FAIL_THRESHOLD,
        mode: str | None = None,
    ) -> None:
        self._warn_threshold = warn_threshold
        self._fail_threshold = fail_threshold
        self._mode = mode

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
        if self._mode == "abstraction_leak":
            return self._check_abstraction_leaks(spec_text)
        return self._check_external_refs(spec_text, spec_path)

    def _check_abstraction_leaks(self, spec_text: str) -> RuleResult:
        """Feature mode: flag implementation-level detail in business-level spec."""
        cleaned = _strip_code_blocks(spec_text)
        findings: list[Finding] = []

        # 1. File paths (contain / or \ with file extensions)
        for match in re.finditer(r"[\w./\\]+\.(?:py|ts|js|java|go|rs|yaml|json|toml)\b", cleaned):
            line_num = _find_line(spec_text, match.group())
            findings.append(
                Finding(
                    message=f"Abstraction leak: file path '{match.group()}'",
                    line=line_num,
                    severity=Severity.WARNING,
                    suggestion="Feature Specs should reference services/modules, not file paths.",
                )
            )

        # 2. Class.method references (e.g. `TaxCalculator.calculate()`)
        for match in re.finditer(r"`([A-Z][a-zA-Z]+\.[a-z_][a-zA-Z_]*\(\))`", cleaned):
            line_num = _find_line(spec_text, match.group(1))
            findings.append(
                Finding(
                    message=f"Abstraction leak: class.method '{match.group(1)}'",
                    line=line_num,
                    severity=Severity.WARNING,
                    suggestion="Feature Specs should describe behavior, not specific method calls.",
                )
            )

        # 3. Dotted import paths (3+ segments, e.g. specweaver.assurance.validation.runner)
        for match in re.finditer(r"`([a-z][a-z_]*(?:\.[a-z][a-z_]*){2,})`", cleaned):
            line_num = _find_line(spec_text, match.group(1))
            findings.append(
                Finding(
                    message=f"Abstraction leak: import path '{match.group(1)}'",
                    line=line_num,
                    severity=Severity.WARNING,
                    suggestion="Feature Specs should reference modules by name, not import paths.",
                )
            )

        if len(findings) > self._fail_threshold:
            return self._fail(
                f"{len(findings)} abstraction leaks found. "
                "Feature Spec contains implementation-level detail.",
                findings,
            )

        if len(findings) > 0:
            return self._warn(
                f"{len(findings)} abstraction leak(s) found. "
                "Consider using service/module names instead.",
                findings,
            )

        return self._pass("No abstraction leaks detected")

    def _check_external_refs(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        """Component mode (default): count external links and undefined terms."""
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
    for match in re.finditer(r"`([A-Z][a-zA-Z_]{3,})`\s*(?:is|refers|:|—)", text, re.MULTILINE):
        defined.add(match.group(1))

    return defined
