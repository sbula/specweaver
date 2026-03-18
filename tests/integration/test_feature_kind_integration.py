# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Integration tests — SpecKind ↔ Rules ↔ Runner cross-component.

These tests verify that the kind-aware preset system (C1) correctly
modifies rule behaviour (C2) when threaded through the runner (C3).
No mocking — exercises the real preset → rule constructor → check path.
"""

from __future__ import annotations

import pytest

from specweaver.validation.models import Status
from specweaver.validation.runner import get_spec_rules, run_rules
from specweaver.validation.spec_kind import SpecKind


# ---------------------------------------------------------------------------
# Fixture specs
# ---------------------------------------------------------------------------

_FEATURE_SPEC = """\
# User Onboarding — Feature Spec

> **Status**: DRAFT

---

## Intent

The system enables new users to register, verify their email, and complete
their profile in a single guided flow.

---

## Value Proposition

Users can onboard in under 2 minutes.

---

## Acceptance Criteria

- User can register with email
- Email verification is sent within 30 seconds
- Profile completion wizard has 3 steps

---

## Done Definition

- [ ] All acceptance criteria pass
- [ ] sw check --level=feature passes
"""

_COMPONENT_SPEC = """\
# Greeter Service — Component Spec

> **Status**: DRAFT

---

## 1. Purpose

The Greeter Service generates personalized welcome messages for new users.

---

## 2. Contract

```python
def greet(name: str) -> str:
    return f"Hello {name}"
```

---

## 3. Protocol

1. Validate name is not empty.
2. Return greeting.

---

## 4. Policy

| Error | Behavior |
|:---|:---|
| Empty name | Raise ValueError |

---

## 5. Boundaries

| Concern | Owned By |
|:---|:---|
| Auth | AuthService |

---

## Done Definition

- [ ] Unit tests pass
- [ ] Coverage >= 70%
"""

_FEATURE_WITH_LEAKS = """\
# Payment Processing — Feature Spec

> **Status**: DRAFT

---

## Intent

The system processes payments.

---

## Implementation Details

Use `TaxCalculator.calculate()` for tax computation.
See [gateway](src/payments/gateway.py) for the payment gateway.
See [invoices](src/billing/invoices/gen.py) for invoice generation.
The module `specweaver.billing.tax_engine` handles all tax logic.
"""

_FEATURE_SPEC_MANY_CONJUNCTIONS = """\
# Mega Feature — Feature Spec

---

## Intent

The system enables user registration and also handles payment processing
additionally it manages notification delivery as well as audit logging
furthermore it provides reporting capabilities along with backup scheduling
in addition to data export functionality on top of that it runs analytics.

---

## Done Definition

