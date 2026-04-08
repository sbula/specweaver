# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for RuleAtom -- adapts Rule ABC to Atom interface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.loom.atoms.base import AtomStatus
from specweaver.loom.atoms.rule_atom import RuleAtom
from specweaver.validation.models import Rule, RuleResult

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class _PassingRule(Rule):
    @property
    def rule_id(self) -> str:
        return "S99"

    @property
    def name(self) -> str:
        return "Passing Rule"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        return self._pass("all good")


class _FailingRule(Rule):
    @property
    def rule_id(self) -> str:
        return "S98"

    @property
    def name(self) -> str:
        return "Failing Rule"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        return self._fail("bad stuff")


class _WarnRule(Rule):
    @property
    def rule_id(self) -> str:
        return "S97"

    @property
    def name(self) -> str:
        return "Warning Rule"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        return self._warn("not ideal")


class _SkipRule(Rule):
    @property
    def rule_id(self) -> str:
        return "S96"

    @property
    def name(self) -> str:
        return "Skip Rule"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        return self._skip("not applicable")


class _CrashingRule(Rule):
    @property
    def rule_id(self) -> str:
        return "S95"

    @property
    def name(self) -> str:
        return "Crashing Rule"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        msg = "boom"
        raise RuntimeError(msg)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRuleAtom:
    """Test RuleAtom adapts Rule.check() to Atom.run()."""

    def test_passing_rule_returns_success(self) -> None:
        atom = RuleAtom(_PassingRule())
        result = atom.run({"spec_text": "hello", "spec_path": None})
        assert result.status == AtomStatus.SUCCESS
        assert "S99" in result.message

    def test_failing_rule_returns_failed(self) -> None:
        atom = RuleAtom(_FailingRule())
        result = atom.run({"spec_text": "hello", "spec_path": None})
        assert result.status == AtomStatus.FAILED
        assert "S98" in result.message

    def test_warn_rule_returns_success(self) -> None:
        """WARN is not FAIL — maps to SUCCESS."""
        atom = RuleAtom(_WarnRule())
        result = atom.run({"spec_text": "hello", "spec_path": None})
        assert result.status == AtomStatus.SUCCESS

    def test_skip_rule_returns_success(self) -> None:
        """SKIP is not FAIL — maps to SUCCESS."""
        atom = RuleAtom(_SkipRule())
        result = atom.run({"spec_text": "hello", "spec_path": None})
        assert result.status == AtomStatus.SUCCESS

    def test_exports_rule_result(self) -> None:
        """AtomResult.exports has the RuleResult."""
        atom = RuleAtom(_PassingRule())
        result = atom.run({"spec_text": "hello", "spec_path": None})
        assert "rule_result" in result.exports
        rr = result.exports["rule_result"]
        assert isinstance(rr, RuleResult)
        assert rr.rule_id == "S99"

    def test_crashing_rule_returns_failed(self) -> None:
        """Unhandled exception in rule maps to FAILED."""
        atom = RuleAtom(_CrashingRule())
        result = atom.run({"spec_text": "hello", "spec_path": None})
        assert result.status == AtomStatus.FAILED
        assert "boom" in result.message

    def test_is_atom_subclass(self) -> None:
        """RuleAtom is a proper Atom subclass."""
        from specweaver.loom.atoms.base import Atom

        atom = RuleAtom(_PassingRule())
        assert isinstance(atom, Atom)
