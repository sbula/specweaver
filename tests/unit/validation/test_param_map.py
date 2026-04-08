# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests — PARAM_MAP contract for all configurable rules + executor edge cases.

Every configurable rule in SpecWeaver self-declares its DB-overridable
parameters via the ``PARAM_MAP`` class variable (inherited from ``Rule``).
These tests verify:

1. The ``Rule`` ABC defines ``PARAM_MAP`` as an empty-dict default.
2. Every configurable rule subclass has a non-empty PARAM_MAP.
3. The PARAM_MAP keys match valid DB column names.
4. The PARAM_MAP values are valid constructor parameter names.
5. ``_build_rule_kwargs`` edge cases (no PARAM_MAP, None settings, None rule_id).

Rule PARAM_MAP reference:
  S01  warn_threshold→warn_conjunctions, fail_threshold→fail_conjunctions, extra:max_h2→max_h2
  S03  warn_threshold→warn_threshold, fail_threshold→fail_threshold
  S04  warn_threshold→warn_threshold, fail_threshold→fail_threshold
  S05  warn_threshold→warn_threshold, fail_threshold→fail_threshold
  S07  warn_threshold→warn_score, fail_threshold→fail_score
  S08  warn_threshold→warn_threshold, fail_threshold→fail_threshold
  S11  warn_threshold→warn_threshold, fail_threshold→fail_threshold
  C04  fail_threshold→threshold
