# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for C04 CoverageRule — context-injected version.

Replaces old C04 tests that mocked QARunnerAtom directly.
Now rules read pre-hydrated results from self.context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.assurance.validation.models import Status
from specweaver.assurance.validation.rules.code.c04_coverage import CoverageRule

if TYPE_CHECKING:
    from pathlib import Path


def _make_rule(threshold: int = 70, context: dict | None = None) -> CoverageRule:
    """Create a CoverageRule with optional context injection."""
    rule = CoverageRule(threshold=threshold)
    if context is not None:
        rule.context = context
    return rule


class TestC04Context:
    """C04 CoverageRule with context injection."""

    def test_rule_id(self) -> None:
        rule = _make_rule()
        assert rule.rule_id == "C04"
        assert rule.name == "Coverage"

    def test_skip_when_no_path(self) -> None:
        rule = _make_rule()
        result = rule.check("", spec_path=None)
        assert result.status == Status.SKIP

    def test_pass_when_above_threshold(self, tmp_path: Path) -> None:
        rule = _make_rule(
            threshold=70,
            context={
                "qa_coverage_result": {
                    "status": "SUCCESS",
                    "message": "OK",
                    "exports": {"coverage_pct": 95.0},
                }
            },
        )
        result = rule.check("", spec_path=tmp_path / "module.py")
        assert result.status == Status.PASS

    def test_fail_when_below_threshold(self, tmp_path: Path) -> None:
        rule = _make_rule(
            threshold=70,
            context={
                "qa_coverage_result": {
                    "status": "SUCCESS",
                    "message": "OK",
                    "exports": {"coverage_pct": 40.0},
                }
            },
        )
        result = rule.check("", spec_path=tmp_path / "module.py")
        assert result.status == Status.FAIL

    def test_pass_at_exact_threshold(self, tmp_path: Path) -> None:
        rule = _make_rule(
            threshold=70,
            context={
                "qa_coverage_result": {
                    "status": "SUCCESS",
                    "message": "OK",
                    "exports": {"coverage_pct": 70.0},
                }
            },
        )
        result = rule.check("", spec_path=tmp_path / "module.py")
        assert result.status == Status.PASS

    def test_fail_one_below_threshold(self, tmp_path: Path) -> None:
        rule = _make_rule(
            threshold=70,
            context={
                "qa_coverage_result": {
                    "status": "SUCCESS",
                    "message": "OK",
                    "exports": {"coverage_pct": 69.0},
                }
            },
        )
        result = rule.check("", spec_path=tmp_path / "module.py")
        assert result.status == Status.FAIL

    def test_warn_when_coverage_none(self, tmp_path: Path) -> None:
        rule = _make_rule(
            context={
                "qa_coverage_result": {
                    "status": "SUCCESS",
                    "message": "OK",
                    "exports": {"coverage_pct": None},
                }
            },
        )
        result = rule.check("", spec_path=tmp_path / "module.py")
        assert result.status == Status.WARN

    def test_fail_when_timeout(self, tmp_path: Path) -> None:
        rule = _make_rule(
            context={
                "qa_coverage_result": {
                    "status": "FAILED",
                    "message": "timed out after 120s",
                    "exports": {},
                }
            },
        )
        result = rule.check("", spec_path=tmp_path / "module.py")
        assert result.status == Status.FAIL
        assert "timed out" in result.message.lower()

    def test_fail_when_context_missing(self, tmp_path: Path) -> None:
        rule = _make_rule(context={})  # No qa_coverage_result key
        result = rule.check("", spec_path=tmp_path / "module.py")
        assert result.status == Status.FAIL
        assert "not hydrated" in result.message.lower() or "not available" in result.message.lower()

    def test_custom_threshold(self) -> None:
        rule = CoverageRule(threshold=90)
        assert rule._threshold == 90

    def test_default_threshold(self) -> None:
        rule = CoverageRule()
        assert rule._threshold == 70
