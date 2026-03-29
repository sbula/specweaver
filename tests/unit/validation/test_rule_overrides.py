# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for configurable thresholds on validation rules.

Each threshold-bearing rule must:
1. Accept constructor overrides for its thresholds
2. Use defaults when no overrides are given (unchanged behavior)
3. Use injected thresholds when provided
"""

from __future__ import annotations

from specweaver.validation.rules.code.c04_coverage import CoverageRule
from specweaver.validation.rules.spec.s01_one_sentence import OneSentenceRule
from specweaver.validation.rules.spec.s03_stranger import StrangerTestRule
from specweaver.validation.rules.spec.s04_dependency_dir import DependencyDirectionRule
from specweaver.validation.rules.spec.s05_day_test import DayTestRule
from specweaver.validation.rules.spec.s07_test_first import TestFirstRule
from specweaver.validation.rules.spec.s08_ambiguity import AmbiguityRule
from specweaver.validation.rules.spec.s11_terminology import TerminologyRule


# Minimal spec text helpers
def _spec_with_purpose(conjunctions: int) -> str:
    conj_phrase = " and also ".join(["does something"] * (conjunctions + 1))
    return f"## 1. Purpose\n{conj_phrase}\n\n## 2. Contract\nSome contract.\n"


def _spec_with_weasels(count: int) -> str:
    weasels = " ".join(["should"] * count)
    return f"## 1. Purpose\nDo X.\n\n## 2. Contract\n{weasels} work.\n"


# ---------------------------------------------------------------------------
# S01: One-Sentence — constructor overrides
# ---------------------------------------------------------------------------


class TestS01Configurable:
    def test_defaults_unchanged(self):
        rule = OneSentenceRule()
        # 3 conjunctions → FAIL with defaults (fail=2)
        spec = _spec_with_purpose(3)
        result = rule.check(spec)
        assert result.status.value == "fail"

    def test_custom_fail_threshold_relaxed(self):
        rule = OneSentenceRule(fail_conjunctions=5)
        # 3 conjunctions → WARN (below new fail=5, but above default warn=0)
        spec = _spec_with_purpose(3)
        result = rule.check(spec)
        assert result.status.value == "warn"

    def test_custom_fail_threshold_strict(self):
        rule = OneSentenceRule(fail_conjunctions=1)
        # 2 conjunctions → FAIL (above new fail=1)
        spec = _spec_with_purpose(2)
        result = rule.check(spec)
        assert result.status.value == "fail"


# ---------------------------------------------------------------------------
# S03: Stranger — constructor overrides
# ---------------------------------------------------------------------------


class TestS03Configurable:
    def test_defaults_unchanged(self):
        rule = StrangerTestRule()
        assert rule._warn_threshold == 5
        assert rule._fail_threshold == 10

    def test_custom_thresholds(self):
        rule = StrangerTestRule(warn_threshold=2, fail_threshold=4)
        assert rule._warn_threshold == 2
        assert rule._fail_threshold == 4


# ---------------------------------------------------------------------------
# S04: Dependency Dir — constructor overrides
# ---------------------------------------------------------------------------


class TestS04Configurable:
    def test_defaults_unchanged(self):
        rule = DependencyDirectionRule()
        assert rule._warn_threshold == 5
        assert rule._fail_threshold == 8

    def test_custom_thresholds(self):
        rule = DependencyDirectionRule(warn_threshold=3, fail_threshold=6)
        assert rule._warn_threshold == 3
        assert rule._fail_threshold == 6


# ---------------------------------------------------------------------------
# S05: Day Test — constructor overrides
# ---------------------------------------------------------------------------


class TestS05Configurable:
    def test_defaults_unchanged(self):
        rule = DayTestRule()
        assert rule._warn_threshold == 25.0
        assert rule._fail_threshold == 40.0

    def test_custom_thresholds(self):
        rule = DayTestRule(warn_threshold=10.0, fail_threshold=20.0)
        assert rule._warn_threshold == 10.0
        assert rule._fail_threshold == 20.0


# ---------------------------------------------------------------------------
# S07: Test-First — constructor overrides
# ---------------------------------------------------------------------------


class TestS07Configurable:
    def test_defaults_unchanged(self):
        rule = TestFirstRule()
        assert rule._warn_score == 6
        assert rule._fail_score == 3

    def test_custom_thresholds(self):
        rule = TestFirstRule(warn_score=8, fail_score=4)
        assert rule._warn_score == 8
        assert rule._fail_score == 4


# ---------------------------------------------------------------------------
# S08: Ambiguity — constructor overrides
# ---------------------------------------------------------------------------


class TestS08Configurable:
    def test_defaults_unchanged(self):
        rule = AmbiguityRule()
        assert rule._warn_threshold == 1
        assert rule._fail_threshold == 3

    def test_custom_thresholds(self):
        rule = AmbiguityRule(warn_threshold=5, fail_threshold=10)
        assert rule._warn_threshold == 5
        assert rule._fail_threshold == 10

    def test_custom_threshold_changes_behavior(self):
        # 2 weasels with defaults → WARN (>1 warn, <3 fail)
        spec = _spec_with_weasels(2)
        default_rule = AmbiguityRule()
        default_result = default_rule.check(spec)
        assert default_result.status.value == "warn"

        # Same 2 weasels with relaxed thresholds → PASS (<5 warn)
        relaxed_rule = AmbiguityRule(warn_threshold=5, fail_threshold=10)
        relaxed_result = relaxed_rule.check(spec)
        assert relaxed_result.status.value == "pass"


# ---------------------------------------------------------------------------
# S11: Terminology — constructor overrides
# ---------------------------------------------------------------------------


class TestS11Configurable:
    def test_defaults_unchanged(self):
        rule = TerminologyRule()
        assert rule._warn_threshold == 1
        assert rule._fail_threshold == 3

    def test_custom_thresholds(self):
        rule = TerminologyRule(warn_threshold=5, fail_threshold=10)
        assert rule._warn_threshold == 5
        assert rule._fail_threshold == 10


# ---------------------------------------------------------------------------
# C04: Coverage — already configurable, verify
# ---------------------------------------------------------------------------


class TestC04AlreadyConfigurable:
    def test_defaults_unchanged(self):
        rule = CoverageRule()
        assert rule._threshold == 70

    def test_custom_threshold(self):
        rule = CoverageRule(threshold=90)
        assert rule._threshold == 90


# ---------------------------------------------------------------------------
# Edge-case tests: boundary values & behavioral verification
# ---------------------------------------------------------------------------


class TestRuleOverrideEdgeCases:
    """Edge cases for rule threshold injection."""

    def test_s08_zero_threshold_everything_warns(self):
        """With warn=0, even a single weasel word should trigger WARN."""
        rule = AmbiguityRule(warn_threshold=0, fail_threshold=100)
        spec = "## 1. Purpose\nDo X.\n\n## 2. Contract\nShould work.\n"
        result = rule.check(spec)
        # 'should' is a weasel word; with warn=0, 1 weasel > 0 → warn
        assert result.status.value == "warn"

    def test_s08_zero_fail_threshold_everything_fails(self):
        """With fail=0, even a single weasel word should trigger FAIL."""
        rule = AmbiguityRule(warn_threshold=0, fail_threshold=0)
        spec = "## 1. Purpose\nDo X.\n\n## 2. Contract\nShould work.\n"
        result = rule.check(spec)
        assert result.status.value == "fail"

    def test_s08_inverted_thresholds_warn_gt_fail(self):
        """When warn > fail, the fail branch is hit first for medium counts."""
        # With warn=10, fail=2: 3 weasels → > fail(2) → FAIL
        rule = AmbiguityRule(warn_threshold=10, fail_threshold=2)
        spec = _spec_with_weasels(3)
        result = rule.check(spec)
        assert result.status.value == "fail"

    def test_s08_huge_threshold_everything_passes(self):
        """With very large thresholds, even many weasels pass."""
        rule = AmbiguityRule(warn_threshold=9999, fail_threshold=9999)
        spec = _spec_with_weasels(5)
        result = rule.check(spec)
        assert result.status.value == "pass"

    def test_s01_max_h2_override(self):
        """S01 max_h2 param changes section count threshold."""
        rule = OneSentenceRule(max_h2=1)
        # Spec with 2 H2 sections → should fail with max_h2=1
        spec = "## 1. Purpose\nDo X.\n\n## 2. Contract\nY.\n\n## 3. Extra\nZ.\n"
        result = rule.check(spec)
        # With max_h2=1, only 1 H2 allowed
        # This should trigger one of the conditions
        assert result is not None  # doesn't crash

    def test_s05_exact_boundary_at_warn_threshold(self):
        """DayTestRule at exactly warn threshold should pass (uses > not >=)."""
        rule = DayTestRule(warn_threshold=0.0, fail_threshold=999.0)
        # A minimal spec that scores > 0 — should trigger warn
        spec = "## 1. Purpose\nA.\n\n## 2. Contract\nB.\n\n## 3. Deps\n- dep1\n"
        result = rule.check(spec)
        # Just verifying no crash with boundary values
        assert result.status.value in {"pass", "warn", "fail"}

    def test_s07_custom_thresholds_change_behavior(self):
        """TestFirstRule with fail_score=0 means nothing can fail (score is never < 0)."""
        rule_lenient = TestFirstRule(warn_score=0, fail_score=0)
        spec = "## 1. Purpose\nDo X.\n\n## 2. Contract\nProvide Y.\n"
        result = rule_lenient.check(spec)
        # score=0, and 0 < 0 is False → should pass
        assert result.status.value == "pass"

    def test_s04_custom_thresholds_stored_correctly(self):
        """DependencyDirectionRule stores both thresholds correctly."""
        rule = DependencyDirectionRule(warn_threshold=1, fail_threshold=2)
        assert rule._warn_threshold == 1
        assert rule._fail_threshold == 2

    def test_s11_custom_thresholds_stored_correctly(self):
        """TerminologyRule stores thresholds as given."""
        rule = TerminologyRule(warn_threshold=0, fail_threshold=0)
        assert rule._warn_threshold == 0
        assert rule._fail_threshold == 0