"""

from __future__ import annotations

from typing import ClassVar

import pytest

import specweaver.validation.rules.code
import specweaver.validation.rules.spec  # noqa: F401 — register all spec rules
from specweaver.config.settings import RuleOverride, ValidationSettings
from specweaver.validation.executor import (
    _build_rule_kwargs,
    _get_rule_id_from_cls,
)
from specweaver.validation.models import Rule

# ---------------------------------------------------------------------------
# Import the rule classes we are testing
# ---------------------------------------------------------------------------
from specweaver.validation.rules.code.c04_coverage import CoverageRule
from specweaver.validation.rules.spec.s01_one_sentence import OneSentenceRule
from specweaver.validation.rules.spec.s03_stranger import StrangerTestRule
from specweaver.validation.rules.spec.s04_dependency_dir import DependencyDirectionRule
from specweaver.validation.rules.spec.s05_day_test import DayTestRule
from specweaver.validation.rules.spec.s07_test_first import TestFirstRule
from specweaver.validation.rules.spec.s08_ambiguity import AmbiguityRule
from specweaver.validation.rules.spec.s11_terminology import TerminologyRule

# Valid DB-settable column names
_VALID_DB_KEYS = frozenset(
    {"warn_threshold", "fail_threshold"} | {f"extra:{k}" for k in ("max_h2",)}
)


# ===========================================================================
# Rule ABC — PARAM_MAP default
# ===========================================================================


class TestRuleABCParamMap:
    """The Rule ABC defines PARAM_MAP as an empty dict (scenario 56-57)."""

    def test_rule_has_param_map_attribute(self) -> None:
        """Rule ABC has PARAM_MAP ClassVar attribute."""
        assert hasattr(Rule, "PARAM_MAP")

    def test_rule_param_map_is_dict(self) -> None:
        """Rule.PARAM_MAP is a dict."""
        assert isinstance(Rule.PARAM_MAP, dict)

    def test_rule_param_map_default_is_empty(self) -> None:
        """Rule.PARAM_MAP defaults to {}."""
        # A minimal stub rule that doesn't override PARAM_MAP

        class _StubRule(Rule):
            @property
            def rule_id(self) -> str:
                return "XX"

            @property
            def name(self) -> str:
                return "Stub"

            def run(self, spec_text: str, **kwargs: object) -> object:  # type: ignore[override]
                pass

        assert _StubRule.PARAM_MAP == {}

    def test_stub_rule_inherits_empty_param_map(self) -> None:
        """Subclass without explicit PARAM_MAP inherits empty dict."""

        class _MinimalRule(Rule):
            @property
            def rule_id(self) -> str:
                return "ZZ"

            @property
            def name(self) -> str:
                return "Minimal"

            def run(self, spec_text: str, **kwargs: object) -> object:  # type: ignore[override]
                pass

        assert _MinimalRule.PARAM_MAP == {}


# ===========================================================================
# Per-rule PARAM_MAP completeness (scenario 58, 67-75)
# ===========================================================================


class TestS01ParamMap:
    """S01 OneSentenceRule PARAM_MAP (scenario 67)."""

    def test_param_map_non_empty(self) -> None:
        assert OneSentenceRule.PARAM_MAP

    def test_maps_warn_threshold(self) -> None:
        assert "warn_threshold" in OneSentenceRule.PARAM_MAP
        assert OneSentenceRule.PARAM_MAP["warn_threshold"] == "warn_conjunctions"

    def test_maps_fail_threshold(self) -> None:
        assert "fail_threshold" in OneSentenceRule.PARAM_MAP
        assert OneSentenceRule.PARAM_MAP["fail_threshold"] == "fail_conjunctions"

    def test_maps_extra_max_h2(self) -> None:
        assert "extra:max_h2" in OneSentenceRule.PARAM_MAP
        assert OneSentenceRule.PARAM_MAP["extra:max_h2"] == "max_h2"

    def test_all_values_are_constructor_params(self) -> None:
        """Each PARAM_MAP value is a valid OneSentenceRule constructor param."""
        import inspect

        sig = inspect.signature(OneSentenceRule.__init__)
        for db_key, ctor_param in OneSentenceRule.PARAM_MAP.items():
            if not db_key.startswith("extra:"):
                assert ctor_param in sig.parameters, (
                    f"PARAM_MAP value '{ctor_param}' (for db_key '{db_key}') "
                    f"is not a constructor parameter"
                )


class TestS03ParamMap:
    """S03 StrangerTestRule PARAM_MAP (scenario 68)."""

    def test_param_map_non_empty(self) -> None:
        assert StrangerTestRule.PARAM_MAP

    def test_maps_warn_threshold(self) -> None:
        assert "warn_threshold" in StrangerTestRule.PARAM_MAP

    def test_maps_fail_threshold(self) -> None:
        assert "fail_threshold" in StrangerTestRule.PARAM_MAP


class TestS04ParamMap:
    """S04 DependencyDirectionRule PARAM_MAP (scenario 69)."""

    def test_param_map_non_empty(self) -> None:
        assert DependencyDirectionRule.PARAM_MAP

    def test_maps_warn_threshold(self) -> None:
        assert "warn_threshold" in DependencyDirectionRule.PARAM_MAP

    def test_maps_fail_threshold(self) -> None:
        assert "fail_threshold" in DependencyDirectionRule.PARAM_MAP


class TestS05ParamMap:
    """S05 DayTestRule PARAM_MAP (scenario 70)."""

    def test_param_map_non_empty(self) -> None:
        assert DayTestRule.PARAM_MAP

    def test_maps_warn_threshold(self) -> None:
        assert "warn_threshold" in DayTestRule.PARAM_MAP

    def test_maps_fail_threshold(self) -> None:
        assert "fail_threshold" in DayTestRule.PARAM_MAP


class TestS07ParamMap:
    """S07 TestFirstRule PARAM_MAP (scenario 71)."""

    def test_param_map_non_empty(self) -> None:
        assert TestFirstRule.PARAM_MAP

    def test_maps_warn_threshold_to_warn_score(self) -> None:
        assert TestFirstRule.PARAM_MAP.get("warn_threshold") == "warn_score"

    def test_maps_fail_threshold_to_fail_score(self) -> None:
        assert TestFirstRule.PARAM_MAP.get("fail_threshold") == "fail_score"


class TestS08ParamMap:
    """S08 AmbiguityRule PARAM_MAP (scenario 72)."""

    def test_param_map_non_empty(self) -> None:
        assert AmbiguityRule.PARAM_MAP

    def test_maps_warn_threshold(self) -> None:
        assert "warn_threshold" in AmbiguityRule.PARAM_MAP

    def test_maps_fail_threshold(self) -> None:
        assert "fail_threshold" in AmbiguityRule.PARAM_MAP


class TestS11ParamMap:
    """S11 TerminologyRule PARAM_MAP (scenario 73)."""

    def test_param_map_non_empty(self) -> None:
        assert TerminologyRule.PARAM_MAP

    def test_maps_warn_threshold(self) -> None:
        assert "warn_threshold" in TerminologyRule.PARAM_MAP

    def test_maps_fail_threshold(self) -> None:
        assert "fail_threshold" in TerminologyRule.PARAM_MAP


class TestC04ParamMap:
    """C04 CoverageRule PARAM_MAP (scenario 74)."""

    def test_param_map_non_empty(self) -> None:
        assert CoverageRule.PARAM_MAP

    def test_maps_fail_threshold_to_threshold(self) -> None:
        assert CoverageRule.PARAM_MAP.get("fail_threshold") == "threshold"

    def test_all_values_are_constructor_params(self) -> None:
        import inspect

        sig = inspect.signature(CoverageRule.__init__)
        for db_key, ctor_param in CoverageRule.PARAM_MAP.items():
            if not db_key.startswith("extra:"):
                assert ctor_param in sig.parameters


class TestAllRuleParamMapsValid:
    """Cross-rule: PARAM_MAP keys match valid DB column names (scenario 75)."""

    CONFIGURABLE_RULES: ClassVar[list[tuple[str, type]]] = [
        ("S01", OneSentenceRule),
        ("S03", StrangerTestRule),
        ("S04", DependencyDirectionRule),
        ("S05", DayTestRule),
        ("S07", TestFirstRule),
        ("S08", AmbiguityRule),
        ("S11", TerminologyRule),
        ("C04", CoverageRule),
    ]

    def test_all_rules_have_non_empty_param_map(self) -> None:
        for rule_id, rule_cls in self.CONFIGURABLE_RULES:
            assert rule_cls.PARAM_MAP, f"{rule_id} has an empty PARAM_MAP"

    def test_all_param_map_keys_are_valid_db_keys(self) -> None:
        """Every PARAM_MAP key must be a recognised DB column or extra: key."""
        valid_simple_keys = {"warn_threshold", "fail_threshold"}
        for rule_id, rule_cls in self.CONFIGURABLE_RULES:
            for key in rule_cls.PARAM_MAP:
                assert key in valid_simple_keys or key.startswith("extra:"), (
                    f"{rule_id}.PARAM_MAP has unknown key '{key}'"
                )

    def test_all_param_map_values_are_strings(self) -> None:
        for rule_id, rule_cls in self.CONFIGURABLE_RULES:
            for key, value in rule_cls.PARAM_MAP.items():
                assert isinstance(value, str), (
                    f"{rule_id}.PARAM_MAP[{key!r}] is not a string: {value!r}"
                )


# ===========================================================================
# executor._build_rule_kwargs — edge cases (scenarios 61-63)
# ===========================================================================


class TestBuildRuleKwargsEdgeCases:
    """Edge cases for _build_rule_kwargs not covered by main tests."""

    def test_none_settings_returns_empty(self) -> None:
        """_build_rule_kwargs returns {} when settings is None (scenario 62)."""
        result = _build_rule_kwargs(OneSentenceRule, settings=None)
        assert result == {}

    def test_rule_with_empty_param_map_returns_empty(self) -> None:
        """Rule with PARAM_MAP = {} returns {} without crashing (scenario 61)."""

        class _NoParamRule(Rule):
            PARAM_MAP: ClassVar[dict[str, str]] = {}  # type: ignore[assignment]

            @property
            def rule_id(self) -> str:
                return "NP"

            @property
            def name(self) -> str:
                return "NoParams"

            def run(self, spec_text: str, **kwargs: object) -> object:  # type: ignore[override]
                pass

        settings = ValidationSettings(
            overrides={"NP": RuleOverride(rule_id="NP", warn_threshold=5.0)},
        )
        result = _build_rule_kwargs(_NoParamRule, settings=settings)
        assert result == {}

    def test_no_override_for_rule_returns_empty(self) -> None:
        """Rule not in settings.overrides returns {}."""
        settings = ValidationSettings(overrides={})
        result = _build_rule_kwargs(OneSentenceRule, settings=settings)
        assert result == {}


# ===========================================================================
# executor._get_rule_id_from_cls — all 9 configurable rules (scenario 63)
# ===========================================================================


class TestGetRuleIdFromCls:
    """_get_rule_id_from_cls correctly resolves rule_id for all configurable rules."""

    @pytest.mark.parametrize(
        "rule_cls, expected_id",
        [
            (OneSentenceRule, "S01"),
            (StrangerTestRule, "S03"),
            (DependencyDirectionRule, "S04"),
            (DayTestRule, "S05"),
            (TestFirstRule, "S07"),
            (AmbiguityRule, "S08"),
            (TerminologyRule, "S11"),
            (CoverageRule, "C04"),
        ],
    )
    def test_rule_id_resolved(self, rule_cls: type, expected_id: str) -> None:
        assert _get_rule_id_from_cls(rule_cls) == expected_id

    def test_returns_none_for_class_that_crashes_on_init(self) -> None:
        """_get_rule_id_from_cls returns None when instantiation fails."""

        class _BrokenRule:
            def __init__(self) -> None:
                raise RuntimeError("cannot instantiate")

        result = _get_rule_id_from_cls(_BrokenRule)
        assert result is None
