# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C03: Tests Pass — runs pytest on the test file and checks results.

Delegates pytest execution to the shared PythonQARunner from the
commons layer, eliminating duplicate subprocess handling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.assurance.validation.models import Finding, Rule, RuleResult, Severity
from specweaver.core.loom.commons.language.python.runner import PythonQARunner

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

        # Delegate to PythonQARunner
        runner = PythonQARunner(cwd=project_root)
        try:
            result = runner.run_tests(
                target=str(test_file.relative_to(project_root)),
                kind="",  # no marker filter
                timeout=60,
            )
        except TimeoutError:
            return self._fail(
                "Tests timed out after 60 seconds",
                [Finding(message="Test execution timed out", severity=Severity.ERROR)],
            )

        if result.failed == 0 and result.errors == 0:
            return self._pass(f"All tests in {test_file.name} passed")

        # Build failure message from structured results
        failure_msgs = [f.message for f in result.failures]
        if failure_msgs:
            message = "; ".join(failure_msgs)
            # Truncate to 500 chars for consistency
            message = message[-500:]
        else:
            message = "No output"

        return self._fail(
            "Tests failed",
            [
                Finding(
                    message=message,
                    severity=Severity.ERROR,
                    suggestion="Fix failing tests before proceeding.",
                )
            ],
        )
