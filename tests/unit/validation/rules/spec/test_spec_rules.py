# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for validation models, runner, and all 7 static spec rules."""

from __future__ import annotations

from pathlib import Path

import pytest

from specweaver.validation.models import Finding, Rule, RuleResult, Severity, Status
from specweaver.validation.rules.spec.s01_one_sentence import OneSentenceRule
from specweaver.validation.rules.spec.s02_single_setup import SingleSetupRule
from specweaver.validation.rules.spec.s03_stranger import StrangerTestRule
from specweaver.validation.rules.spec.s04_dependency_dir import DependencyDirectionRule
from specweaver.validation.rules.spec.s05_day_test import DayTestRule
from specweaver.validation.rules.spec.s06_concrete_example import ConcreteExampleRule
from specweaver.validation.rules.spec.s07_test_first import TestFirstRule
from specweaver.validation.rules.spec.s08_ambiguity import AmbiguityRule
from specweaver.validation.rules.spec.s09_error_path import ErrorPathRule
from specweaver.validation.rules.spec.s10_done_definition import DoneDefinitionRule
from specweaver.validation.rules.spec.s11_terminology import TerminologyRule
from specweaver.validation.runner import (
    all_passed,
    count_by_status,
    get_spec_rules,
    run_rules,
)

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
            "ACTIVE", "PENDING", "WAITING", "RUNNING", "FAILED",
            "COMPLETED", "CANCELLED", "PAUSED", "TERMINATED", "STARTING",
            "STOPPING", "IDLE", "BLOCKED", "READY", "PROCESSING",
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
        assert any("elsewhere" in f.message.lower() or "code" in f.message.lower() for f in result.findings)

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
        assert any("error keywords" in f.message.lower() or "no dedicated" in f.message.lower() for f in result.findings)

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


# ---------------------------------------------------------------------------
# Runner tests
# ---------------------------------------------------------------------------


class TestRunner:
    """Test the validation runner."""

    def test_get_spec_rules_excludes_llm(self) -> None:
        rules = get_spec_rules(include_llm=False)
        assert len(rules) == 11
        assert all(not r.requires_llm for r in rules)

    def test_get_spec_rules_ordered_by_id(self) -> None:
        rules = get_spec_rules()
        ids = [r.rule_id for r in rules]
        assert ids == sorted(ids)

    def test_run_rules_collects_all_results(self, good_spec: str) -> None:
        rules = get_spec_rules()
        results = run_rules(rules, good_spec)
        assert len(results) == 11

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
        """The good_spec fixture should pass all 10 rules."""
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


# ---------------------------------------------------------------------------
# S03: Stranger Test
# ---------------------------------------------------------------------------


