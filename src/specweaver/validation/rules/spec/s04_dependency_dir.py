# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""S04: Dependency Direction — detects upward/peer cross-references in specs.

Scans for markdown links and explicit references to other specs.
Flags references that go upward or sideways in the architecture,
indicating entanglement with peer components.

Static accuracy: ~90% (from spec_methodology.md §7).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from specweaver.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    pass

# Pattern: markdown links like [text](path/to/spec.md)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+\.md)\)")

# Pattern: explicit cross-references like "see §3" or "see Section 3"
_SECTION_REF_RE = re.compile(r"see\s+(?:§|section\s+)\d+", re.IGNORECASE)

# Pattern: backtick references to other components (e.g., `FlowEngine`)
_COMPONENT_REF_RE = re.compile(r"`([A-Z][a-zA-Z]+(?:Service|Engine|Manager|Provider|Adapter|Handler|Store|Client))`")

# Max cross-references before we warn (from spec_methodology.md §8.3)
_WARN_THRESHOLD = 5
_FAIL_THRESHOLD = 8


class DependencyDirectionRule(Rule):
    """Detect specs with too many cross-references to other components."""

    @property
    def rule_id(self) -> str:
        return "S04"

    @property
    def name(self) -> str:
        return "Dependency Direction"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        # Strip code blocks to avoid false positives
        cleaned = _strip_code_blocks(spec_text)

        findings: list[Finding] = []

        # 1. Count markdown links to other .md files + check dead links
        md_links = _MD_LINK_RE.findall(cleaned)
        for text, href in md_links:
            line_num = _find_line(spec_text, href)
            findings.append(
                Finding(
                    message=f"Cross-reference: [{text}]({href})",
                    line=line_num,
                    severity=Severity.INFO,
                )
            )

            # Traceability: check if the linked file exists
            if spec_path is not None:
                target = spec_path.parent / href
                if not target.exists():
                    findings.append(
                        Finding(
                            message=f"Dead link: [{text}]({href}) — file not found",
                            line=line_num,
                            severity=Severity.WARNING,
                            suggestion=f"Verify that '{href}' exists relative to this spec.",
                        )
                    )

        # 2. Count explicit section references ("see §3")
        section_refs = _SECTION_REF_RE.findall(cleaned)
        for ref in section_refs:
            line_num = _find_line(spec_text, ref)
            findings.append(
                Finding(
                    message=f"Section reference: '{ref}'",
                    line=line_num,
                    severity=Severity.INFO,
                )
            )

        # 3. Count component name references in backticks
        component_refs = _COMPONENT_REF_RE.findall(cleaned)
        # Deduplicate but keep count
        unique_components = set(component_refs)
        for comp in sorted(unique_components):
            line_num = _find_line(spec_text, comp)
            findings.append(
                Finding(
                    message=f"Component reference: `{comp}`",
                    line=line_num,
                    severity=Severity.INFO,
                )
            )

        total_refs = len(md_links) + len(section_refs) + len(unique_components)

        # Separate dead-link findings from informational cross-ref findings
        dead_link_findings = [f for f in findings if f.severity == Severity.WARNING]

        if total_refs > _FAIL_THRESHOLD:
            return self._fail(
                f"{total_refs} cross-references found (threshold: {_FAIL_THRESHOLD}). "
                "This spec may be entangled with too many peer components.",
                findings,
            )

        if total_refs > _WARN_THRESHOLD:
            return self._warn(
                f"{total_refs} cross-references found (threshold: {_WARN_THRESHOLD}). "
                "Consider reducing external dependencies.",
                findings,
            )

        # Even if cross-ref count is fine, report dead links as warnings
        if dead_link_findings:
            return self._warn(
                f"{total_refs} cross-references (within threshold), "
                f"but {len(dead_link_findings)} dead link(s) found",
                findings,
            )

        return self._pass(f"{total_refs} cross-references (within threshold)")


def _strip_code_blocks(text: str) -> str:
    """Remove fenced code blocks to avoid false positives."""
    return re.sub(r"```[\s\S]*?```", "", text)


def _find_line(text: str, needle: str) -> int | None:
    """Find the 1-based line number of the first occurrence of needle."""
    for i, line in enumerate(text.split("\n"), 1):
        if needle in line:
            return i
    return None
