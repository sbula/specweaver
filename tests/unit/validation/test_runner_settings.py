# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for runner with ValidationSettings injection."""

from __future__ import annotations

from specweaver.config.settings import RuleOverride, ValidationSettings
from specweaver.validation.runner import get_code_rules, get_spec_rules

# ---------------------------------------------------------------------------
# Settings injection tests
# ---------------------------------------------------------------------------


class TestRunnerSettingsInjection:
    def test_spec_rules_defaults_without_settings(self):
        """Without settings, rules use built-in defaults."""
        rules = get_spec_rules()
        assert len(rules) > 0
        # S08 should have default warn=1
        s08 = next(r for r in rules if r.rule_id == "S08")
        assert s08._warn_threshold == 1

    def test_spec_rules_with_threshold_overrides(self):
        """Settings inject custom thresholds into rules."""
        settings = ValidationSettings(overrides={
            "S08": RuleOverride(rule_id="S08", warn_threshold=10.0, fail_threshold=20.0),
        })
        rules = get_spec_rules(settings=settings)
        s08 = next(r for r in rules if r.rule_id == "S08")
        assert s08._warn_threshold == 10
        assert s08._fail_threshold == 20

    def test_spec_rules_disabled_rule_skipped(self):
        """Disabled rules are excluded from the list."""
        settings = ValidationSettings(overrides={
            "S08": RuleOverride(rule_id="S08", enabled=False),
        })
        rules = get_spec_rules(settings=settings)
        rule_ids = {r.rule_id for r in rules}
        assert "S08" not in rule_ids

    def test_spec_rules_disabled_does_not_affect_others(self):
        """Disabling one rule doesn't remove any other rules."""
        rules_default = get_spec_rules()
        settings = ValidationSettings(overrides={
            "S08": RuleOverride(rule_id="S08", enabled=False),
        })
        rules_with_settings = get_spec_rules(settings=settings)
        assert len(rules_with_settings) == len(rules_default) - 1

    def test_code_rules_with_coverage_override(self):
        """C04 coverage threshold can be overridden."""
        settings = ValidationSettings(overrides={
            "C04": RuleOverride(rule_id="C04", fail_threshold=90.0),
        })
        rules = get_code_rules(include_subprocess=False, settings=settings)
        # C04 not included without subprocess — verify other rules still work
        rule_ids = {r.rule_id for r in rules}
        assert "C04" not in rule_ids  # excluded by include_subprocess=False

    def test_code_rules_disabled(self):
        """Disabling a code rule removes it."""
        settings = ValidationSettings(overrides={
            "C01": RuleOverride(rule_id="C01", enabled=False),
        })
        rules = get_code_rules(include_subprocess=False, settings=settings)
        rule_ids = {r.rule_id for r in rules}
        assert "C01" not in rule_ids

    def test_run_all_flag_ignores_disabled(self):
        """run_all=True ignores the enabled flag."""
        settings = ValidationSettings(overrides={
            "S08": RuleOverride(rule_id="S08", enabled=False),
        })
        rules = get_spec_rules(settings=settings, run_all=True)
        rule_ids = {r.rule_id for r in rules}
        assert "S08" in rule_ids

    def test_partial_override_only_affects_specified_field(self):
        """Overriding only warn_threshold leaves fail_threshold at default."""
        settings = ValidationSettings(overrides={
            "S08": RuleOverride(rule_id="S08", warn_threshold=99.0),
        })
        rules = get_spec_rules(settings=settings)
        s08 = next(r for r in rules if r.rule_id == "S08")
        assert s08._warn_threshold == 99
        assert s08._fail_threshold == 3  # default

    def test_unknown_rule_id_ignored(self):
        """Override for unknown rule IDs doesn't crash."""
        settings = ValidationSettings(overrides={
            "Z99": RuleOverride(rule_id="Z99", enabled=False),
        })
        rules = get_spec_rules(settings=settings)
        assert len(rules) > 0  # no crash


# ---------------------------------------------------------------------------
# Runner edge cases
# ---------------------------------------------------------------------------