class TestS03StrangerTest:
    """S03 detects specs that are not self-contained."""

    def test_good_spec_passes(self, good_spec: str) -> None:
        result = StrangerTestRule().check(good_spec)
        assert result.status in (Status.PASS, Status.WARN)

    def test_self_contained_passes(self) -> None:
        spec = """
## 1. Purpose

The Greeter Service generates personalized welcome messages.

## 2. Contract

`GreetService` is the main class. It accepts a name and returns a greeting.

```python
def greet(name: str) -> str:
    ...
```
"""
        result = StrangerTestRule().check(spec)
        assert result.status == Status.PASS

    def test_many_external_refs_warns(self) -> None:
        spec = """
## 1. Purpose

This component depends on many others.

See [auth](auth_spec.md) and [session](session_spec.md).
Also see [rate_limit](rate_limit_spec.md).
Also see [cache](cache_spec.md) and [db](db_spec.md).
Also see [queue](queue_spec.md).
"""
        result = StrangerTestRule().check(spec)
        assert result.status in (Status.WARN, Status.FAIL)
        assert len(result.findings) > 3

    def test_many_undefined_terms_warns(self) -> None:
        spec = """
## 1. Purpose

Uses `FlowEngine`, `StateStore`, `TaskQueue`, `ConfigManager`,
`EventBus`, and `MetricsCollector` without explanation.
"""
        result = StrangerTestRule().check(spec)
        assert result.status in (Status.WARN, Status.FAIL)

    def test_defined_terms_not_counted(self) -> None:
        """Terms defined in headers should not count as undefined."""
        spec = """
## 1. Purpose

The `GreetService` is a simple greeting component.

### `GreetService` Interface

```python
class GreetService:
    pass
```
"""
        result = StrangerTestRule().check(spec)
        assert result.status == Status.PASS

    def test_rule_id(self) -> None:
        assert StrangerTestRule().rule_id == "S03"
        assert StrangerTestRule().name == "Stranger Test"

    def test_empty_spec(self) -> None:
        result = StrangerTestRule().check("")
        assert result.status == Status.PASS

    def test_http_urls_excluded(self) -> None:
        """HTTP links should not count as external cross-references."""
        spec = """
## 1. Purpose

See [Python docs](https://docs.python.org) and [RFC 2119](https://tools.ietf.org/html/rfc2119).
"""
        result = StrangerTestRule().check(spec)
        assert result.status == Status.PASS

    def test_anchor_links_excluded(self) -> None:
        """Anchor links within the same doc should not count."""
        spec = """
## 1. Purpose

See [Contract](#contract) and [Protocol](#protocol) below.
"""
        result = StrangerTestRule().check(spec)
        assert result.status == Status.PASS

    def test_terms_inside_code_blocks_ignored(self) -> None:
        """Backtick terms inside fenced code should not count as undefined."""
        spec = """
## 1. Purpose

Simple greeter.

```python
# These should not trigger warnings
from myapp import FlowEngine, StateStore, TaskQueue
result = ConfigManager.get()
```
"""
        result = StrangerTestRule().check(spec)
        assert result.status == Status.PASS


# ---------------------------------------------------------------------------
# S04: Dependency Direction
# ---------------------------------------------------------------------------


class TestS04DependencyDirection:
    """S04 detects specs with too many cross-references to peers."""

    def test_good_spec_passes(self, good_spec: str) -> None:
        result = DependencyDirectionRule().check(good_spec)
        assert result.status in (Status.PASS, Status.WARN)

    def test_no_cross_refs_passes(self) -> None:
        spec = """
## 1. Purpose

A simple standalone component.

## 2. Contract

Takes input, produces output.
"""
        result = DependencyDirectionRule().check(spec)
        assert result.status == Status.PASS
        assert "0" in result.message

    def test_many_links_warns(self) -> None:
        spec = """
## 3. Protocol

See [auth](auth_spec.md) for details.
See [session](session_spec.md) for state.
See [cache](cache_spec.md) for caching.
See [queue](queue_spec.md) for async.
See [db](db_spec.md) for storage.
See [metrics](metrics_spec.md) for monitoring.
"""
        result = DependencyDirectionRule().check(spec)
        assert result.status in (Status.WARN, Status.FAIL)
        assert len(result.findings) >= 6

    def test_component_refs_detected(self) -> None:
        spec = """
Communicates with `AuthService`, `CacheManager`, `TaskHandler`,
`EventBus`, `MetricsProvider`, `ConfigAdapter`,
`SessionStore`, `QueueClient`, and `LogHandler`.
"""
        result = DependencyDirectionRule().check(spec)
        # 8 component suffixes matched (EventBus excluded — "Bus" not in suffix list)
        assert result.status in (Status.WARN, Status.FAIL)
        assert any("Component reference" in f.message for f in result.findings)

    def test_code_block_refs_ignored(self) -> None:
        """References inside code blocks should not count."""
        spec = """
## 1. Purpose

Simple service.

```python
from auth import AuthService  # this should be ignored
class MyHandler:
    pass
```
"""
        result = DependencyDirectionRule().check(spec)
        assert result.status == Status.PASS

    def test_rule_id(self) -> None:
        assert DependencyDirectionRule().rule_id == "S04"
        assert DependencyDirectionRule().name == "Dependency Direction"

    def test_empty_spec(self) -> None:
        result = DependencyDirectionRule().check("")
        assert result.status == Status.PASS

    def test_section_refs_detected(self) -> None:
        """'see §3' patterns should be counted."""
        spec = """
See §1 for purpose.
See §2 for contract.
See §3 for protocol.
See §4 for policy.
See §5 for boundaries.
See section 6 for extras.
"""
        result = DependencyDirectionRule().check(spec)
        assert result.status in (Status.WARN, Status.FAIL)
        assert any("Section reference" in f.message for f in result.findings)

    def test_non_md_links_ignored(self) -> None:
        """Links to non-.md files should not count as cross-references."""
        spec = """
See [config](config.yaml) and [script](deploy.sh) for details.
"""
        result = DependencyDirectionRule().check(spec)
        # These are not .md links — should not be counted
        assert result.status == Status.PASS

    def test_findings_have_line_numbers(self) -> None:
        """Line numbers must be populated when threshold triggers findings."""
        spec = (
            "Line 1\n"
            "See [a](a_spec.md) link.\n"             # line 2
            "See [b](b_spec.md) link.\n"             # line 3
            "See [c](c_spec.md) link.\n"             # line 4
            "See [d](d_spec.md) link.\n"             # line 5
            "See [e](e_spec.md) link.\n"             # line 6
            "See [target](target_spec.md) link.\n"   # line 7
        )
        result = DependencyDirectionRule().check(spec)
        assert result.status in (Status.WARN, Status.FAIL)
        target_findings = [f for f in result.findings if "target_spec.md" in f.message]
        assert len(target_findings) == 1
        assert target_findings[0].line == 7


