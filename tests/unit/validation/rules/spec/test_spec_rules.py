# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for validation models, runner, and all 7 static spec rules."""

from __future__ import annotations

from pathlib import Path

import pytest

from specweaver.validation.models import Finding, RuleResult, Severity, Status
from specweaver.validation.rules.spec.s01_one_sentence import OneSentenceRule
from specweaver.validation.rules.spec.s02_single_setup import SingleSetupRule
from specweaver.validation.rules.spec.s05_day_test import DayTestRule
from specweaver.validation.rules.spec.s06_concrete_example import ConcreteExampleRule
from specweaver.validation.rules.spec.s08_ambiguity import AmbiguityRule
from specweaver.validation.rules.spec.s09_error_path import ErrorPathRule
from specweaver.validation.rules.spec.s10_done_definition import DoneDefinitionRule

# ---------------------------------------------------------------------------
# Fixtures — load test spec files
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "fixtures"


@pytest.fixture()
def good_spec() -> str:
    return (FIXTURES_DIR / "good_spec.md").read_text(encoding="utf-8")


@pytest.fixture()
def bad_ambiguous() -> str:
    return (FIXTURES_DIR / "bad_spec_ambiguous.md").read_text(encoding="utf-8")


@pytest.fixture()
def bad_no_examples() -> str:
    return (FIXTURES_DIR / "bad_spec_no_examples.md").read_text(encoding="utf-8")


@pytest.fixture()
def bad_too_big() -> str:
    return (FIXTURES_DIR / "bad_spec_too_big.md").read_text(encoding="utf-8")


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

    def test_empty_spec(self) -> None:
        result = OneSentenceRule().check("")
        assert result.status == Status.WARN

    def test_rule_id(self) -> None:
        assert OneSentenceRule().rule_id == "S01"
        assert OneSentenceRule().name == "One-Sentence Test"

    def test_purpose_without_number(self) -> None:
        """'## Purpose' without '1.' prefix — S01 does NOT match this."""
        spec = "## Purpose\n\nThis does many things and also handles events.\n"
        result = OneSentenceRule().check(spec)
        # Current regex requires '1.' — this is a known gap
        assert result.status == Status.WARN
        assert any("Purpose" in f.message for f in result.findings)


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

    def test_rule_id(self) -> None:
        assert SingleSetupRule().rule_id == "S02"
        assert SingleSetupRule().name == "Single Test Setup"


# ---------------------------------------------------------------------------
# S05: Day Test
# ---------------------------------------------------------------------------


