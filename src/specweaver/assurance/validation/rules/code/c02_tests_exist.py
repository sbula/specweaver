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

        # Derive expected test file name
        name = spec_path.stem
        test_name = f"test_{name}.py"

        # Look in common test directories
        project_root = spec_path.parent
        while project_root != project_root.parent:
            tests_dir = project_root / "tests"
            if tests_dir.is_dir():
                # Search recursively for the test file
                matches = list(tests_dir.rglob(test_name))
                if matches:
                    return self._pass(f"Test file found: {matches[0]}")
            project_root = project_root.parent

        return self._fail(
            f"No test file '{test_name}' found",
            [
                Finding(
                    message=f"Expected test file '{test_name}' not found in any tests/ directory",
                    severity=Severity.ERROR,
                    suggestion=f"Create a test file: tests/unit/{test_name}",
                )
            ],
        )
