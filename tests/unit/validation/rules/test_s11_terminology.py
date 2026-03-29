# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Unit tests for S11 TerminologyRule — inconsistent naming and undefined terms."""

from __future__ import annotations

from specweaver.validation.models import Status
from specweaver.validation.rules.spec.s11_terminology import (
    TerminologyRule,
    _extract_code_block_content,
    _extract_heading_terms,
    _find_line,
    _normalize_term,
)

# ── Helper functions ─────────────────────────────────────────────────────


class TestNormalizeTerm:
    def test_camel_case(self) -> None:
        assert _normalize_term("userId") == "userid"

    def test_snake_case(self) -> None:
        assert _normalize_term("user_id") == "userid"

    def test_pascal_case(self) -> None:
        assert _normalize_term("UserId") == "userid"

    def test_all_upper(self) -> None:
        assert _normalize_term("USERID") == "userid"

    def test_mixed(self) -> None:
        assert _normalize_term("user_ID") == "userid"


class TestExtractCodeBlockContent:
    def test_extracts_fenced_blocks(self) -> None:
        text = "before\n```python\ncode here\n```\nafter\n"
        result = _extract_code_block_content(text)
        assert "code here" in result

    def test_multiple_blocks(self) -> None:
        text = "```a\nfirst\n```\nmiddle\n```b\nsecond\n```\n"
        result = _extract_code_block_content(text)
        assert "first" in result
        assert "second" in result

    def test_no_blocks(self) -> None:
        result = _extract_code_block_content("plain text only")
        assert result == ""


class TestExtractHeadingTerms:
    def test_extracts_backtick_terms(self) -> None:
        text = "## The `FlowEngine` Module\n\nSome text.\n"
        terms = _extract_heading_terms(text)
        assert "FlowEngine" in terms

    def test_no_backtick_terms(self) -> None:
        text = "## Simple Heading\n"
        terms = _extract_heading_terms(text)
        assert len(terms) == 0


class TestFindLine:
    def test_finds_first_occurrence(self) -> None:
        text = "line one\nline two\n"
        assert _find_line(text, "two") == 2

    def test_returns_none_when_absent(self) -> None:
        assert _find_line("hello\nworld\n", "missing") is None


# ── TerminologyRule.check() ──────────────────────────────────────────────


class TestTerminologyRuleConsistency:
    def test_consistent_casing_passes(self) -> None:
        spec = "The `userId` field is used to identify the `userId` in the system.\n"
        rule = TerminologyRule()
        result = rule.check(spec)
        assert result.status == Status.PASS

    def test_inconsistent_casing_warns(self) -> None:
        spec = "The `userId` is stored. Later we reference `user_id` for lookup.\n"
        rule = TerminologyRule()
        result = rule.check(spec)
        assert result.status in (Status.WARN, Status.FAIL)

    def test_multiple_inconsistencies_fail(self) -> None:
        spec = (
            "Use `userId` here.\n"
            "Use `user_id` there.\n"
            "Use `FlowEngine` here.\n"
            "Use `flow_engine` there.\n"
            "Use `RunStatus` here.\n"
            "Use `run_status` there.\n"
        )
        rule = TerminologyRule()
        result = rule.check(spec)
        assert result.status == Status.FAIL

    def test_short_terms_casing_ignored(self) -> None:
        """Terms <= 2 chars are ignored by the casing consistency check,
        but PascalCase terms can still be flagged as undefined."""
        spec = "Use `foo` here and `foo` there.\n"  # same term, consistent
        rule = TerminologyRule()
        result = rule.check(spec)
        assert result.status == Status.PASS

    def test_empty_spec_passes(self) -> None:
        rule = TerminologyRule()
        result = rule.check("")
        assert result.status == Status.PASS

    def test_whitespace_only_passes(self) -> None:
        rule = TerminologyRule()
        result = rule.check("   \n\n   ")
        assert result.status == Status.PASS


class TestTerminologyRuleUndefined:
    def test_defined_in_heading_not_flagged(self) -> None:
        spec = "## The `FlowEngine`\n\nThe `FlowEngine` orchestrates steps.\n"
        rule = TerminologyRule()
        result = rule.check(spec)
        assert result.status == Status.PASS

    def test_defined_in_code_block_not_flagged(self) -> None:
        spec = "```python\nclass FlowEngine:\n    pass\n```\n\nThe `FlowEngine` runs pipelines.\n"
        rule = TerminologyRule()
        result = rule.check(spec)
        assert result.status == Status.PASS

    def test_undefined_pascal_case_warns(self) -> None:
        spec = "The `StateManager` handles all persistence. No heading or code block defines it.\n"
        rule = TerminologyRule()
        result = rule.check(spec)
        assert result.status in (Status.WARN, Status.FAIL)

    def test_snake_case_not_flagged_as_undefined(self) -> None:
        """Only PascalCase terms are checked for definitions."""
        spec = "The `state_manager` does stuff.\n"
        rule = TerminologyRule()
        result = rule.check(spec)
        assert result.status == Status.PASS

    def test_custom_thresholds(self) -> None:
        rule = TerminologyRule(warn_threshold=10, fail_threshold=20)
        spec = "The `UndefinedThing` is used once.\n"
        result = rule.check(spec)
        assert result.status == Status.PASS  # Below warn threshold

    def test_rule_id(self) -> None:
        assert TerminologyRule().rule_id == "S11"
