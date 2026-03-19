# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Unit tests for the RuleRegistry — Phase A of Feature 3.4.

Tests the rule registry module that maps rule IDs to Rule classes,
replacing hardcoded imports in runner.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.validation.models import Rule, RuleResult

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Test helper: minimal Rule subclass for registry tests
# ---------------------------------------------------------------------------


class _FakeRule(Rule):
    """Minimal Rule subclass for registry testing."""

    @property
    def rule_id(self) -> str:
        return "S99"

    @property
    def name(self) -> str:
        return "Fake Rule"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        return self._pass("ok")


class _FakeRule2(Rule):
    """Second fake rule for duplicate-ID tests."""

    @property
    def rule_id(self) -> str:
        return "S98"

    @property
    def name(self) -> str:
        return "Fake Rule 2"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        return self._pass("ok")


class _CustomRule(Rule):
    """Fake domain-specific custom rule with D-prefix."""

    @property
    def rule_id(self) -> str:
        return "D01"

    @property
    def name(self) -> str:
        return "Custom Domain Rule"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        return self._pass("ok")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def registry():
    """Return a fresh RuleRegistry instance (not the global singleton)."""
    from specweaver.validation.registry import RuleRegistry
    return RuleRegistry()


# ---------------------------------------------------------------------------
# Registration basics
# ---------------------------------------------------------------------------


class TestRegister:
    """Test RuleRegistry.register()."""

    def test_register_spec_rule(self, registry):
        """Register a spec rule and retrieve it."""
        registry.register("S99", _FakeRule, "spec")
        assert registry.get("S99") is _FakeRule

    def test_register_code_rule(self, registry):
        """Register a code rule and retrieve it."""
        registry.register("C99", _FakeRule, "code")
        assert registry.get("C99") is _FakeRule

    def test_register_custom_rule_d_prefix(self, registry):
        """Custom rules with D-prefix can be registered."""
        registry.register("D01", _CustomRule, "spec")
        assert registry.get("D01") is _CustomRule

    def test_register_duplicate_raises(self, registry):
        """Registering the same ID twice raises ValueError."""
        registry.register("S99", _FakeRule, "spec")
        with pytest.raises(ValueError, match="already registered"):
            registry.register("S99", _FakeRule2, "spec")

    def test_register_invalid_category_raises(self, registry):
        """Category must be 'spec' or 'code'."""
        with pytest.raises(ValueError, match="category"):
            registry.register("S99", _FakeRule, "invalid")


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


class TestGet:
    """Test RuleRegistry.get()."""

    def test_get_existing(self, registry):
        """Get returns the class for registered rule."""
        registry.register("S99", _FakeRule, "spec")
        assert registry.get("S99") is _FakeRule

    def test_get_nonexistent_returns_none(self, registry):
        """Get returns None for unregistered rule."""
        assert registry.get("X99") is None


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


class TestListing:
    """Test list_spec(), list_code(), list_all()."""

    def test_list_spec_empty(self, registry):
        """Empty registry returns empty list."""
        assert registry.list_spec() == []

    def test_list_spec_only_returns_spec(self, registry):
        """list_spec returns only spec-category rules."""
        registry.register("S99", _FakeRule, "spec")
        registry.register("C99", _FakeRule2, "code")
        result = registry.list_spec()
        assert len(result) == 1
        assert result[0] == ("S99", _FakeRule)

    def test_list_code_only_returns_code(self, registry):
        """list_code returns only code-category rules."""
        registry.register("S99", _FakeRule, "spec")
        registry.register("C99", _FakeRule2, "code")
        result = registry.list_code()
        assert len(result) == 1
        assert result[0] == ("C99", _FakeRule2)

    def test_list_spec_sorted_by_id(self, registry):
        """list_spec returns rules sorted by rule_id."""
        registry.register("S11", _FakeRule, "spec")
        registry.register("S01", _FakeRule2, "spec")
        ids = [r[0] for r in registry.list_spec()]
        assert ids == ["S01", "S11"]

    def test_list_code_sorted_by_id(self, registry):
        """list_code returns rules sorted by rule_id."""
        registry.register("C08", _FakeRule, "code")
        registry.register("C01", _FakeRule2, "code")
        ids = [r[0] for r in registry.list_code()]
        assert ids == ["C01", "C08"]

    def test_list_all_returns_everything(self, registry):
        """list_all returns all rules with category."""
        registry.register("S99", _FakeRule, "spec")
        registry.register("C99", _FakeRule2, "code")
        result = registry.list_all()
        assert len(result) == 2
        # Each item is (rule_id, rule_class, category)
        assert ("S99", _FakeRule, "spec") in result
        assert ("C99", _FakeRule2, "code") in result

    def test_list_all_sorted_by_id(self, registry):
        """list_all returns rules sorted by rule_id."""
        registry.register("C01", _FakeRule2, "code")
        registry.register("S01", _FakeRule, "spec")
        ids = [r[0] for r in registry.list_all()]
        assert ids == ["C01", "S01"]


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------


class TestGlobalRegistry:
    """Test get_registry() singleton."""

    def test_get_registry_returns_same_instance(self):
        """get_registry() always returns the same instance."""
        from specweaver.validation.registry import get_registry
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2

    def test_get_registry_is_rule_registry(self):
        """get_registry() returns a RuleRegistry instance."""
        from specweaver.validation.registry import RuleRegistry, get_registry
        assert isinstance(get_registry(), RuleRegistry)
