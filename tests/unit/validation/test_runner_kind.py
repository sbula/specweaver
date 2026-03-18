# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for runner kind-threading via SpecKind + get_presets."""

from __future__ import annotations

from specweaver.validation.runner import get_spec_rules
from specweaver.validation.spec_kind import SpecKind


class TestRunnerKindThreading:
    """get_spec_rules(kind=...) applies kind-specific presets to rules."""

    def test_kind_none_is_default_behaviour(self) -> None:
        """No kind → same 11 rules with default thresholds."""
        rules = get_spec_rules()
        assert len(rules) == 11

    def test_kind_component_same_as_default(self) -> None:
        """COMPONENT → no preset overrides, same as kind=None."""
        rules = get_spec_rules(kind=SpecKind.COMPONENT)
        assert len(rules) == 11
        s08 = next(r for r in rules if r.rule_id == "S08")
        assert s08._warn_threshold == 1  # component default

    def test_kind_feature_applies_s01_header(self) -> None:
        """FEATURE → S01 uses Intent header pattern."""
        rules = get_spec_rules(kind=SpecKind.FEATURE)
        s01 = next(r for r in rules if r.rule_id == "S01")
        assert s01._kind == SpecKind.FEATURE
        assert s01._header_pattern is not None

    def test_kind_feature_applies_s01_thresholds(self) -> None:
        """FEATURE → S01 gets warn=2, fail=4."""
        rules = get_spec_rules(kind=SpecKind.FEATURE)
        s01 = next(r for r in rules if r.rule_id == "S01")
        assert s01._warn_conjunctions == 2
        assert s01._fail_conjunctions == 4

    def test_kind_feature_applies_s03_mode(self) -> None:
        """FEATURE → S03 mode='abstraction_leak'."""
        rules = get_spec_rules(kind=SpecKind.FEATURE)
        s03 = next(r for r in rules if r.rule_id == "S03")
        assert s03._mode == "abstraction_leak"

    def test_kind_feature_applies_s04_skip(self) -> None:
        """FEATURE → S04 skip=True."""
        rules = get_spec_rules(kind=SpecKind.FEATURE)
        s04 = next(r for r in rules if r.rule_id == "S04")
        assert s04._skip is True

    def test_kind_feature_applies_s05_thresholds(self) -> None:
        """FEATURE → S05 gets warn=60, fail=100."""
        rules = get_spec_rules(kind=SpecKind.FEATURE)
        s05 = next(r for r in rules if r.rule_id == "S05")
        assert s05._warn_threshold == 60
        assert s05._fail_threshold == 100

    def test_kind_feature_applies_s08_thresholds(self) -> None:
        """FEATURE → S08 gets warn=2, fail=5."""
        rules = get_spec_rules(kind=SpecKind.FEATURE)
        s08 = next(r for r in rules if r.rule_id == "S08")
        assert s08._warn_threshold == 2
        assert s08._fail_threshold == 5

    def test_kind_feature_unchanged_rules_unaffected(self) -> None:
        """Rules without presets (S02, S06, S07, S09-S11) are unchanged."""
        rules_default = get_spec_rules()
        rules_feature = get_spec_rules(kind=SpecKind.FEATURE)
        unchanged_ids = {"S02", "S06", "S07", "S09", "S10", "S11"}
        for rid in unchanged_ids:
            r_def = next(r for r in rules_default if r.rule_id == rid)
            r_feat = next(r for r in rules_feature if r.rule_id == rid)
            assert type(r_def) is type(r_feat)

    def test_settings_override_presets(self) -> None:
        """Settings overrides take priority over kind presets."""
        from specweaver.config.settings import RuleOverride, ValidationSettings

        settings = ValidationSettings(overrides={
            "S08": RuleOverride(rule_id="S08", warn_threshold=99.0),
        })
        rules = get_spec_rules(kind=SpecKind.FEATURE, settings=settings)
        s08 = next(r for r in rules if r.rule_id == "S08")
        # Settings override (99) should win over kind preset (2)
        assert s08._warn_threshold == 99


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestRunnerKindEdgeCases:
    """Edge cases for runner kind-threading."""

    def test_settings_override_s01_beats_preset(self) -> None:
        """Settings override for S01 wins over FEATURE preset."""
        from specweaver.config.settings import RuleOverride, ValidationSettings

        # _THRESHOLD_PARAMS maps warn_threshold → warn_conjunctions for S01
        settings = ValidationSettings(overrides={
            "S01": RuleOverride(rule_id="S01", warn_threshold=10.0),
        })
        rules = get_spec_rules(kind=SpecKind.FEATURE, settings=settings)
        s01 = next(r for r in rules if r.rule_id == "S01")
        assert s01._warn_conjunctions == 10  # settings override, not kind preset 2

    def test_settings_override_s05_beats_preset(self) -> None:
        """Settings override for S05 wins over FEATURE preset."""
        from specweaver.config.settings import RuleOverride, ValidationSettings

        settings = ValidationSettings(overrides={
            "S05": RuleOverride(rule_id="S05", warn_threshold=99.0),
        })
        rules = get_spec_rules(kind=SpecKind.FEATURE, settings=settings)
        s05 = next(r for r in rules if r.rule_id == "S05")
        assert s05._warn_threshold == 99  # settings override, not kind preset 60

    def test_kind_feature_with_include_llm_true(self) -> None:
        """Kind presets still apply when include_llm=True."""
        rules = get_spec_rules(kind=SpecKind.FEATURE, include_llm=True)
        s01 = next(r for r in rules if r.rule_id == "S01")
        assert s01._kind == SpecKind.FEATURE

    def test_kind_feature_same_rule_count(self) -> None:
        """Feature kind doesn't add or remove rules — same 11."""
        rules_default = get_spec_rules()
        rules_feature = get_spec_rules(kind=SpecKind.FEATURE)
        assert len(rules_default) == len(rules_feature)
