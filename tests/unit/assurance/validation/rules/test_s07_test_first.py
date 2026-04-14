# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for S07 TestFirstRule — Contract section testability scoring."""

from __future__ import annotations

from specweaver.assurance.validation.models import Severity, Status
from specweaver.assurance.validation.rules.spec.s07_test_first import (
    TestFirstRule,
    _analyse_contract,
    _extract_contract,
    _extract_scenarios,
    _testability_score,
    _validate_scenario_item,
    _validate_scenario_yaml,
)

# ── Fixtures ──────────────────────────────────────────────────────────────

_GOOD_CONTRACT = """\
## 2. Contract

### Interface

```python
def greet(name: str) -> str:
    \"\"\"Return a greeting for the given name.\"\"\"
```

### Examples

```python
>>> greet("Alice")
"Hello, Alice!"
>>> greet("")
"Hello, World!"
```

Input: name — a non-empty string.
Output: greeting string.
The function MUST return a string starting with "Hello".
"""

_NO_CODE_CONTRACT = """\
## 2. Contract

The service accepts a name and returns a greeting.
It SHOULD handle empty names gracefully.
"""

_EMPTY_CONTRACT = """\
## 2. Contract

"""

_NO_CONTRACT_SPEC = """\
## 1. Purpose

A simple greeter service.
"""


# ── _extract_contract() ──────────────────────────────────────────────────


class TestExtractContract:
    def test_extracts_numbered_header(self) -> None:
        result = _extract_contract(_GOOD_CONTRACT)
        assert result is not None
        assert "greet" in result

    def test_extracts_unnumbered_header(self) -> None:
        spec = "## Contract\n\nSome content here.\n\n## 3. Protocol\n"
        result = _extract_contract(spec)
        assert result is not None
        assert "Some content" in result

    def test_returns_none_when_missing(self) -> None:
        assert _extract_contract(_NO_CONTRACT_SPEC) is None

    def test_stops_at_next_section(self) -> None:
        spec = "## 2. Contract\n\nContent\n\n## 3. Protocol\n\nProto stuff\n"
        result = _extract_contract(spec)
        assert result is not None
        assert "Proto stuff" not in result

    def test_end_of_file_contract(self) -> None:
        spec = "## 2. Contract\n\nLast section content."
        result = _extract_contract(spec)
        assert result is not None
        assert "Last section" in result


# ── _analyse_contract() ─────────────────────────────────────────────────


class TestAnalyseContract:
    def test_detects_code_blocks(self) -> None:
        contract = "```python\ndef f(): pass\n```\nSome text.\n"
        has_code, _, _, _ = _analyse_contract(contract)
        assert has_code

    def test_no_code_blocks(self) -> None:
        has_code, _, _, _ = _analyse_contract("Just plain text.\n")
        assert not has_code

    def test_counts_assertions(self) -> None:
        contract = "The function MUST return a string. It SHALL NOT raise."
        _, count, _, _ = _analyse_contract(contract)
        assert count >= 2  # MUST + SHALL NOT

    def test_detects_concrete_values(self) -> None:
        contract = 'Returns "Hello" or the number 42.'
        _, _, has_concrete, _ = _analyse_contract(contract)
        assert has_concrete

    def test_no_concrete_values(self) -> None:
        contract = "Returns a greeting string."
        _, _, has_concrete, _ = _analyse_contract(contract)
        assert not has_concrete

    def test_detects_io_labels(self) -> None:
        contract = "Input: name string.\nOutput: greeting.\n"
        _, _, _, has_io = _analyse_contract(contract)
        assert has_io

    def test_no_io_labels(self) -> None:
        contract = "A function that does stuff."
        _, _, _, has_io = _analyse_contract(contract)
        assert not has_io


# ── _testability_score() ─────────────────────────────────────────────────