# ---------------------------------------------------------------------------
# S07: Test-First
# ---------------------------------------------------------------------------


class TestS07TestFirst:
    """S07 checks that the Contract section is testable."""

    def test_good_spec_passes(self, good_spec: str) -> None:
        result = TestFirstRule().check(good_spec)
        assert result.status in (Status.PASS, Status.WARN)

    def test_rich_contract_passes(self) -> None:
        spec = """
## 2. Contract

The `greet` function MUST return a `Greeting` object.
If the name is empty, it MUST raise `ValueError`.

```python
def greet(name: str) -> Greeting:
    ...
```

Example:
  Input: name = "Alice"
  Output: Greeting(message="Hello, Alice!")
"""
        result = TestFirstRule().check(spec)
        assert result.status == Status.PASS
        assert "12" in result.message or "score" in result.message.lower()

    def test_no_contract_fails(self) -> None:
        spec = "# Just a title\n\nNo contract here."
        result = TestFirstRule().check(spec)
        assert result.status == Status.FAIL
        assert any("Contract" in f.message for f in result.findings)

    def test_vague_contract_warns_or_fails(self) -> None:
        spec = """
## 2. Contract

The component does stuff.
"""
        result = TestFirstRule().check(spec)
        assert result.status in (Status.WARN, Status.FAIL)
        assert any("testable" in f.message.lower() or "code" in f.message.lower()
                    for f in result.findings)

    def test_contract_with_code_but_no_assertions_warns(self) -> None:
        spec = """
## 2. Contract

```python
class Greeter:
    pass
```
"""
        result = TestFirstRule().check(spec)
        # Has code but no assertions — should warn
        assert result.status in (Status.WARN, Status.PASS)

    def test_rule_id(self) -> None:
        assert TestFirstRule().rule_id == "S07"
        assert TestFirstRule().name == "Test-First"

    def test_empty_spec(self) -> None:
        result = TestFirstRule().check("")
        assert result.status == Status.FAIL

    def test_contract_header_without_number(self) -> None:
        """'## Contract' (no '2.') should still be detected."""
        spec = """
## Contract

The function MUST return a string.

```python
def greet(name: str) -> str:
    ...
```
"""
        result = TestFirstRule().check(spec)
        assert result.status in (Status.PASS, Status.WARN)

    def test_contract_as_last_section(self) -> None:
        """Contract at end of doc (no following ## header) should be extracted."""
        spec = """
## 1. Purpose

A greeter.

## 2. Contract

The `greet` function MUST return a greeting string.
It MUST raise `ValueError` for empty input.

```python
def greet(name: str) -> str:
    ...
```
"""
        result = TestFirstRule().check(spec)
        assert result.status in (Status.PASS, Status.WARN)

    def test_score_at_exact_fail_boundary(self) -> None:
        """Score 0-2 should FAIL — no code, no assertions, no values."""
        spec = """
## 2. Contract

The component handles things appropriately.
It does what is expected.
"""
        result = TestFirstRule().check(spec)
        assert result.status == Status.FAIL
        assert "low testability" in result.message.lower()