class TestS05DayTest:
    """S05 detects specs too large for one implementation session."""

    def test_good_spec_passes(self, good_spec: str) -> None:
        result = DayTestRule().check(good_spec)
        assert result.status == Status.PASS

    def test_bad_too_big_fixture_not_complex_enough(self, bad_too_big: str) -> None:
        """bad_too_big is only 3.2KB with score ~6.7 — it triggers S01, not S05."""
        result = DayTestRule().check(bad_too_big)
        # This fixture has multiple responsibilities (S01 fails) but is small
        # enough that the Day Test complexity score stays under WARN (25).
        assert result.status == Status.PASS

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

    def test_borderline_complexity_warns(self) -> None:
        """Score between WARN and FAIL thresholds should WARN."""
        # Build a spec that lands between 25 and 40 score.
        # Weights: size*0.30, sections*0.20, branches*0.20,
        #          states*0.15, code_blocks*0.15
        # Use uppercase-only states (regex: `[A-Z][A-Z_]+`)
        states = [
            "ACTIVE",
            "PENDING",
            "WAITING",
            "RUNNING",
            "FAILED",
            "COMPLETED",
            "CANCELLED",
            "PAUSED",
            "TERMINATED",
            "STARTING",
            "STOPPING",
            "IDLE",
            "BLOCKED",
            "READY",
            "PROCESSING",
        ]
        spec = "## 1. Purpose\n\nModerately complex component.\n"
        for i in range(30):
            spec += f"\n### Section {i}\n\n"
            spec += "If condition then handle, when state changes unless.\n"
            state = states[i % len(states)]
            spec += f"Handle `{state}` transitions.\n"
            spec += "```python\ncode_block()\n```\n"
        result = DayTestRule().check(spec)
        assert result.status == Status.WARN
        assert "score" in result.message.lower()

    def test_rule_id(self) -> None:
        assert DayTestRule().rule_id == "S05"
        assert DayTestRule().name == "Day Test"


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

    def test_no_contract_code_but_examples_elsewhere_warns(self) -> None:
        """Contract has no code blocks but spec has code elsewhere."""
        spec = """
## 2. Contract

The function processes data. Example: input -> output.

## 3. Protocol

```python
result = process(data)
```
"""
        result = ConcreteExampleRule().check(spec)
        assert result.status == Status.WARN
        assert any(
            "elsewhere" in f.message.lower() or "code" in f.message.lower() for f in result.findings
        )

    def test_no_code_blocks_and_no_examples_fails(self) -> None:
        """Contract has no code blocks and no example patterns."""
        spec = """
## 2. Contract

The function processes data.

## 3. Protocol

```python
result = process(data)
```
"""
        result = ConcreteExampleRule().check(spec)
        assert result.status == Status.FAIL
        assert "no concrete" in result.message.lower() or "contract" in result.message.lower()

    def test_no_code_blocks_anywhere_fails(self) -> None:
        """Spec has no code blocks at all."""
        spec = """
## 2. Contract

The function processes data.
No code blocks anywhere.
"""
        result = ConcreteExampleRule().check(spec)
        assert result.status == Status.FAIL
        assert "no code blocks" in result.message.lower()

    def test_empty_spec(self) -> None:
        result = ConcreteExampleRule().check("")
        assert result.status == Status.FAIL

    def test_rule_id(self) -> None:
        assert ConcreteExampleRule().rule_id == "S06"
        assert ConcreteExampleRule().name == "Concrete Example"


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
        assert any(
            "tbd" in f.message.lower() or "later" in f.message.lower() for f in result.findings
        )

    def test_findings_have_line_numbers(self) -> None:
        spec = "Line 1\nLine 2\nThis should work properly.\nLine 4\n"
        result = AmbiguityRule().check(spec)
        if result.findings:
            assert all(f.line is not None and f.line > 0 for f in result.findings)

    def test_empty_spec(self) -> None:
        result = AmbiguityRule().check("")
        assert result.status == Status.PASS

    def test_rule_id(self) -> None:
        assert AmbiguityRule().rule_id == "S08"
        assert AmbiguityRule().name == "Ambiguity Test"

    def test_exactly_one_weasel_word(self) -> None:
        """Score at _MAX_WEASEL_WARN boundary (1) should still PASS."""
        spec = "The service should return a value.\n"
        result = AmbiguityRule().check(spec)
        # 1 weasel word ("should") = at threshold = PASS
        assert result.status == Status.PASS


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

    def test_error_keywords_no_policy_no_section_warns(self) -> None:
        """Error keywords exist but no Policy section and no error section."""
        spec = """
## 1. Purpose

Service that handles timeouts and retries on failure.

## 3. Protocol

1. Send request.
2. On timeout, retry.
3. After 3 failures, abort.
"""
        result = ErrorPathRule().check(spec)
        assert result.status == Status.WARN
        assert any(
            "error keywords" in f.message.lower() or "no dedicated" in f.message.lower()
            for f in result.findings
        )

    def test_policy_with_error_keywords_passes(self) -> None:
        """Policy section containing error keywords should pass."""
        spec = """
## 4. Policy

On invalid input, raise ValueError.
On timeout, retry 3 times then abort.
"""
        result = ErrorPathRule().check(spec)
        assert result.status == Status.PASS

    def test_empty_spec(self) -> None:
        result = ErrorPathRule().check("")
        assert result.status == Status.FAIL

    def test_rule_id(self) -> None:
        assert ErrorPathRule().rule_id == "S09"
        assert ErrorPathRule().name == "Error Path"


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

    def test_empty_spec(self) -> None:
        result = DoneDefinitionRule().check("")
        assert result.status == Status.FAIL

    def test_rule_id(self) -> None:
        assert DoneDefinitionRule().rule_id == "S10"
        assert DoneDefinitionRule().name == "Done Definition"

    def test_dod_section_variant(self) -> None:
        """'## DoD' and '## Definition of Done' should both work."""
        spec = """
## DoD

- [ ] All tests pass
"""
        result = DoneDefinitionRule().check(spec)
        assert result.status == Status.PASS
