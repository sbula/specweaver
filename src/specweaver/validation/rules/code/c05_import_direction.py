# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""C05: Import Direction — checks that imports follow layering rules."""

from __future__ import annotations

import ast
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
    """Check that imports follow the correct layering direction."""

    @property
    def rule_id(self) -> str:
        return "C05"

    @property
    def name(self) -> str:
        return "Import Direction"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        try:
            tree = ast.parse(spec_text)
        except SyntaxError:
            return self._skip("Cannot parse file (syntax error)")

        findings: list[Finding] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in _FORBIDDEN_IMPORTS:
                        findings.append(
                            Finding(
                                message=f"Forbidden import: '{alias.name}'",
                                line=node.lineno,
                                severity=Severity.ERROR,
                                suggestion="Components should not import from the CLI layer.",
                            )
                        )
            elif isinstance(node, ast.ImportFrom) and node.module:
                for forbidden in _FORBIDDEN_IMPORTS:
                    if node.module == forbidden or node.module.startswith(forbidden + "."):
                        findings.append(
                            Finding(
                                message=f"Forbidden import from: '{node.module}'",
                                line=node.lineno,
                                severity=Severity.ERROR,
                                suggestion="Components should not import from the CLI layer.",
                            )
                        )

        if findings:
            return self._fail(f"Found {len(findings)} forbidden import(s)", findings)

        return self._pass("All imports follow layering rules")