- [ ] All features work
"""


# ---------------------------------------------------------------------------
# C1 ↔ C2 ↔ C3: Runner threads kind through to rules
# ---------------------------------------------------------------------------


class TestRunnerKindIntegration:
    """Runner + presets + rules integration (no mocking)."""

    def test_feature_kind_uses_intent_header(self) -> None:
        """S01 with kind=FEATURE uses ## Intent header, not ## 1. Purpose."""
        rules = get_spec_rules(include_llm=False, kind=SpecKind.FEATURE)
        results = run_rules(rules, _FEATURE_SPEC)

        s01 = next(r for r in results if r.rule_id == "S01")
        # Feature spec has ## Intent — S01 should find it and PASS (no conjunctions)
        assert s01.status == Status.PASS, f"S01 should pass on clean feature spec: {s01.message}"

    def test_component_kind_uses_purpose_header(self) -> None:
        """S01 with kind=COMPONENT uses ## 1. Purpose header."""
        rules = get_spec_rules(include_llm=False, kind=SpecKind.COMPONENT)
        results = run_rules(rules, _COMPONENT_SPEC)

        s01 = next(r for r in results if r.rule_id == "S01")
        assert s01.status == Status.PASS, f"S01 should pass on clean component spec: {s01.message}"

    def test_feature_kind_skips_s04(self) -> None:
        """S04 is SKIPPED for kind=FEATURE (dependency direction N/A for features)."""
        rules = get_spec_rules(include_llm=False, kind=SpecKind.FEATURE)
        results = run_rules(rules, _FEATURE_SPEC)

        s04 = next(r for r in results if r.rule_id == "S04")
        assert s04.status == Status.SKIP, f"S04 should be SKIP for feature kind: {s04.message}"

    def test_component_kind_does_not_skip_s04(self) -> None:
        """S04 runs normally for kind=COMPONENT."""
        rules = get_spec_rules(include_llm=False, kind=SpecKind.COMPONENT)
        results = run_rules(rules, _COMPONENT_SPEC)

        s04 = next(r for r in results if r.rule_id == "S04")
        assert s04.status != Status.SKIP, f"S04 should not be SKIP for component kind"

    def test_feature_kind_enables_s03_abstraction_leak_mode(self) -> None:
        """S03 with kind=FEATURE detects abstraction leaks (file paths, method refs)."""
        rules = get_spec_rules(include_llm=False, kind=SpecKind.FEATURE)
        results = run_rules(rules, _FEATURE_WITH_LEAKS)

        s03 = next(r for r in results if r.rule_id == "S03")
        assert s03.status in (Status.WARN, Status.FAIL), (
            f"S03 should detect abstraction leaks: {s03.message}"
        )
        # Should have specific leak findings
        assert len(s03.findings) > 0
        assert any("leak" in f.message.lower() or "path" in f.message.lower()
                    for f in s03.findings)

    def test_same_spec_different_results_by_kind(self) -> None:
        """Same spec produces different results for FEATURE vs COMPONENT."""
        feature_rules = get_spec_rules(include_llm=False, kind=SpecKind.FEATURE)
        component_rules = get_spec_rules(include_llm=False, kind=SpecKind.COMPONENT)

        feature_results = run_rules(feature_rules, _FEATURE_SPEC)
        component_results = run_rules(component_rules, _FEATURE_SPEC)

        # S04 should differ: SKIP for feature, not SKIP for component
        f_s04 = next(r for r in feature_results if r.rule_id == "S04")
        c_s04 = next(r for r in component_results if r.rule_id == "S04")
        assert f_s04.status == Status.SKIP
        assert c_s04.status != Status.SKIP

        # S01 should differ: feature finds ## Intent, component doesn't
        f_s01 = next(r for r in feature_results if r.rule_id == "S01")
        c_s01 = next(r for r in component_results if r.rule_id == "S01")
        # Feature spec has ## Intent → S01 PASS; component looks for ## 1. Purpose → WARN
        assert f_s01.status == Status.PASS
        assert c_s01.status == Status.WARN  # Can't find ## 1. Purpose

    def test_feature_conjunctions_fail_threshold(self) -> None:
        """Feature spec with many conjunctions in Intent → S01 FAIL."""
        rules = get_spec_rules(include_llm=False, kind=SpecKind.FEATURE)
        results = run_rules(rules, _FEATURE_SPEC_MANY_CONJUNCTIONS)

        s01 = next(r for r in results if r.rule_id == "S01")
        assert s01.status == Status.FAIL, f"S01 should fail on many conjunctions: {s01.message}"
        assert len(s01.findings) > 0


class TestRunnerSettingsOverrideIntegration:
    """Settings overrides correctly layer on top of kind presets."""

    def test_settings_override_beats_preset(self) -> None:
        """Settings warn_threshold overrides kind preset for S05."""
        from specweaver.config.settings import RuleOverride, ValidationSettings

        # Feature preset for S05: warn=60, fail=100 (from spec_kind.py)
        # Override: warn=999 (so lenient it will always PASS)
        settings = ValidationSettings(overrides={
            "S05": RuleOverride(rule_id="S05", warn_threshold=999),
        })
        rules = get_spec_rules(include_llm=False, kind=SpecKind.FEATURE, settings=settings)
        results = run_rules(rules, _FEATURE_SPEC)

        s05 = next(r for r in results if r.rule_id == "S05")
        # With warn_threshold=999, almost any spec passes
        assert s05.status == Status.PASS, f"S05 should pass with lenient override: {s05.message}"

    def test_none_kind_uses_code_defaults(self) -> None:
        """kind=None uses code defaults (no presets applied)."""
        rules_no_kind = get_spec_rules(include_llm=False, kind=None)
        rules_feature = get_spec_rules(include_llm=False, kind=SpecKind.FEATURE)

        # Feature gets extra kwargs (warn_conjunctions=2, etc.)
        # No-kind uses code defaults (warn_conjunctions=0, etc.)
        results_no = run_rules(rules_no_kind, _FEATURE_SPEC)
        results_feat = run_rules(rules_feature, _FEATURE_SPEC)

        # Both should produce results for all rules
        assert len(results_no) == len(results_feat)

    def test_rule_count_same_regardless_of_kind(self) -> None:
        """Number of rules doesn't change based on kind — only behaviour changes."""
        rules_feature = get_spec_rules(include_llm=False, kind=SpecKind.FEATURE)
        rules_component = get_spec_rules(include_llm=False, kind=SpecKind.COMPONENT)
        rules_none = get_spec_rules(include_llm=False, kind=None)

        assert len(rules_feature) == len(rules_component) == len(rules_none)