# ---------------------------------------------------------------------------
# S11: Terminology Consistency
# ---------------------------------------------------------------------------


class TestS11Terminology:
    """S11 detects inconsistent and undefined terminology in specs."""

    def test_good_spec_passes(self, good_spec: str) -> None:
        result = TerminologyRule().check(good_spec)
        assert result.status in (Status.PASS, Status.WARN)

    def test_rule_id(self) -> None:
        assert TerminologyRule().rule_id == "S11"
        assert TerminologyRule().name == "Terminology Consistency"

    def test_consistent_terms_passes(self) -> None:
        spec = """
## 1. Purpose

The `GreetService` generates personalized greetings.

## 2. Contract

```python
class GreetService:
    def greet(self, name: str) -> str:
        ...
```
"""
        result = TerminologyRule().check(spec)
        assert result.status == Status.PASS

    def test_inconsistent_casing_warns(self) -> None:
        """Same concept with different casing styles should trigger findings."""
        spec = """
## 1. Purpose

The `userId` field identifies the user. The `user_id` is stored in the
database. The `UserID` is sent in the header.
"""
        result = TerminologyRule().check(spec)
        assert result.status in (Status.WARN, Status.FAIL)
        assert any("inconsistent" in f.message.lower() for f in result.findings)

    def test_many_inconsistencies_fails(self) -> None:
        """3+ inconsistent term groups should FAIL."""
        spec = """
The `userId` and `user_id` identify the user.
The `sessionToken` and `session_token` are used for auth.
The `requestId` and `request_id` track requests.
"""
        result = TerminologyRule().check(spec)
        assert result.status == Status.FAIL
        assert len(result.findings) >= 3

    def test_undefined_domain_terms_warns(self) -> None:
        """PascalCase terms in backticks not defined in headers or code should warn."""
        spec = """
## 1. Purpose

This component uses `FlowEngine` and `StateManager` to process data.
"""
        result = TerminologyRule().check(spec)
        assert result.status in (Status.WARN, Status.FAIL)
        assert any("undefined" in f.message.lower() or "not defined" in f.message.lower()
                   for f in result.findings)

    def test_defined_terms_not_flagged(self) -> None:
        """Terms defined in headers or code blocks should not be flagged."""
        spec = """
## 1. Purpose

The `GreetService` generates greetings.

### `GreetService` Interface

```python
class GreetService:
    pass
```
"""
        result = TerminologyRule().check(spec)
        assert result.status == Status.PASS
        assert not any("GreetService" in f.message for f in result.findings)

    def test_terms_in_code_blocks_counted_as_defined(self) -> None:
        """Terms appearing inside code blocks count as definitions."""
        spec = """
## 1. Purpose

Uses `ConfigManager` for configuration.

```python
class ConfigManager:
    def get(self) -> dict:
        ...
```
"""
        result = TerminologyRule().check(spec)
        assert result.status == Status.PASS

    def test_empty_spec_passes(self) -> None:
        result = TerminologyRule().check("")
        assert result.status == Status.PASS

    def test_findings_have_line_numbers(self) -> None:
        spec = "Line 1\nThe `userId` is here.\nThe `user_id` is there.\nLine 4\n"
        result = TerminologyRule().check(spec)
        if result.findings:
            assert all(f.line is not None and f.line > 0 for f in result.findings)

    def test_snake_case_variants_detected(self) -> None:
        """user_name vs userName should be detected as inconsistent."""
        spec = """
The `userName` field stores the user's name.
Later, the `user_name` field is validated.
"""
        result = TerminologyRule().check(spec)
        assert result.status in (Status.WARN, Status.FAIL)

    def test_single_inconsistency_warns(self) -> None:
        """One inconsistent group should WARN, not FAIL."""
        spec = "The `userId` and `user_id` track the user.\n"
        result = TerminologyRule().check(spec)
        assert result.status == Status.WARN


