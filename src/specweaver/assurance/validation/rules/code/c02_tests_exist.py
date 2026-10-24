# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C02: Tests Exist — checks that a corresponding test file exists."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.assurance.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path


class TestsExistRule(Rule):
    """Check that a test file exists for the given source file."""

    @property
    def rule_id(self) -> str:
        return "C02"

    @property
    def name(self) -> str:
        return "Tests Exist"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        if spec_path is None:
            return self._skip("No file path provided")

        from specweaver.assurance.validation.project_root import find_tests

        found = find_tests(spec_path, self.context.get("project_root"))
        if not isinstance(found, str):
            return self._pass(f"Test file found: {found}")
        if found.startswith("no test convention"):
            return self._skip(found)
        return self._fail(
            found,
            [
                Finding(
                    message=f"{found} by the language's convention",
                    severity=Severity.ERROR,
                    suggestion="Create the test file where the language keeps its tests",
                )
            ],
        )
