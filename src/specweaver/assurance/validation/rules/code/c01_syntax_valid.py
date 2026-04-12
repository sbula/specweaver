# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C01: Syntax Valid — checks that generated code parses without errors."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from specweaver.assurance.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path


class SyntaxValidRule(Rule):
    """Check that the code file is valid Python syntax."""

    @property
    def rule_id(self) -> str:
        return "C01"

    @property
    def name(self) -> str:
        return "Syntax Valid"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        """Check syntax of the code file at spec_path.

        Note: For code rules, spec_text contains the code content,
        and spec_path points to the code file.
        """
        try:
            ast.parse(spec_text)
        except SyntaxError as exc:
            return self._fail(
                f"Syntax error at line {exc.lineno}: {exc.msg}",
                [
                    Finding(
                        message=f"SyntaxError: {exc.msg}",
                        line=exc.lineno,
                        severity=Severity.ERROR,
                        suggestion="Fix the syntax error before proceeding.",
                    )
                ],
            )
        return self._pass("Code parses without syntax errors")
