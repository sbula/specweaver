# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Unit tests for S07 TestFirstRule — Contract section testability scoring."""

from __future__ import annotations

from specweaver.validation.models import Status
from specweaver.validation.rules.spec.s07_test_first import (
    TestFirstRule,
    _analyse_contract,
    _extract_contract,
    _testability_score,
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
        score = _testability_score(has_code=True, assertion_count=10, has_concrete=True, has_io=True)
        assert score == 12  # 3 + 5(cap) + 2 + 2

    def test_zero_score(self) -> None:
        score = _testability_score(has_code=False, assertion_count=0, has_concrete=False, has_io=False)
        assert score == 0

    def test_code_only(self) -> None:
        score = _testability_score(has_code=True, assertion_count=0, has_concrete=False, has_io=False)
        assert score == 3

    def test_assertion_cap_at_5(self) -> None:
        score = _testability_score(has_code=False, assertion_count=100, has_concrete=False, has_io=False)
        assert score == 5  # capped


# ── TestFirstRule.check() ────────────────────────────────────────────────

class TestTestFirstRuleCheck:

    def test_good_contract_passes(self) -> None:
        rule = TestFirstRule()
        result = rule.check(_GOOD_CONTRACT)
        assert result.status == Status.PASS

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