class TestTestabilityScore:
    def test_max_score(self) -> None:
        score = _testability_score(
            has_code=True, assertion_count=10, has_concrete=True, has_io=True
        )
        assert score == 12  # 3 + 5(cap) + 2 + 2

    def test_zero_score(self) -> None:
        score = _testability_score(
            has_code=False, assertion_count=0, has_concrete=False, has_io=False
        )
        assert score == 0

    def test_code_only(self) -> None:
        score = _testability_score(
            has_code=True, assertion_count=0, has_concrete=False, has_io=False
        )
        assert score == 3

    def test_assertion_cap_at_5(self) -> None:
        score = _testability_score(
            has_code=False, assertion_count=100, has_concrete=False, has_io=False
        )
        assert score == 5  # capped


# ── TestFirstRule.check() ────────────────────────────────────────────────


class TestTestFirstRuleCheck:
    def test_good_contract_passes(self) -> None:
        # _GOOD_CONTRACT has no ## Scenarios section, so S07 now warns (3.28 SF-A).
        # This is backward-compatible — WARN is not FAIL (NFR-7).
        rule = TestFirstRule()
        result = rule.check(_GOOD_CONTRACT)
        assert result.status == Status.WARN

    def test_no_contract_fails(self) -> None:
        rule = TestFirstRule()
        result = rule.check(_NO_CONTRACT_SPEC)
        assert result.status != Status.PASS
        assert any("Contract" in f.message for f in result.findings)

    def test_no_code_contract_warns_or_fails(self) -> None:
        rule = TestFirstRule()
        result = rule.check(_NO_CODE_CONTRACT)
        # Should warn or fail — not pass cleanly
        assert result.status != Status.PASS or result.status == Status.WARN

    def test_empty_contract_warns(self) -> None:
        rule = TestFirstRule()
        result = rule.check(_EMPTY_CONTRACT)
        # Empty contract should fail (very low score)
        assert result.status != Status.PASS

    def test_custom_thresholds(self) -> None:
        rule = TestFirstRule(warn_score=1, fail_score=0)
        result = rule.check(_NO_CODE_CONTRACT)
        # With very low thresholds, even a weak contract may pass
        assert result.status == Status.PASS or result.status == Status.WARN


# ── _extract_scenarios() ─────────────────────────────────────────────────


class TestScenarioExtraction:
    def test_extracts_numbered_header(self) -> None:
        spec = "## 3. Scenarios\n\nscenario content here\n\n## 4. Done\n"
        result = _extract_scenarios(spec)
        assert result is not None
        assert "scenario content" in result

    def test_extracts_unnumbered_header(self) -> None:
        spec = "## Scenarios\n\nscenario content\n\n## Done\n"
        result = _extract_scenarios(spec)
        assert result is not None
        assert "scenario content" in result

    def test_returns_none_when_missing(self) -> None:
        spec = "## 1. Purpose\n\nA simple service.\n"
        assert _extract_scenarios(spec) is None

    def test_stops_at_next_section(self) -> None:
        spec = "## 3. Scenarios\n\nscenario stuff\n\n## 4. Protocol\n\nproto stuff\n"
        result = _extract_scenarios(spec)
        assert result is not None
        assert "proto stuff" not in result

    def test_end_of_file_scenarios(self) -> None:
        spec = "## 3. Scenarios\n\nLast section content."
        result = _extract_scenarios(spec)
        assert result is not None
        assert "Last section" in result


# ── _validate_scenario_yaml() + _validate_scenario_item() ────────────────


