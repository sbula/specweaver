# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C05: Import Direction — reads the hydrated result of the shared boundary check.

`self.context["qa_architecture_result"]` holds the QA atom's `run_architecture` exports: the
violations of the boundary rule and of the extra tools the project configured, the imports not
mapped to a project folder, a note when nothing was judged, and each extra's run. No sandbox
imports — this rule is pure logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
            return self._skip("Architecture check results not available (QA context not hydrated)")

        exports = result_data.get("exports") or {}
        if "violation_count" not in exports:
            reason = result_data.get("message") or "no architecture results"
            return self._fail(
                f"Architecture check could not run: {reason}",
                [
                    Finding(
                        message=f"Architecture check could not run: {reason}",
                        severity=Severity.ERROR,
                    )
                ],
            )
        violation_count = exports.get("violation_count", 0)
        # A note with no violation means nothing was judged (no context.yaml covers the file): no
        # verdict to pass.
        if not violation_count and exports.get("note"):
            return self._skip(str(exports["note"]))

        if violation_count == 0:
            return self._clean(exports)

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

    def _clean(self, exports: dict[str, Any]) -> RuleResult:
        """PASS, unless a configured extra tool did not run: that is a WARN naming it."""
        not_run = [e for e in exports.get("extras") or [] if not e.get("ran")]
        if not_run:
            said = "; ".join(
                f"{e['tool']} is configured but did not run: {e['reason']}" for e in not_run
            )
            findings = [Finding(message=said, severity=Severity.WARNING)]
            return self._warn(f"Boundary rule passed; {said}", findings)
        unmapped = exports.get("unmapped", 0)
        return self._pass(
            f"All imports follow the boundary rule; {unmapped} imports not mapped to a project folder"
        )
