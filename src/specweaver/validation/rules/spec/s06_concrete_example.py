# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""S06: Concrete Example Test — checks for real input/output examples."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from specweaver.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path


def _extract_contract(spec_text: str) -> str:
    """Extract the Contract section (## 2. Contract) content."""
    match = re.search(
        r"##\s*2\.?\s*Contract\b(.*?)(?=\n##\s|\Z)",
        spec_text,
        re.DOTALL | re.IGNORECASE,
    )
    return match.group(1).strip() if match else ""


class ConcreteExampleRule(Rule):
    """Detect specs without concrete input/output examples."""

    @property
    def rule_id(self) -> str:
        return "S06"

    @property
    def name(self) -> str:
        return "Concrete Example"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        contract = _extract_contract(spec_text)

        # Check for code blocks in Contract section
        code_blocks_in_contract = len(re.findall(r"```", contract)) // 2

        # Check for code blocks anywhere in the spec
        code_blocks_total = len(re.findall(r"```", spec_text)) // 2

        # Check for example/assert patterns
        has_examples = bool(re.search(
            r"(?:example|input|output|assert|->|=>|-->|returns?)\s*[:=]",
            spec_text,
            re.IGNORECASE,
        ))

        findings: list[Finding] = []

        if code_blocks_in_contract == 0 and not contract:
            findings.append(Finding(
                message="No Contract section found",
                severity=Severity.ERROR,
                suggestion="Add a '## 2. Contract' section with interface definitions and examples.",
            ))
            return self._fail("Missing Contract section", findings)

        if code_blocks_in_contract == 0:
            findings.append(Finding(
                message="Contract section has no code blocks",
                severity=Severity.ERROR,
                suggestion="Add at least one code block with concrete input -> output example.",
            ))

        if code_blocks_total == 0:
            findings.append(Finding(
                message="Entire spec has no code blocks",
                severity=Severity.ERROR,
                suggestion="A spec without code examples cannot be implemented precisely.",
            ))
            return self._fail("No code blocks found anywhere in spec", findings)

        if code_blocks_in_contract == 0 and not has_examples:
            return self._fail("No concrete examples in Contract section", findings)

        if code_blocks_in_contract == 0:
            return self._warn("Contract lacks code blocks but examples found elsewhere", findings)

        return self._pass(f"Contract has {code_blocks_in_contract} code block(s)")
