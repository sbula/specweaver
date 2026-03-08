# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""S09: Error Path Test — checks that specs define failure behavior."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from specweaver.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path

# Keywords that indicate error/failure behavior is documented
_ERROR_KEYWORDS = [
    "error",
    "exception",
    "raise",
    "raises",
    "fail",
    "failure",
    "invalid",
    "malformed",
    "reject",
    "denied",
    "timeout",
    "retry",
    "fallback",
    "abort",
]

# Section headers that indicate error handling
_ERROR_SECTION_PATTERNS = [
    r"error\s*handl",
    r"error\s*cas",
    r"failure\s*mode",
    r"exception",
    r"edge\s*cas",
]


def _extract_policy(spec_text: str) -> str:
    """Extract the Policy section (## 4. Policy) content."""
    match = re.search(
        r"##\s*4\.?\s*Policy\b(.*?)(?=\n##\s|\Z)",
        spec_text,
        re.DOTALL | re.IGNORECASE,
    )
    return match.group(1).strip() if match else ""


class ErrorPathRule(Rule):
    """Detect specs that only define the happy path without error handling."""

    @property
    def rule_id(self) -> str:
        return "S09"

    @property
    def name(self) -> str:
        return "Error Path"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        findings: list[Finding] = []
        spec_lower = spec_text.lower()

        # Count error-related keywords
        error_mentions = sum(
            len(re.findall(r"\b" + re.escape(kw) + r"\b", spec_lower)) for kw in _ERROR_KEYWORDS
        )

        # Check for error-handling sections
        has_error_section = any(
            re.search(pattern, spec_lower) for pattern in _ERROR_SECTION_PATTERNS
        )

        # Check Policy section specifically
        policy = _extract_policy(spec_text)
        policy_has_errors = bool(policy and any(kw in policy.lower() for kw in _ERROR_KEYWORDS))

        if error_mentions == 0:
            findings.append(
                Finding(
                    message="No error/failure keywords found in entire spec",
                    severity=Severity.ERROR,
                    suggestion="Add error handling to Policy section (## 4. Policy). "
                    "Define what happens when operations fail.",
                )
            )
            return self._fail("Spec defines no error behavior", findings)

        if not has_error_section and not policy_has_errors:
            findings.append(
                Finding(
                    message=f"Found {error_mentions} error keywords but no dedicated error section",
                    severity=Severity.WARNING,
                    suggestion=(
                        "Consider adding an 'Error Handling' "
                        "subsection to Policy (## 4. Policy)."
                    ),
                )
            )
            return self._warn("Error keywords found but no structured error section", findings)

        return self._pass(
            f"Error coverage: {error_mentions} keywords, "
            f"error section: {'yes' if has_error_section else 'no'}, "
            f"policy errors: {'yes' if policy_has_errors else 'no'}"
        )
