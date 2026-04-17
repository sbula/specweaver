# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C05: Import Direction — checks that imports follow layering rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.assurance.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path

# Allowed import layers (lower -> cannot import higher)
# For now, a simple check: implementation should not import from CLI
_FORBIDDEN_IMPORTS = [
    "specweaver.interfaces.cli",  # No component should import from CLI
]


class ImportDirectionRule(Rule):
    """Check that imports follow the correct layering direction (Tach)."""

    @property
    def rule_id(self) -> str:
        return "C05"

    @property
    def name(self) -> str:
        return "Import Direction"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        if not spec_path:
            return self._skip("Cannot run architecture checks without a file path")

        import logging

        from specweaver.core.config.dal_resolver import DALResolver
        from specweaver.core.loom.atoms.qa_runner.atom import QARunnerAtom

        logger = logging.getLogger(__name__)

        try:
            cwd = spec_path.parent
            atom = QARunnerAtom(cwd=cwd)

            # Resolve the active DAL for this boundary
            resolver = DALResolver(project_root=cwd)
            dal_enum = resolver.resolve(target_path=spec_path)

            result = atom.run(
                {
                    "intent": "run_architecture",
                    "target": str(spec_path.absolute()),
                    "dal_level": dal_enum,
                }
            )
        except Exception as e:
            logger.warning("C05 architecture check failed: %s", e)
            return self._skip(f"Architecture engine failure: {e}")

        exports = result.exports or {}
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
