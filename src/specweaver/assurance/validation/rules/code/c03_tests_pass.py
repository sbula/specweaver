# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C03: Tests Pass — checks pre-hydrated test execution results.

Reads test results from self.context["qa_tests_result"], which is
populated by the flow layer's validation hydrator (AD-4, AD-5).
No sandbox imports — this rule is pure logic.
"""

from __future__ import annotations

from pathlib import Path

from specweaver.assurance.validation.models import Finding, Rule, RuleResult, Severity


class TestsPassRule(Rule):
    """Check that all tests pass using pre-hydrated QA context."""

    @property
    def rule_id(self) -> str:
        return "C03"

    @property
    def name(self) -> str:
        return "Tests Pass"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        if spec_path is None:
            return self._skip("No file path provided")

        test_file = self._located_test_file(spec_path)
        if isinstance(test_file, str):
            return self._skip(test_file)

        # Read pre-hydrated QA results from context
        result_data = self.context.get("qa_tests_result")
        if result_data is None:
            return self._fail(
                "Test execution results not available (QA context not hydrated)",
                [Finding(message="Rule requires pre-hydrated QA context", severity=Severity.ERROR)],
            )

        # Check for timeout
        if (
            result_data.get("status") == "FAILED"
            and "timed out" in (result_data.get("message") or "").lower()
        ):
            return self._fail(
                "Tests timed out after 60 seconds",
                [Finding(message="Test execution timed out", severity=Severity.ERROR)],
            )

        exports = result_data.get("exports") or {}
        if "failed" not in exports:
            reason = result_data.get("message") or "no test results"
            return self._fail(
                f"Tests could not run: {reason}",
                [Finding(message=f"Tests could not run: {reason}", severity=Severity.ERROR)],
            )
        failed = exports.get("failed", 0)
        errors = exports.get("errors", 0)

        if failed == 0 and errors == 0:
            return self._pass(f"All tests in {test_file.name} passed")

        # Build failure message from structured results
        failures = exports.get("failures", [])
        failure_msgs = [f.get("message", "") for f in failures]
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

    def _located_test_file(self, spec_path: Path) -> Path | str:
        """The test file the hydrator ran, from the real project root; else a search of our own."""
        if "qa_test_file" not in self.context:
            return _test_file(spec_path)
        located = self.context["qa_test_file"]
        return Path(located) if located else f"No test file 'test_{spec_path.stem}.py' found"


def _test_file(spec_path: Path) -> Path | str:
    """The file's `tests/**/test_<stem>.py` under the nearest `pyproject.toml`, or why there is none."""
    test_name = f"test_{spec_path.stem}.py"
    project_root = spec_path.parent
    while project_root != project_root.parent:
        if (project_root / "pyproject.toml").exists():
            break
        project_root = project_root.parent
    tests_dir = project_root / "tests"
    if not tests_dir.is_dir():
        return "No tests/ directory found"
    matches = list(tests_dir.rglob(test_name))
    return matches[0] if matches else f"No test file '{test_name}' found"
