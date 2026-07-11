# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for C03 TestsPassRule — context-injected version.

Replaces old C03 tests that mocked QARunnerAtom directly.
Now rules read pre-hydrated results from self.context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.assurance.validation.models import Status
from specweaver.assurance.validation.rules.code.c03_tests_pass import TestsPassRule

if TYPE_CHECKING:
    from pathlib import Path


def _make_rule(context: dict | None = None) -> TestsPassRule:
    """Create a TestsPassRule with optional context injection."""
    rule = TestsPassRule()
    if context is not None:
        rule.context = context
    return rule


def _setup_test_file(tmp_path: Path, code_stem: str = "module") -> Path:
    """Create a minimal project structure with a matching test file.

    Returns the code file path (used as spec_path in check()).
    """
    # Create pyproject.toml at root
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n", encoding="utf-8")
    # Create code file
    code_file = tmp_path / "src" / f"{code_stem}.py"
    code_file.parent.mkdir(parents=True, exist_ok=True)
    code_file.write_text("pass\n", encoding="utf-8")
    # Create test file
    test_file = tmp_path / "tests" / f"test_{code_stem}.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("def test_ok(): pass\n", encoding="utf-8")
    return code_file


class TestC03Context:
    """C03 TestsPassRule with context injection."""

    def test_rule_id(self) -> None:
        rule = _make_rule()
        assert rule.rule_id == "C03"
        assert rule.name == "Tests Pass"

    def test_skip_when_no_path(self) -> None:
        rule = _make_rule()
        result = rule.check("", spec_path=None)
        assert result.status == Status.SKIP

    def test_skip_when_no_tests_dir(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
        code_file = tmp_path / "src" / "module.py"
        code_file.parent.mkdir(parents=True, exist_ok=True)
        code_file.write_text("pass\n", encoding="utf-8")
        # No tests/ directory
        rule = _make_rule()
        result = rule.check("", spec_path=code_file)
        assert result.status == Status.SKIP

    def test_skip_when_no_test_file(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
        code_file = tmp_path / "src" / "module.py"
        code_file.parent.mkdir(parents=True, exist_ok=True)
        code_file.write_text("pass\n", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        # tests/ exists but no matching test file
        rule = _make_rule()
        result = rule.check("", spec_path=code_file)
        assert result.status == Status.SKIP

    def test_pass_when_context_reports_success(self, tmp_path: Path) -> None:
        code_file = _setup_test_file(tmp_path)
        rule = _make_rule(
            context={
                "qa_tests_result": {
                    "status": "SUCCESS",
                    "message": "All passed",
                    "exports": {"failed": 0, "errors": 0},
                }
            }
        )
        result = rule.check("", spec_path=code_file)
        assert result.status == Status.PASS

    def test_fail_when_context_reports_failure(self, tmp_path: Path) -> None:
        code_file = _setup_test_file(tmp_path)
        rule = _make_rule(
            context={
                "qa_tests_result": {
                    "status": "FAILED",
                    "message": "Tests failed",
                    "exports": {
                        "failed": 1,
                        "errors": 0,
                        "failures": [{"message": "assert False"}],
                    },
                }
            }
        )
        result = rule.check("", spec_path=code_file)
        assert result.status == Status.FAIL

    def test_fail_when_timeout(self, tmp_path: Path) -> None:
        code_file = _setup_test_file(tmp_path)
        rule = _make_rule(
            context={
                "qa_tests_result": {
                    "status": "FAILED",
                    "message": "timed out after 120s",
                    "exports": {},
                }
            }
        )
        result = rule.check("", spec_path=code_file)
        assert result.status == Status.FAIL
        assert "timed out" in result.message.lower()

    def test_fail_when_context_missing_but_tests_exist(self, tmp_path: Path) -> None:
        code_file = _setup_test_file(tmp_path)
        rule = _make_rule(context={})  # No qa_tests_result key
        result = rule.check("", spec_path=code_file)
        assert result.status == Status.FAIL
        assert "not hydrated" in result.message.lower() or "not available" in result.message.lower()

    def test_fail_output_truncated(self, tmp_path: Path) -> None:
        code_file = _setup_test_file(tmp_path)
        long_msg = "x" * 1000
        rule = _make_rule(
            context={
                "qa_tests_result": {
                    "status": "FAILED",
                    "message": "Tests failed",
                    "exports": {
                        "failed": 1,
                        "errors": 0,
                        "failures": [{"message": long_msg}],
                    },
                }
            }
        )
        result = rule.check("", spec_path=code_file)
        assert result.status == Status.FAIL
        # Truncated to max 500 chars
        all_text = " ".join(f.message for f in result.findings)
        assert len(all_text) <= 600  # Allow some buffer for prefix text

    def test_fail_no_output(self, tmp_path: Path) -> None:
        code_file = _setup_test_file(tmp_path)
        rule = _make_rule(
            context={
                "qa_tests_result": {
                    "status": "FAILED",
                    "message": "Tests failed",
                    "exports": {
                        "failed": 1,
                        "errors": 0,
                        "failures": [],
                    },
                }
            }
        )
        result = rule.check("", spec_path=code_file)
        assert result.status == Status.FAIL
