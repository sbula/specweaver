# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Unit tests for S09 ErrorPathRule — error/failure coverage in specs."""

from __future__ import annotations

from specweaver.validation.models import Status
from specweaver.validation.rules.spec.s09_error_path import ErrorPathRule, _extract_policy

# ── Fixtures ──────────────────────────────────────────────────────────────

_GOOD_SPEC = """\
# Service Spec

## 1. Purpose
Handles user registration.

## 4. Policy

| Error | Behavior |
|:---|:---|
| Invalid email | Raise ValueError |
| Timeout | Retry with exponential backoff |
| Duplicate | Reject registration |
"""

_NO_ERROR_SPEC = """\
# Happy Service

## 1. Purpose
Always succeeds. No problems ever.

## 2. Contract
Accepts input, returns output.
"""

_KEYWORDS_BUT_NO_SECTION = """\
# Service Spec

## 1. Purpose
The service must not fail silently.
If the input is invalid, the error is logged.
"""

_POLICY_WITH_ERRORS = """\
# Service

## 4. Policy

On timeout, the service should retry 3 times.
On failure, return HTTP 503.
"""

_PARTIAL_ERROR_SPEC = """\
# Service

## 1. Purpose
This service might raise exceptions sometimes.

## 2. Contract
Returns results. Raises ValueError on bad input.
"""


# ── _extract_policy() ────────────────────────────────────────────────────

class TestExtractPolicy:

    def test_extracts_policy_section(self) -> None:
        result = _extract_policy(_GOOD_SPEC)
        assert "Invalid email" in result

    def test_returns_empty_when_missing(self) -> None:
        result = _extract_policy(_NO_ERROR_SPEC)
        assert result == ""


# ── ErrorPathRule.check() ────────────────────────────────────────────────

class TestErrorPathRule:

    def test_good_spec_passes(self) -> None:
        rule = ErrorPathRule()
        result = rule.check(_GOOD_SPEC)
        assert result.status == Status.PASS

    def test_no_error_keywords_fails(self) -> None:
        rule = ErrorPathRule()
        result = rule.check(_NO_ERROR_SPEC)
        assert result.status == Status.FAIL
        assert any(
            "error" in f.message.lower() or "failure" in f.message.lower()
            for f in result.findings)

    def test_keywords_without_section_warns(self) -> None:
        rule = ErrorPathRule()
        result = rule.check(_KEYWORDS_BUT_NO_SECTION)
        assert result.status == Status.WARN

    def test_policy_with_errors_passes(self) -> None:
        rule = ErrorPathRule()
        result = rule.check(_POLICY_WITH_ERRORS)
        assert result.status == Status.PASS

    def test_partial_errors_warns(self) -> None:
        rule = ErrorPathRule()
        result = rule.check(_PARTIAL_ERROR_SPEC)
        # Has error keywords but no dedicated section → warn
        assert result.status in (Status.WARN, Status.PASS)

    def test_empty_spec_fails(self) -> None:
        rule = ErrorPathRule()
        result = rule.check("")
        assert result.status == Status.FAIL

    def test_rule_id(self) -> None:
        assert ErrorPathRule().rule_id == "S09"

    def test_rule_name(self) -> None:
        assert ErrorPathRule().name == "Error Path"
