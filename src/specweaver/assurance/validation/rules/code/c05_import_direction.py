# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C05: Import Direction — checks pre-hydrated architecture results.

Reads architecture check results from self.context["qa_architecture_result"],
which is populated by the flow layer's validation hydrator (AD-4, AD-5).
No sandbox imports — this rule is pure logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.assurance.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path


class ImportDirectionRule(Rule):
    """Check that imports follow the correct layering direction."""

    @property
    def rule_id(self) -> str:
        return "C05"

    @property
    def name(self) -> str:
        return "Import Direction"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        if not spec_path:
            return self._skip("Cannot run architecture checks without a file path")

        # Read pre-hydrated QA results from context
        result_data = self.context.get("qa_architecture_result")
        if result_data is None:
            return self._skip(
                "Architecture check results not available (QA context not hydrated)"
            )

        exports = result_data.get("exports") or {}
        violation_count = exports.get("violation_count", 0)

        if violation_count == 0:
            return self._pass("All imports follow layering rules")

        findings: list[Finding] = []

        violations = exports.get("violations", [])
        for viol in violations:
            msg = viol.get("message", "Unknown violation")
            code = viol.get("code", "UNKNOWN")
            findings.append(
                Finding(
                    message=f"Architecture boundary violated: {msg}",
                    line=0,
                    severity=Severity.ERROR,
                    suggestion=f"See architectural boundary configuration (Code: {code}).",
                )
            )

        if findings:
            return self._fail(f"Found {violation_count} architectural violation(s)", findings)

        return self._fail("Architectural violations detected.", [])
