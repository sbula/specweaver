# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C05: Import Direction — checks that imports follow layering rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path

# Allowed import layers (lower -> cannot import higher)
# For now, a simple check: implementation should not import from CLI
_FORBIDDEN_IMPORTS = [
    "specweaver.cli",  # No component should import from CLI
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

        from specweaver.config.dal_resolver import DALResolver
        from specweaver.loom.commons.qa_runner.factory import resolve_runner

        logger = logging.getLogger(__name__)

        try:
            cwd = spec_path.parent
            runner = resolve_runner(cwd)

            # Resolve the active DAL for this boundary
            resolver = DALResolver(project_root=cwd)
            dal_enum = resolver.resolve(target_path=spec_path)

            result = runner.run_architecture_check(target=str(spec_path.absolute()), dal_level=dal_enum)
        except Exception as e:
            logger.warning("C05 architecture check failed: %s", e)
            return self._skip(f"Architecture engine failure: {e}")

        if result.violation_count == 0:
            return self._pass("All imports follow layering rules")

        findings: list[Finding] = []

        for viol in result.violations:
            findings.append(
                Finding(
                    message=f"Architecture boundary violated: {viol.message}",
                    line=0,
                    severity=Severity.ERROR,
                    suggestion=f"See architectural boundary configuration (Code: {viol.code}).",
                )
            )

        if findings:
            return self._fail(
                f"Found {result.violation_count} architectural violation(s)", findings
            )

        return self._fail("Architectural violations detected.", [])
