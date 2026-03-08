# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""C03: Tests Pass — runs pytest on the test file and checks results."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from specweaver.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path


class TestsPassRule(Rule):
    """Run pytest and check that all tests pass."""

    @property
    def rule_id(self) -> str:
        return "C03"

    @property
    def name(self) -> str:
        return "Tests Pass"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        if spec_path is None:
            return self._skip("No file path provided")

        # Derive test file
        test_name = f"test_{spec_path.stem}.py"

        # Find project root (look for pyproject.toml)
        project_root = spec_path.parent
        while project_root != project_root.parent:
            if (project_root / "pyproject.toml").exists():
                break
            project_root = project_root.parent

        # Find test file
        tests_dir = project_root / "tests"
        if not tests_dir.is_dir():
            return self._skip("No tests/ directory found")

        matches = list(tests_dir.rglob(test_name))
        if not matches:
            return self._skip(f"No test file '{test_name}' found")

        test_file = matches[0]

        try:
            result = subprocess.run(
                ["python", "-m", "pytest", str(test_file), "-q", "--tb=line"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(project_root),
            )
        except subprocess.TimeoutExpired:
            return self._fail(
                "Tests timed out after 60 seconds",
                [Finding(message="Test execution timed out", severity=Severity.ERROR)],
            )

        if result.returncode == 0:
            return self._pass(f"All tests in {test_file.name} passed")

        return self._fail(
            "Tests failed",
            [Finding(
                message=result.stdout[-500:] if result.stdout else "No output",
                severity=Severity.ERROR,
                suggestion="Fix failing tests before proceeding.",
            )],
        )
