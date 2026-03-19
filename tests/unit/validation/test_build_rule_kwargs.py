# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Unit tests for _build_rule_kwargs — bridges RuleOverride into constructor kwargs.

Tests the private helper that maps warn/fail thresholds and extra_params
from ValidationSettings into rule constructor kwargs via _THRESHOLD_PARAMS.
"""

from __future__ import annotations

from specweaver.config.settings import RuleOverride, ValidationSettings
from specweaver.validation.runner import _build_rule_kwargs

# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------


class TestBuildRuleKwargs:
    """Test _build_rule_kwargs() with various RuleOverride configurations."""

    def test_no_settings_returns_empty(self) -> None:
        """None settings → empty kwargs."""
        assert _build_rule_kwargs("S01", None) == {}

    def test_no_override_for_rule_returns_empty(self) -> None:
        """Settings exist but no override for this specific rule → empty."""
        settings = ValidationSettings(
            overrides={"S02": RuleOverride(rule_id="S02", warn_threshold=5)},
        )
        result = _build_rule_kwargs("S01", settings)
        assert result == {}

    def test_warn_threshold_mapped(self) -> None:
        """S01 warn_threshold → maps to 'warn_conjunctions' constructor arg."""
        settings = ValidationSettings(
            overrides={"S01": RuleOverride(rule_id="S01", warn_threshold=5)},
        )
        result = _build_rule_kwargs("S01", settings)
        assert result["warn_conjunctions"] == 5

    def test_fail_threshold_mapped(self) -> None:
        """S01 fail_threshold → maps to 'fail_conjunctions' constructor arg."""
        settings = ValidationSettings(
            overrides={"S01": RuleOverride(rule_id="S01", fail_threshold=10)},
        )
        result = _build_rule_kwargs("S01", settings)
        assert result["fail_conjunctions"] == 10

    def test_both_thresholds_mapped(self) -> None:
        """Both warn and fail thresholds for S05."""
        settings = ValidationSettings(
            overrides={"S05": RuleOverride(
                rule_id="S05", warn_threshold=20, fail_threshold=40,
            )},
        )
        result = _build_rule_kwargs("S05", settings)
        assert result["warn_threshold"] == 20
        assert result["fail_threshold"] == 40

    def test_none_threshold_skipped(self) -> None:
        """None threshold value does not produce a kwarg."""
        settings = ValidationSettings(
            overrides={"S05": RuleOverride(
                rule_id="S05", warn_threshold=None, fail_threshold=40,
            )},
        )
        result = _build_rule_kwargs("S05", settings)
        assert "warn_threshold" not in result
        assert result["fail_threshold"] == 40

    def test_extra_params_mapped(self) -> None:
        """S01 extra_params max_h2 → maps to 'max_h2' constructor arg."""
        settings = ValidationSettings(
            overrides={"S01": RuleOverride(
                rule_id="S01", extra_params={"max_h2": 12},
            )},
        )
        result = _build_rule_kwargs("S01", settings)
        assert result["max_h2"] == 12

    def test_extra_params_combined_with_thresholds(self) -> None:
        """S01 with all three override fields."""
        settings = ValidationSettings(
            overrides={"S01": RuleOverride(
                rule_id="S01",
                warn_threshold=3,
                fail_threshold=5,
                extra_params={"max_h2": 15},
            )},
        )
        result = _build_rule_kwargs("S01", settings)
        assert result["warn_conjunctions"] == 3
        assert result["fail_conjunctions"] == 5
        assert result["max_h2"] == 15

    def test_rule_not_in_threshold_params_returns_empty(self) -> None:
        """Rule not in _THRESHOLD_PARAMS (e.g. S02) → empty kwargs even with overrides."""
        settings = ValidationSettings(
            overrides={"S02": RuleOverride(
                rule_id="S02", warn_threshold=5, fail_threshold=10,
            )},
        )
        result = _build_rule_kwargs("S02", settings)
        # S02 has no entry in _THRESHOLD_PARAMS, so thresholds ignored
        assert result == {}

    def test_unknown_extra_param_ignored(self) -> None:
        """Extra param key not in _THRESHOLD_PARAMS mapping is silently ignored."""
        settings = ValidationSettings(
            overrides={"S01": RuleOverride(
                rule_id="S01", extra_params={"nonexistent_key": 42},
            )},
        )
        result = _build_rule_kwargs("S01", settings)
        assert "nonexistent_key" not in result
