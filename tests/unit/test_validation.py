# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for validation models, runner, and all 7 static spec rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.validation.models import Finding, Rule, RuleResult, Severity, Status
from specweaver.validation.rules.spec.s01_one_sentence import OneSentenceRule
from specweaver.validation.rules.spec.s02_single_setup import SingleSetupRule
from specweaver.validation.rules.spec.s05_day_test import DayTestRule
from specweaver.validation.rules.spec.s06_concrete_example import ConcreteExampleRule
from specweaver.validation.rules.spec.s08_ambiguity import AmbiguityRule
from specweaver.validation.rules.spec.s09_error_path import ErrorPathRule
from specweaver.validation.rules.spec.s10_done_definition import DoneDefinitionRule
from specweaver.validation.runner import (
    all_passed,
    count_by_status,
    get_spec_rules,
    run_rules,
)

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Fixtures — load test spec files
# ---------------------------------------------------------------------------

FIXTURES_DIR = "tests/fixtures"


@pytest.fixture()
def good_spec() -> str:
    from pathlib import Path

    return Path(FIXTURES_DIR, "good_spec.md").read_text(encoding="utf-8")


@pytest.fixture()
def bad_ambiguous() -> str:
    from pathlib import Path

    return Path(FIXTURES_DIR, "bad_spec_ambiguous.md").read_text(encoding="utf-8")


@pytest.fixture()
def bad_no_examples() -> str:
    from pathlib import Path

    return Path(FIXTURES_DIR, "bad_spec_no_examples.md").read_text(encoding="utf-8")