class TestScenarioYamlValidation:
    def test_valid_yaml_list(self) -> None:
        text = '\n```yaml\n- name: "test"\n  function_under_test: "foo"\n  input_summary: "bar"\n  expected_behavior: "baz"\n```\n'
        findings = _validate_scenario_yaml(text)
        assert len(findings) == 0

    def test_valid_yaml_mapping(self) -> None:
        text = '\n```yaml\nname: "test"\nfunction_under_test: "foo"\ninput_summary: "bar"\nexpected_behavior: "baz"\n```\n'
        findings = _validate_scenario_yaml(text)
        assert len(findings) == 0

    def test_invalid_yaml_syntax(self) -> None:
        text = "\n```yaml\n- name: [invalid\n```\n"
        findings = _validate_scenario_yaml(text)
        assert len(findings) == 1
        assert "Invalid YAML" in findings[0].message

    def test_no_yaml_code_blocks(self) -> None:
        text = "\nJust some text, no code blocks\n"
        findings = _validate_scenario_yaml(text)
        assert len(findings) == 1
        assert "no YAML code blocks" in findings[0].message

    def test_non_collection_yaml(self) -> None:
        text = "\n```yaml\njust a scalar string\n```\n"
        findings = _validate_scenario_yaml(text)
        assert len(findings) == 1
        assert "list or mapping" in findings[0].message

    def test_missing_required_keys(self) -> None:
        text = '\n```yaml\n- name: "test"\n```\n'
        findings = _validate_scenario_yaml(text)
        assert len(findings) == 1
        assert "missing required keys" in findings[0].message
        assert findings[0].severity == Severity.ERROR

    def test_all_required_keys_present(self) -> None:
        item = {
            "name": "test",
            "function_under_test": "foo",
            "input_summary": "bar",
            "expected_behavior": "baz",
        }
        findings = _validate_scenario_item(item, 0)
        assert len(findings) == 0

    def test_invalid_category_warns(self) -> None:
        item = {
            "name": "test",
            "function_under_test": "foo",
            "input_summary": "bar",
            "expected_behavior": "baz",
            "category": "invalid",
        }
        findings = _validate_scenario_item(item, 0)
        assert len(findings) == 1
        assert findings[0].severity == Severity.WARNING

    def test_valid_categories_pass(self) -> None:
        for cat in ("happy", "error", "boundary"):
            item = {
                "name": "test",
                "function_under_test": "foo",
                "input_summary": "bar",
                "expected_behavior": "baz",
                "category": cat,
            }
            findings = _validate_scenario_item(item, 0)
            assert len(findings) == 0, f"category '{cat}' should pass"


# ── Scenario Integration with check() ───────────────────────────────────

_GOOD_SPEC_WITH_SCENARIOS = (
    _GOOD_CONTRACT
    + """
## 3. Scenarios

```yaml
- name: "happy_greet"
  function_under_test: "greet"
  input_summary: "valid name"
  expected_behavior: "returns greeting"
  category: "happy"
```
"""
)

_GOOD_SPEC_WITH_BAD_SCENARIOS = (
    _GOOD_CONTRACT
    + """
## 3. Scenarios

```yaml
- name: [invalid yaml
```
"""
)


class TestScenarioIntegration:
    def test_good_spec_with_scenarios_passes(self) -> None:
        rule = TestFirstRule()
        result = rule.check(_GOOD_SPEC_WITH_SCENARIOS)
        assert result.status == Status.PASS

    def test_good_spec_without_scenarios_warns(self) -> None:
        rule = TestFirstRule()
        result = rule.check(_GOOD_CONTRACT)
        # Should still warn (not fail) because scenarios are missing
        assert result.status == Status.WARN
        assert any("Scenarios" in f.message for f in result.findings)

    def test_good_spec_with_malformed_scenarios_warns(self) -> None:
        rule = TestFirstRule()
        result = rule.check(_GOOD_SPEC_WITH_BAD_SCENARIOS)
        assert result.status == Status.WARN
        assert any("Invalid YAML" in f.message for f in result.findings)

    def test_existing_spec_fixture_backward_compat(self) -> None:
        """Existing _GOOD_CONTRACT fixture must still not FAIL S07 (NFR-7)."""
        rule = TestFirstRule()
        result = rule.check(_GOOD_CONTRACT)
        assert result.status != Status.FAIL
