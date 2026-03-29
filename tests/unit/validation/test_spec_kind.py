# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for SpecKind enum and get_presets() threshold lookup."""

from __future__ import annotations

import pytest

from specweaver.validation.spec_kind import SpecKind, get_presets

# ---------------------------------------------------------------------------
# SpecKind enum
# ---------------------------------------------------------------------------


class TestSpecKindEnum:
    """SpecKind has exactly 2 values: feature and component."""

    def test_feature_value(self) -> None:
        assert SpecKind.FEATURE == "feature"
        assert SpecKind.FEATURE.value == "feature"

    def test_component_value(self) -> None:
        assert SpecKind.COMPONENT == "component"
        assert SpecKind.COMPONENT.value == "component"

    def test_exactly_two_members(self) -> None:
        assert len(SpecKind) == 2

    def test_str_enum_usable_as_string(self) -> None:
        """StrEnum values can be compared directly to strings."""
        assert SpecKind.FEATURE == "feature"
        assert SpecKind.COMPONENT == "component"

    def test_from_string(self) -> None:
        assert SpecKind("feature") is SpecKind.FEATURE
        assert SpecKind("component") is SpecKind.COMPONENT

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError, match="module"):
            SpecKind("module")


# ---------------------------------------------------------------------------
# get_presets — threshold lookup by (rule_id, kind)
# ---------------------------------------------------------------------------


class TestGetPresets:
    """get_presets returns kind-specific thresholds for parameterized rules."""

    # --- S01 thresholds ---
    def test_s01_feature_thresholds(self) -> None:
        presets = get_presets("S01", SpecKind.FEATURE)
        assert presets["warn_conjunctions"] == 2
        assert presets["fail_conjunctions"] == 4

    def test_s01_component_returns_empty(self) -> None:
        """Component uses code defaults, so no overrides needed."""
        presets = get_presets("S01", SpecKind.COMPONENT)
        assert presets == {}

    # --- S01 header_pattern ---
    def test_s01_feature_header_pattern(self) -> None:
        """Feature specs use ## Intent as purpose header."""
        presets = get_presets("S01", SpecKind.FEATURE)
        assert "header_pattern" in presets

    def test_s01_component_no_header_override(self) -> None:
        """Component specs use default ## 1. Purpose — no override needed."""
        presets = get_presets("S01", SpecKind.COMPONENT)
        assert "header_pattern" not in presets

    # --- S03 mode ---
    def test_s03_feature_returns_mode(self) -> None:
        presets = get_presets("S03", SpecKind.FEATURE)
        assert presets.get("mode") == "abstraction_leak"

    def test_s03_component_returns_empty(self) -> None:
        presets = get_presets("S03", SpecKind.COMPONENT)
        assert presets == {}

    # --- S04 skip ---
    def test_s04_feature_returns_skip(self) -> None:
        presets = get_presets("S04", SpecKind.FEATURE)
        assert presets.get("skip") is True

    def test_s04_component_returns_empty(self) -> None:
        presets = get_presets("S04", SpecKind.COMPONENT)
        assert presets == {}

    # --- S05 thresholds ---
    def test_s05_feature_thresholds(self) -> None:
        presets = get_presets("S05", SpecKind.FEATURE)
        assert presets["warn_threshold"] == 60
        assert presets["fail_threshold"] == 100

    def test_s05_component_returns_empty(self) -> None:
        presets = get_presets("S05", SpecKind.COMPONENT)
        assert presets == {}

    # --- S08 thresholds ---
    def test_s08_feature_thresholds(self) -> None:
        presets = get_presets("S08", SpecKind.FEATURE)
        assert presets["warn_threshold"] == 2
        assert presets["fail_threshold"] == 5

    def test_s08_component_returns_empty(self) -> None:
        presets = get_presets("S08", SpecKind.COMPONENT)
        assert presets == {}

    # --- Unchanged rules return empty ---
    @pytest.mark.parametrize("rule_id", ["S02", "S06", "S07", "S09", "S10", "S11"])
    def test_unchanged_rules_return_empty_for_feature(self, rule_id: str) -> None:
        presets = get_presets(rule_id, SpecKind.FEATURE)
        assert presets == {}

    @pytest.mark.parametrize("rule_id", ["S02", "S06", "S07", "S09", "S10", "S11"])
    def test_unchanged_rules_return_empty_for_component(self, rule_id: str) -> None:
        presets = get_presets(rule_id, SpecKind.COMPONENT)
        assert presets == {}

    # --- None kind returns empty (backwards compat) ---
    @pytest.mark.parametrize("rule_id", ["S01", "S03", "S04", "S05", "S08"])
    def test_none_kind_returns_empty(self, rule_id: str) -> None:
        """When kind is None, returns empty dict (use code defaults)."""
        presets = get_presets(rule_id, None)
        assert presets == {}

    # --- Unknown rule_id returns empty ---
    def test_unknown_rule_id_returns_empty(self) -> None:
        presets = get_presets("X99", SpecKind.FEATURE)
        assert presets == {}


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestSpecKindEdgeCases:
    """Edge cases for SpecKind and presets."""

    def test_case_sensitive_construction(self) -> None:
        """SpecKind('Feature') raises — StrEnum is case-sensitive."""
        with pytest.raises(ValueError, match="Feature"):
            SpecKind("Feature")
        with pytest.raises(ValueError, match="COMPONENT"):
            SpecKind("COMPONENT")

    def test_get_presets_returns_fresh_copy(self) -> None:
        """Mutating a returned dict must not affect subsequent calls."""
        presets1 = get_presets("S01", SpecKind.FEATURE)
        presets1["injected"] = "harmful"
        presets2 = get_presets("S01", SpecKind.FEATURE)
        assert "injected" not in presets2