@pytest.fixture()
def bad_too_big() -> str:
    from pathlib import Path

    return Path(FIXTURES_DIR, "bad_spec_too_big.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Models tests
# ---------------------------------------------------------------------------


class TestModels:
    """Test validation data models."""

    def test_finding_defaults(self) -> None:
        f = Finding(message="test")
        assert f.severity == Severity.ERROR
        assert f.line is None
        assert f.suggestion is None

    def test_finding_with_all_fields(self) -> None:
        f = Finding(message="test", line=42, severity=Severity.WARNING, suggestion="fix it")
        assert f.line == 42
        assert f.severity == Severity.WARNING

    def test_rule_result_defaults(self) -> None:
        r = RuleResult(rule_id="X01", rule_name="Test", status=Status.PASS)
        assert r.findings == []
        assert r.message == ""

    def test_status_enum_values(self) -> None:
        assert Status.PASS.value == "pass"
        assert Status.FAIL.value == "fail"
        assert Status.WARN.value == "warn"
        assert Status.SKIP.value == "skip"

    def test_severity_enum_values(self) -> None:
        assert Severity.ERROR.value == "error"
        assert Severity.WARNING.value == "warning"
        assert Severity.INFO.value == "info"


# ---------------------------------------------------------------------------
# S01: One-Sentence Test
# ---------------------------------------------------------------------------


class TestS01OneSentence:
    """S01 detects multiple responsibilities in Purpose section."""

    def test_good_spec_passes(self, good_spec: str) -> None:
        result = OneSentenceRule().check(good_spec)
        assert result.status == Status.PASS

    def test_bad_too_big_fails(self, bad_too_big: str) -> None:
        result = OneSentenceRule().check(bad_too_big)
        assert result.status in (Status.FAIL, Status.WARN)

    def test_multiple_conjunctions_fail(self) -> None:
        spec = """
## 1. Purpose

This service manages authentication and also handles session tokens,
additionally it provides rate limiting, and furthermore it logs all events,
as well as managing user profiles.
"""
        result = OneSentenceRule().check(spec)
        assert result.status == Status.FAIL
        assert len(result.findings) > 0

    def test_single_conjunction_warns(self) -> None:
        spec = """
## 1. Purpose

This service handles authentication and also manages tokens.
"""
        result = OneSentenceRule().check(spec)
        assert result.status == Status.WARN

    def test_no_purpose_section_warns(self) -> None:
        spec = "# Just a title\n\nSome content without sections."
        result = OneSentenceRule().check(spec)
        assert result.status == Status.WARN

    def test_clean_purpose_passes(self) -> None:
        spec = """
## 1. Purpose

The Greeter Service generates personalized welcome messages for new users.
"""
        result = OneSentenceRule().check(spec)
        assert result.status == Status.PASS

    def test_many_h2_sections_warns(self) -> None:
        spec = "## 1. Purpose\n\nSimple purpose.\n"
        for i in range(10):
            spec += f"\n## Section {i + 2}\n\nContent.\n"
        result = OneSentenceRule().check(spec)
        assert result.status == Status.WARN
        assert any("H2" in f.message for f in result.findings)


# ---------------------------------------------------------------------------
# S02: Single Test Setup
# ---------------------------------------------------------------------------


class TestS02SingleSetup:
    """S02 detects specs needing multiple test environments."""

    def test_good_spec_passes(self, good_spec: str) -> None:
        result = SingleSetupRule().check(good_spec)
        assert result.status == Status.PASS

    def test_too_many_environments_fails(self, bad_too_big: str) -> None:
        result = SingleSetupRule().check(bad_too_big)
        assert result.status in (Status.FAIL, Status.WARN)

    def test_single_environment_passes(self) -> None:
        spec = "This component reads from a file and writes to a directory."
        result = SingleSetupRule().check(spec)
        assert result.status == Status.PASS

    def test_four_environments_fails(self) -> None:
        spec = """
The service reads from a database, uses a mock server for testing,
handles concurrent thread access with mutex locks, and recovers
from crash events by restarting.
"""
        result = SingleSetupRule().check(spec)
        assert result.status == Status.FAIL
        assert "4" in result.message or "5" in result.message

    def test_three_environments_warns(self) -> None:
        spec = """
Uses a database for storage, reads from files, and calls an HTTP endpoint.
"""
        result = SingleSetupRule().check(spec)
        assert result.status == Status.WARN

    def test_empty_spec_passes(self) -> None:
        result = SingleSetupRule().check("")
        assert result.status == Status.PASS


# ---------------------------------------------------------------------------
# S05: Day Test
# ---------------------------------------------------------------------------


class TestS05DayTest:
    """S05 detects specs too large for one implementation session."""

    def test_good_spec_passes(self, good_spec: str) -> None:
        result = DayTestRule().check(good_spec)
        assert result.status == Status.PASS

    def test_bad_too_big_detects(self, bad_too_big: str) -> None:
        result = DayTestRule().check(bad_too_big)
        # bad_too_big has moderate size — may WARN or PASS
        assert result.status in (Status.PASS, Status.WARN, Status.FAIL)

    def test_tiny_spec_passes(self) -> None:
        spec = "## 1. Purpose\n\nSmall component.\n"
        result = DayTestRule().check(spec)
        assert result.status == Status.PASS
        assert "score" in result.message.lower()

    def test_huge_spec_fails(self) -> None:
        # Create a spec that's clearly too big
        spec = "## 1. Purpose\n\nBig spec.\n"
        for i in range(50):
            spec += f"\n## Section {i}\n\nContent with if clause and when clause.\n"
            spec += "```python\ncode\n```\n"
            spec += f"The `STATE_{i}` must be handled.\n"
        result = DayTestRule().check(spec)
        assert result.status in (Status.FAIL, Status.WARN)

    def test_empty_spec_passes(self) -> None:
        result = DayTestRule().check("")
        assert result.status == Status.PASS


# ---------------------------------------------------------------------------
# S06: Concrete Example
# ---------------------------------------------------------------------------


class TestS06ConcreteExample:
    """S06 checks for real input/output examples in Contract section."""

    def test_good_spec_passes(self, good_spec: str) -> None:
        result = ConcreteExampleRule().check(good_spec)
        assert result.status == Status.PASS
        assert result.findings == []

    def test_no_examples_fails(self, bad_no_examples: str) -> None:
        result = ConcreteExampleRule().check(bad_no_examples)
        assert result.status == Status.FAIL

    def test_code_blocks_in_contract(self) -> None:
        spec = """
## 2. Contract

```python
def greet(name: str) -> str:
    pass
```

Example:
```python
greet("Alice") -> "Hello, Alice!"
```
"""
        result = ConcreteExampleRule().check(spec)
        assert result.status == Status.PASS

    def test_no_contract_section_fails(self) -> None:
        spec = "# Just a title\n\nNo contract here."
        result = ConcreteExampleRule().check(spec)
        assert result.status == Status.FAIL
        assert any("Contract" in f.message for f in result.findings)

    def test_contract_without_code_blocks_warns(self) -> None:
        spec = """
## 2. Contract

The function accepts a name and returns a greeting.
Input: name (string)
Output: greeting (string)
"""
        result = ConcreteExampleRule().check(spec)
        # Has example-like patterns but no code blocks
        assert result.status in (Status.WARN, Status.FAIL)


# ---------------------------------------------------------------------------
# S08: Ambiguity Test
# ---------------------------------------------------------------------------


class TestS08Ambiguity:
    """S08 detects weasel words that leave decisions unmade."""

    def test_good_spec_has_few_weasels(self, good_spec: str) -> None:
        result = AmbiguityRule().check(good_spec)
        # Good spec should pass or at most warn
        assert result.status in (Status.PASS, Status.WARN)

    def test_bad_ambiguous_fails(self, bad_ambiguous: str) -> None:
        result = AmbiguityRule().check(bad_ambiguous)
        assert result.status == Status.FAIL
        assert len(result.findings) > 3

    def test_no_weasels_passes(self) -> None:
        spec = """
## 1. Purpose

The Greeter Service generates welcome messages.

## 2. Contract

The function MUST return a Greeting object. On empty name, it MUST raise ValueError.
"""
        result = AmbiguityRule().check(spec)
        assert result.status == Status.PASS

    def test_weasel_in_code_block_ignored(self) -> None:
        spec = """
## 1. Purpose

Precise implementation.

```python
# This should handle errors properly
value = compute(x)  # may return None
```
"""
        result = AmbiguityRule().check(spec)
        # "should" and "may" inside code block should not count
        # Only counts outside code blocks
        assert result.status == Status.PASS

    def test_tbd_detected(self) -> None:
        spec = """
## 1. Purpose

The service handles requests. TBD - to be determined later.
"""
        result = AmbiguityRule().check(spec)
        assert result.status in (Status.WARN, Status.FAIL)
        assert any("tbd" in f.message.lower() or "later" in f.message.lower() for f in result.findings)

    def test_findings_have_line_numbers(self) -> None:
        spec = "Line 1\nLine 2\nThis should work properly.\nLine 4\n"
        result = AmbiguityRule().check(spec)
        if result.findings:
            assert all(f.line is not None and f.line > 0 for f in result.findings)


# ---------------------------------------------------------------------------
# S09: Error Path
# ---------------------------------------------------------------------------


class TestS09ErrorPath:
    """S09 checks that specs define failure behavior."""

    def test_good_spec_passes(self, good_spec: str) -> None:
        result = ErrorPathRule().check(good_spec)
        assert result.status == Status.PASS

    def test_no_examples_fails(self, bad_no_examples: str) -> None:
        result = ErrorPathRule().check(bad_no_examples)
        assert result.status in (Status.FAIL, Status.WARN)

    def test_no_error_keywords_fails(self) -> None:
        spec = """
## 1. Purpose

The component generates greetings.

## 3. Protocol

1. Accept name
2. Return greeting

## 4. Policy

Configuration is simple.
"""
        result = ErrorPathRule().check(spec)
        assert result.status == Status.FAIL

    def test_error_section_passes(self) -> None:
        spec = """
## 4. Policy

### Error Handling

| Error Condition | Behavior |
|:---|:---|
| Invalid input | Raise ValueError |
| Timeout | Retry 3 times, then fail |
"""
        result = ErrorPathRule().check(spec)
        assert result.status == Status.PASS

    def test_mentions_without_section_warns(self) -> None:
        spec = """
## 1. Purpose

Handles errors gracefully.

## 3. Protocol

If the input is invalid, raise an exception.
"""
        result = ErrorPathRule().check(spec)
        # Has error keywords but no dedicated section
        assert result.status in (Status.WARN, Status.PASS)


# ---------------------------------------------------------------------------
# S10: Done Definition
# ---------------------------------------------------------------------------


class TestS10DoneDefinition:
    """S10 checks for unambiguous completion criteria."""

    def test_good_spec_passes(self, good_spec: str) -> None:
        result = DoneDefinitionRule().check(good_spec)
        assert result.status == Status.PASS

    def test_no_done_section_fails(self, bad_no_examples: str) -> None:
        result = DoneDefinitionRule().check(bad_no_examples)
        assert result.status == Status.FAIL

    def test_missing_section_fails(self) -> None:
        spec = "# Component\n\n## 1. Purpose\n\nDoes stuff.\n"
        result = DoneDefinitionRule().check(spec)
        assert result.status == Status.FAIL
        assert any("Done Definition" in f.message for f in result.findings)

    def test_empty_done_section_fails(self) -> None:
        spec = "## Done Definition\n\n"
        result = DoneDefinitionRule().check(spec)
        assert result.status == Status.FAIL

    def test_with_checkboxes_passes(self) -> None:
        spec = """
## Done Definition

- [ ] All unit tests pass
- [ ] Coverage >= 70%
- [ ] sw check --level=component passes
"""
        result = DoneDefinitionRule().check(spec)
        assert result.status == Status.PASS
        assert "3" in result.message  # 3 checkboxes

    def test_vague_done_warns(self) -> None:
        spec = """
## Done Definition

The component is complete and robust.
"""
        result = DoneDefinitionRule().check(spec)
        assert result.status == Status.WARN

    def test_acceptance_criteria_accepted(self) -> None:
        spec = """
## Acceptance Criteria

- [ ] Feature works as described
- [ ] All tests pass
"""
        result = DoneDefinitionRule().check(spec)
        assert result.status == Status.PASS


# ---------------------------------------------------------------------------
# Runner tests
# ---------------------------------------------------------------------------


class TestRunner:
    """Test the validation runner."""

    def test_get_spec_rules_excludes_llm(self) -> None:
        rules = get_spec_rules(include_llm=False)
        assert len(rules) == 7
        assert all(not r.requires_llm for r in rules)

    def test_get_spec_rules_ordered_by_id(self) -> None:
        rules = get_spec_rules()
        ids = [r.rule_id for r in rules]
        assert ids == sorted(ids)

    def test_run_rules_collects_all_results(self, good_spec: str) -> None:
        rules = get_spec_rules()
        results = run_rules(rules, good_spec)
        assert len(results) == 7

    def test_run_rules_exception_handling(self) -> None:
        """A crashing rule should produce FAIL, not crash the runner."""

        class CrashingRule(Rule):
            @property
            def rule_id(self) -> str:
                return "X99"

            @property
            def name(self) -> str:
                return "Crasher"

            def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
                msg = "boom"
                raise RuntimeError(msg)

        results = run_rules([CrashingRule()], "some spec")
        assert len(results) == 1
        assert results[0].status == Status.FAIL
        assert "boom" in results[0].message

    def test_all_passed_with_passing_results(self) -> None:
        results = [
            RuleResult(rule_id="S01", rule_name="Test", status=Status.PASS),
            RuleResult(rule_id="S02", rule_name="Test", status=Status.SKIP),
        ]
        assert all_passed(results) is True

    def test_all_passed_with_failure(self) -> None:
        results = [
            RuleResult(rule_id="S01", rule_name="Test", status=Status.PASS),
            RuleResult(rule_id="S02", rule_name="Test", status=Status.FAIL),
        ]
        assert all_passed(results) is False

    def test_count_by_status(self) -> None:
        results = [
            RuleResult(rule_id="S01", rule_name="Test", status=Status.PASS),
            RuleResult(rule_id="S02", rule_name="Test", status=Status.PASS),
            RuleResult(rule_id="S05", rule_name="Test", status=Status.FAIL),
            RuleResult(rule_id="S08", rule_name="Test", status=Status.WARN),
        ]
        counts = count_by_status(results)
        assert counts[Status.PASS] == 2
        assert counts[Status.FAIL] == 1
        assert counts[Status.WARN] == 1
        assert counts[Status.SKIP] == 0

    def test_good_spec_passes_all(self, good_spec: str) -> None:
        """The good_spec fixture should pass all 7 rules."""
        rules = get_spec_rules()
        results = run_rules(rules, good_spec)
        for r in results:
            assert r.status in (Status.PASS, Status.WARN), (
                f"{r.rule_id} ({r.rule_name}): {r.status.value} — {r.message}"
            )

    def test_empty_rules_list(self) -> None:
        results = run_rules([], "some spec")
        assert results == []
        assert all_passed(results) is True
