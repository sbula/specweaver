# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for _build_rule_kwargs — bridges RuleOverride into constructor kwargs.

Tests the private helper that maps warn/fail thresholds and extra_params
from ValidationSettings into rule constructor kwargs via each rule's PARAM_MAP.

NOTE: _build_rule_kwargs is now in specweaver.validation.executor (moved from
runner.py as part of Feature 3.5b).  The signature changed to accept
(rule_cls, settings) instead of (rule_id, settings), so the rule class
itself is the source of truth for the PARAM_MAP (self-declaring pattern).
"""

from __future__ import annotations

from specweaver.config.settings import RuleOverride, ValidationSettings
from specweaver.validation.executor import _build_rule_kwargs
from specweaver.validation.rules.spec.s01_one_sentence import OneSentenceRule
from specweaver.validation.rules.spec.s02_single_setup import SingleSetupRule
from specweaver.validation.rules.spec.s05_day_test import DayTestRule
from specweaver.validation.rules.spec.s07_test_first import TestFirstRule
from specweaver.validation.rules.spec.s08_ambiguity import AmbiguityRule

# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------


class TestBuildRuleKwargs:
    """Test _build_rule_kwargs() with various RuleOverride configurations."""

    def test_no_settings_returns_empty(self) -> None:
        """None settings → empty kwargs."""
        assert _build_rule_kwargs(OneSentenceRule, None) == {}

    def test_no_override_for_rule_returns_empty(self) -> None:
        """Settings exist but no override for this specific rule → empty."""
        settings = ValidationSettings(
            overrides={"S02": RuleOverride(rule_id="S02", warn_threshold=5)},
        )
        result = _build_rule_kwargs(OneSentenceRule, settings)
        assert result == {}

    def test_warn_threshold_mapped(self) -> None:
        """S01 warn_threshold → maps to 'warn_conjunctions' constructor arg via PARAM_MAP."""
        settings = ValidationSettings(
            overrides={"S01": RuleOverride(rule_id="S01", warn_threshold=5)},
        )
        result = _build_rule_kwargs(OneSentenceRule, settings)
        assert result["warn_conjunctions"] == 5

    def test_fail_threshold_mapped(self) -> None:
        """S01 fail_threshold → maps to 'fail_conjunctions' constructor arg."""
        settings = ValidationSettings(
            overrides={"S01": RuleOverride(rule_id="S01", fail_threshold=10)},
        )
        result = _build_rule_kwargs(OneSentenceRule, settings)
        assert result["fail_conjunctions"] == 10

    def test_both_thresholds_mapped(self) -> None:
        """Both warn and fail thresholds for S05."""
        settings = ValidationSettings(
            overrides={
                "S05": RuleOverride(
                    rule_id="S05",
                    warn_threshold=20,
                    fail_threshold=40,
                )
            },
        )
        result = _build_rule_kwargs(DayTestRule, settings)
        assert result["warn_threshold"] == 20
        assert result["fail_threshold"] == 40

    def test_none_threshold_skipped(self) -> None:
        """None threshold value does not produce a kwarg."""
        settings = ValidationSettings(
            overrides={
                "S05": RuleOverride(
                    rule_id="S05",
                    warn_threshold=None,
                    fail_threshold=40,
                )
            },
        )
        result = _build_rule_kwargs(DayTestRule, settings)
        assert "warn_threshold" not in result
        assert result["fail_threshold"] == 40

    def test_extra_params_mapped(self) -> None:
        """S01 extra_params max_h2 → maps to 'max_h2' constructor arg via PARAM_MAP."""
        settings = ValidationSettings(
            overrides={
                "S01": RuleOverride(
                    rule_id="S01",
                    extra_params={"max_h2": 12},
                )
            },
        )
        result = _build_rule_kwargs(OneSentenceRule, settings)
        assert result["max_h2"] == 12

    def test_extra_params_combined_with_thresholds(self) -> None:
        """S01 with all three override fields."""
        settings = ValidationSettings(
            overrides={
                "S01": RuleOverride(
                    rule_id="S01",
                    warn_threshold=3,
                    fail_threshold=5,
                    extra_params={"max_h2": 15},
                )
            },
        )
        result = _build_rule_kwargs(OneSentenceRule, settings)
        assert result["warn_conjunctions"] == 3
        assert result["fail_conjunctions"] == 5
        assert result["max_h2"] == 15

    def test_rule_with_empty_param_map_returns_empty(self) -> None:
        """S02 has PARAM_MAP = {} — no threshold mapping, returns empty."""
        settings = ValidationSettings(
            overrides={
                "S02": RuleOverride(
                    rule_id="S02",
                    warn_threshold=5,
                    fail_threshold=10,
                )
            },
        )
        result = _build_rule_kwargs(SingleSetupRule, settings)
        # S02 has no PARAM_MAP entries, so thresholds are gracefully ignored
        assert result == {}

    def test_unknown_extra_param_ignored(self) -> None:
        """Extra param key not in PARAM_MAP 'extra:<key>' entries is silently ignored."""
        settings = ValidationSettings(
            overrides={
                "S01": RuleOverride(
                    rule_id="S01",
                    extra_params={"nonexistent_key": 42},
                )
            },
        )
        result = _build_rule_kwargs(OneSentenceRule, settings)
        assert "nonexistent_key" not in result

    def test_s07_param_map_translation(self) -> None:
        """S07 warn_threshold → warn_score, fail_threshold → fail_score."""
        settings = ValidationSettings(
            overrides={
                "S07": RuleOverride(
                    rule_id="S07",
                    warn_threshold=8.0,
                    fail_threshold=3.0,
                )
            },
        )
        result = _build_rule_kwargs(TestFirstRule, settings)
        assert result["warn_score"] == 8
        assert result["fail_score"] == 3

    def test_s08_symmetric_mapping(self) -> None:
        """S08 warn_threshold → warn_threshold (symmetric PARAM_MAP)."""
        settings = ValidationSettings(
            overrides={
                "S08": RuleOverride(
                    rule_id="S08",
                    warn_threshold=2.0,
                    fail_threshold=5.0,
                )
            },
        )
        result = _build_rule_kwargs(AmbiguityRule, settings)
        assert result["warn_threshold"] == 2
        assert result["fail_threshold"] == 5
