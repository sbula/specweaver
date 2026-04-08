# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C08: Type Hints — checks that public functions have type annotations."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from specweaver.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path


class TypeHintsRule(Rule):
    """Check that public functions have return type annotations."""

    @property
    def rule_id(self) -> str:
        return "C08"

    @property
    def name(self) -> str:
        return "Type Hints"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        try:
            tree = ast.parse(spec_text)
        except SyntaxError:
            return self._skip("Cannot parse file (syntax error)")

        findings: list[Finding] = []
        total_public = 0
        missing_hints = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip private/dunder methods
                if node.name.startswith("_"):
                    continue

                total_public += 1

                if node.returns is None:
                    missing_hints += 1
                    findings.append(
                        Finding(
                            message=f"Function '{node.name}' missing return type annotation",
                            line=node.lineno,
                            severity=Severity.WARNING,
                            suggestion=f"Add return type: def {node.name}(...) -> <type>:",
                        )
                    )

        if total_public == 0:
            return self._pass("No public functions to check")

        if missing_hints > 0:
            ratio = (total_public - missing_hints) / total_public * 100
            if ratio < 50:
                msg = (
                    f"{missing_hints}/{total_public} public "
                    f"functions missing type hints ({ratio:.0f}%)"
                )
                return self._fail(msg, findings)
            msg = (
                f"{missing_hints}/{total_public} public functions missing type hints ({ratio:.0f}%)"
            )
            return self._warn(msg, findings)

        return self._pass(f"All {total_public} public functions have return type annotations")