class TestHeaderPatternRegex:
    """_HEADER_PATTERNS regexes match real spec heading variations."""

    def test_feature_intent_basic(self) -> None:
        """Matches '## Intent' followed by content."""
        from specweaver.validation.spec_kind import _HEADER_PATTERNS

        pattern = _HEADER_PATTERNS[SpecKind.FEATURE]
        text = "## Intent\n\nThe system enables selling shares.\n"
        match = pattern.search(text)
        assert match is not None
        assert "selling shares" in match.group(1)

    def test_feature_intent_extra_space(self) -> None:
        """Matches '##  Intent' (extra space)."""
        from specweaver.validation.spec_kind import _HEADER_PATTERNS

        pattern = _HEADER_PATTERNS[SpecKind.FEATURE]
        text = "##  Intent\n\nContent here.\n"
        match = pattern.search(text)
        assert match is not None

    def test_feature_intent_case_insensitive(self) -> None:
        """Matches '## INTENT' or '## intent'."""
        from specweaver.validation.spec_kind import _HEADER_PATTERNS

        pattern = _HEADER_PATTERNS[SpecKind.FEATURE]
        assert pattern.search("## INTENT\n\nContent.\n") is not None
        assert pattern.search("## intent\n\nContent.\n") is not None

    def test_component_purpose_basic(self) -> None:
        """Matches '## 1. Purpose'."""
        from specweaver.validation.spec_kind import _HEADER_PATTERNS

        pattern = _HEADER_PATTERNS[SpecKind.COMPONENT]
        text = "## 1. Purpose\n\nGreeter Service generates welcome messages.\n"
        match = pattern.search(text)
        assert match is not None
        assert "welcome messages" in match.group(1)

    def test_component_purpose_no_dot(self) -> None:
        """Matches '## 1 Purpose' (no dot after number)."""
        from specweaver.validation.spec_kind import _HEADER_PATTERNS

        pattern = _HEADER_PATTERNS[SpecKind.COMPONENT]
        text = "## 1 Purpose\n\nContent here.\n"
        match = pattern.search(text)
        assert match is not None

    def test_component_purpose_stops_at_next_heading(self) -> None:
        """Content extraction stops at the next ## heading."""
        from specweaver.validation.spec_kind import _HEADER_PATTERNS

        pattern = _HEADER_PATTERNS[SpecKind.COMPONENT]
        text = "## 1. Purpose\n\nFirst section.\n\n## 2. Contract\n\nSecond section.\n"
        match = pattern.search(text)
        assert match is not None
        assert "First section" in match.group(1)
        assert "Second section" not in match.group(1)
