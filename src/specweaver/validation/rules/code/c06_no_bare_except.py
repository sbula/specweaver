# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""C06: No Bare Except — checks for bare except clauses."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from specweaver.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path


class NoBareExceptRule(Rule):
    """Check for bare 'except:' clauses (should use 'except Exception:')."""

    @property
    def rule_id(self) -> str:
        return "C06"

    @property
    def name(self) -> str:
        return "No Bare Except"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        try:
            tree = ast.parse(spec_text)
        except SyntaxError:
            return self._skip("Cannot parse file (syntax error)")

        findings: list[Finding] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                findings.append(
                    Finding(
                        message=(
                            "Bare 'except:' clause — catches all "
                            "exceptions including SystemExit"
                        ),
                        line=node.lineno,
                        severity=Severity.WARNING,
                        suggestion=(
                            "Use 'except Exception:' instead to "
                            "avoid catching SystemExit/KeyboardInterrupt."
                        ),
                    )
                )

        if findings:
            return self._warn(f"Found {len(findings)} bare except clause(s)", findings)

        return self._pass("No bare except clauses found")