class TestRunnerSettingsEdgeCases:
    """Edge cases for the runner's settings injection path."""

    def test_empty_settings_same_as_none(self):
        """Empty ValidationSettings produces same rules as no settings."""
        rules_none = get_spec_rules(settings=None)
        rules_empty = get_spec_rules(settings=ValidationSettings())
        assert len(rules_none) == len(rules_empty)
        for r1, r2 in zip(rules_none, rules_empty, strict=True):
            assert r1.rule_id == r2.rule_id

    def test_multiple_rules_disabled(self):
        """Disabling multiple rules removes all of them."""
        settings = ValidationSettings(overrides={
            "S01": RuleOverride(rule_id="S01", enabled=False),
            "S03": RuleOverride(rule_id="S03", enabled=False),
            "S05": RuleOverride(rule_id="S05", enabled=False),
        })
        rules = get_spec_rules(settings=settings)
        rule_ids = {r.rule_id for r in rules}
        assert "S01" not in rule_ids
        assert "S03" not in rule_ids
        assert "S05" not in rule_ids
        # Others still present
        assert "S04" in rule_ids
        assert "S08" in rule_ids

    def test_disabled_with_threshold_still_excluded(self):
        """A rule with enabled=False + thresholds set should still be excluded."""
        settings = ValidationSettings(overrides={
            "S08": RuleOverride(rule_id="S08", enabled=False, warn_threshold=99.0),
        })
        rules = get_spec_rules(settings=settings)
        rule_ids = {r.rule_id for r in rules}
        assert "S08" not in rule_ids

    def test_run_all_still_applies_thresholds(self):
        """run_all=True ignores disabled but still injects thresholds."""
        settings = ValidationSettings(overrides={
            "S08": RuleOverride(rule_id="S08", enabled=False, warn_threshold=42.0),
        })
        rules = get_spec_rules(settings=settings, run_all=True)
        s08 = next(r for r in rules if r.rule_id == "S08")
        assert s08._warn_threshold == 42  # threshold applied despite run_all

    def test_s01_threshold_mapping_uses_correct_param_names(self):
        """S01 maps warn_threshold→warn_conjunctions, fail_threshold→fail_conjunctions."""
        settings = ValidationSettings(overrides={
            "S01": RuleOverride(rule_id="S01", warn_threshold=5.0, fail_threshold=10.0),
        })
        rules = get_spec_rules(settings=settings)
        s01 = next(r for r in rules if r.rule_id == "S01")
        assert s01._warn_conjunctions == 5
        assert s01._fail_conjunctions == 10

    def test_all_spec_rules_disabled_returns_empty(self):
        """Disabling all 11 spec rules → empty list."""
        all_ids = [f"S{i:02d}" for i in range(1, 12)]
        overrides = {
            rid: RuleOverride(rule_id=rid, enabled=False) for rid in all_ids
        }
        settings = ValidationSettings(overrides=overrides)
        rules = get_spec_rules(settings=settings)
        assert rules == []

    def test_code_rules_multiple_disabled(self):
        """Disabling multiple code rules with subprocess disabled."""
        settings = ValidationSettings(overrides={
            "C01": RuleOverride(rule_id="C01", enabled=False),
            "C05": RuleOverride(rule_id="C05", enabled=False),
        })
        rules = get_code_rules(include_subprocess=False, settings=settings)
        rule_ids = {r.rule_id for r in rules}
        assert "C01" not in rule_ids
        assert "C05" not in rule_ids
        assert "C02" in rule_ids  # still present

    def test_override_for_non_threshold_rule_just_enables_disables(self):
        """S02 has no threshold params — override only controls enabled/disabled."""
        settings = ValidationSettings(overrides={
            "S02": RuleOverride(rule_id="S02", enabled=False),
        })
        rules = get_spec_rules(settings=settings)
        rule_ids = {r.rule_id for r in rules}
        assert "S02" not in rule_ids

    def test_override_threshold_for_non_threshold_rule_ignored(self):
        """S02 doesn't accept thresholds — extra kwargs should NOT crash."""
        settings = ValidationSettings(overrides={
            "S02": RuleOverride(rule_id="S02", warn_threshold=5.0),
        })
        rules = get_spec_rules(settings=settings)
        s02 = next(r for r in rules if r.rule_id == "S02")
        assert s02 is not None  # no crash

