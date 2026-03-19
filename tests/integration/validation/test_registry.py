# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Integration tests for rule registry — verifies all 19 built-in rules
are auto-registered correctly and the runner still produces correct results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest

from specweaver.validation.models import Rule

if TYPE_CHECKING:
    from specweaver.validation.registry import RuleRegistry

# ---------------------------------------------------------------------------
# Fresh registry helpers
# ---------------------------------------------------------------------------


def _populated_registry() -> RuleRegistry:
    """Create a fresh registry and populate it by importing rule packages.

    We can't simply use get_registry() because the global singleton may
    already have rules from other test modules. Instead, we verify that
    importing the packages registers into the global registry.
    """
    # Trigger auto-registration (idempotent — already imported in many tests)
    import specweaver.validation.rules.code
    import specweaver.validation.rules.spec  # noqa: F401
    from specweaver.validation.registry import get_registry

    return get_registry()


# ---------------------------------------------------------------------------
# Built-in rule registration
# ---------------------------------------------------------------------------


class TestBuiltInRegistration:
    """Verify all 19 built-in rules are registered."""

    EXPECTED_SPEC_IDS: ClassVar[list[str]] = [
        "S01", "S02", "S03", "S04", "S05", "S06",
        "S07", "S08", "S09", "S10", "S11",
    ]
    EXPECTED_CODE_IDS: ClassVar[list[str]] = [
        "C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08",
    ]

    def test_all_spec_rules_registered(self):
        """All 11 spec rules (S01-S11) are registered."""
        reg = _populated_registry()
        spec_ids = [rid for rid, _cls in reg.list_spec()]
        assert spec_ids == self.EXPECTED_SPEC_IDS

    def test_all_code_rules_registered(self):
        """All 8 code rules (C01-C08) are registered."""
        reg = _populated_registry()
        code_ids = [rid for rid, _cls in reg.list_code()]
        assert code_ids == self.EXPECTED_CODE_IDS

    def test_total_rule_count(self):
        """Total of 19 rules registered."""
        reg = _populated_registry()
        assert len(reg.list_all()) == 19

    def test_all_rules_are_rule_subclasses(self):
        """Every registered class is a Rule subclass."""
        reg = _populated_registry()
        for _rid, cls, _cat in reg.list_all():
            assert issubclass(cls, Rule), f"{cls.__name__} is not a Rule subclass"

    def test_each_rule_can_be_instantiated(self):
        """Every registered rule can be instantiated with no args."""
        reg = _populated_registry()
        for rid, cls, _cat in reg.list_all():
            try:
                instance = cls()
            except Exception as exc:
                pytest.fail(f"Failed to instantiate {rid} ({cls.__name__}): {exc}")
            assert instance.rule_id == rid

    def test_spec_categories_correct(self):
        """All spec rules have category 'spec'."""
        reg = _populated_registry()
        for rid, _cls, cat in reg.list_all():
            if rid.startswith("S"):
                assert cat == "spec", f"{rid} has wrong category: {cat}"

    def test_code_categories_correct(self):
        """All code rules have category 'code'."""
        reg = _populated_registry()
        for rid, _cls, cat in reg.list_all():
            if rid.startswith("C"):
                assert cat == "code", f"{rid} has wrong category: {cat}"


# ---------------------------------------------------------------------------
# Runner ↔ registry integration
# ---------------------------------------------------------------------------


class TestRunnerRegistryIntegration:
    """Verify runner functions produce the same results via registry."""

    def test_get_spec_rules_returns_11(self):
        """get_spec_rules() returns 11 rules (all non-LLM spec rules)."""
        from specweaver.validation.runner import get_spec_rules
        rules = get_spec_rules()
        assert len(rules) == 11

    def test_get_spec_rules_ids_match(self):
        """get_spec_rules() returns rules in S01-S11 order."""
        from specweaver.validation.runner import get_spec_rules
        rules = get_spec_rules()
        ids = [r.rule_id for r in rules]
        assert ids == ["S01", "S02", "S03", "S04", "S05", "S06",
                        "S07", "S08", "S09", "S10", "S11"]

    def test_get_code_rules_without_subprocess(self):
        """get_code_rules(include_subprocess=False) returns 6 rules."""
        from specweaver.validation.runner import get_code_rules
        rules = get_code_rules(include_subprocess=False)
        assert len(rules) == 6
        ids = [r.rule_id for r in rules]
        assert "C03" not in ids
        assert "C04" not in ids

    def test_get_code_rules_with_subprocess(self):
        """get_code_rules(include_subprocess=True) returns 8 rules."""
        from specweaver.validation.runner import get_code_rules
        rules = get_code_rules(include_subprocess=True)
        assert len(rules) == 8
        ids = [r.rule_id for r in rules]
        assert ids == ["C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08"]