# ---------------------------------------------------------------------------
# S04: Traceability Extension (Dead Link Detection)
# ---------------------------------------------------------------------------


class TestS04DeadLinks:
    """S04 extension: dead link detection when spec_path is provided."""

    def test_existing_link_no_warning(self, tmp_path: Path) -> None:
        """A link to an existing file should not produce a dead-link finding."""
        target = tmp_path / "auth_spec.md"
        target.write_text("# Auth Spec", encoding="utf-8")
        spec_file = tmp_path / "my_spec.md"
        spec_text = "See [auth](auth_spec.md) for details.\n"
        spec_file.write_text(spec_text, encoding="utf-8")

        result = DependencyDirectionRule().check(spec_text, spec_path=spec_file)
        dead_link_findings = [f for f in result.findings if "dead link" in f.message.lower()
                              or "not found" in f.message.lower()]
        assert len(dead_link_findings) == 0

    def test_missing_link_warns(self, tmp_path: Path) -> None:
        """A link to a non-existent file should produce a dead-link warning."""
        spec_file = tmp_path / "my_spec.md"
        spec_text = "See [missing](missing_spec.md) for details.\n"
        spec_file.write_text(spec_text, encoding="utf-8")

        result = DependencyDirectionRule().check(spec_text, spec_path=spec_file)
        dead_link_findings = [f for f in result.findings if "dead link" in f.message.lower()
                              or "not found" in f.message.lower()]
        assert len(dead_link_findings) == 1
        assert dead_link_findings[0].severity == Severity.WARNING

    def test_no_path_skips_link_check(self) -> None:
        """Without spec_path, dead link checking should be skipped."""
        spec_text = "See [missing](missing_spec.md) for details.\n"
        result = DependencyDirectionRule().check(spec_text, spec_path=None)
        dead_link_findings = [f for f in result.findings if "dead link" in f.message.lower()
                              or "not found" in f.message.lower()]
        assert len(dead_link_findings) == 0

    def test_multiple_dead_links(self, tmp_path: Path) -> None:
        """Multiple dead links should each produce a finding."""
        spec_file = tmp_path / "my_spec.md"
        spec_text = (
            "See [a](a_spec.md) for details.\n"
            "See [b](b_spec.md) for details.\n"
            "See [c](c_spec.md) for details.\n"
        )
        spec_file.write_text(spec_text, encoding="utf-8")

        result = DependencyDirectionRule().check(spec_text, spec_path=spec_file)
        dead_link_findings = [f for f in result.findings if "dead link" in f.message.lower()
                              or "not found" in f.message.lower()]
        assert len(dead_link_findings) == 3

    def test_mixed_existing_and_dead_links(self, tmp_path: Path) -> None:
        """Only non-existent links should produce dead-link findings."""
        (tmp_path / "auth_spec.md").write_text("# Auth", encoding="utf-8")
        spec_file = tmp_path / "my_spec.md"
        spec_text = (
            "See [auth](auth_spec.md) for auth.\n"
            "See [missing](missing_spec.md) for missing.\n"
        )
        spec_file.write_text(spec_text, encoding="utf-8")

        result = DependencyDirectionRule().check(spec_text, spec_path=spec_file)
        dead_link_findings = [f for f in result.findings if "dead link" in f.message.lower()
                              or "not found" in f.message.lower()]
        assert len(dead_link_findings) == 1
        assert "missing_spec.md" in dead_link_findings[0].message
