# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Integration tests — SpecKind ↔ Rules ↔ Pipeline Executor cross-component.

These tests verify that the kind-aware preset system (C1) correctly
modifies rule behaviour (C2) when threaded through the pipeline executor (C3).
No mocking — exercises the real preset → rule constructor → check path.

Design: uses the pipeline executor path (load_pipeline_yaml + spec_kind.get_presets)
instead of the legacy get_spec_rules() function (removed in Feature 3.5b).
"""

from __future__ import annotations

import specweaver.validation.rules.spec  # noqa: F401 — register all spec rules
from specweaver.config.settings import RuleOverride, ValidationSettings
from specweaver.validation.executor import (
    apply_settings_to_pipeline,
    execute_validation_pipeline,
)
from specweaver.validation.models import Status
from specweaver.validation.pipeline_loader import load_pipeline_yaml
from specweaver.validation.runner import run_rules
from specweaver.validation.spec_kind import SpecKind, get_presets

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
# C1 ↔ C2 ↔ C3: Pipeline executor + kind presets integration (no mocking)
# ---------------------------------------------------------------------------


def _run_feature_pipeline(spec_text: str) -> list:
    """Load + execute the feature spec pipeline (removes S04)."""
    pipeline = load_pipeline_yaml("validation_spec_feature")
    return execute_validation_pipeline(pipeline, spec_text)


def _run_spec_rules_with_kind(
    kind: SpecKind,
    spec_text: str,
    settings: ValidationSettings | None = None,
) -> list:
    """Run spec rules using get_presets() (kind-specific constructor kwargs).

    This is the integration equivalent of the old get_spec_rules(kind=kind):
    1. Load the default spec pipeline
    2. Instantiate each rule with kind-awareness via get_presets(rule_id, kind)
    3. Execute via run_rules
    """
    from specweaver.validation.registry import get_registry

    registry = get_registry()
    pipeline = load_pipeline_yaml("validation_spec_default")
    if settings:
        pipeline = apply_settings_to_pipeline(pipeline, settings)

    rules = []
    for step in pipeline.steps:
        rule_cls = registry.get(step.rule)
        if rule_cls is None:
            continue
        rule_id = step.rule
        # get_presets(rule_id, kind) — takes TWO arguments
        preset_kwargs = get_presets(rule_id, kind)
        merged = {**step.params, **preset_kwargs}
        rules.append(rule_cls(**merged))

    return run_rules(rules, spec_text)


class TestRunnerKindIntegration:
    """Pipeline executor + presets + rules integration (no mocking)."""

    def test_feature_kind_uses_intent_header(self) -> None:
        """S01 with kind=FEATURE uses ## Intent header, not ## 1. Purpose."""
        results = _run_spec_rules_with_kind(SpecKind.FEATURE, _FEATURE_SPEC)

        s01 = next(r for r in results if r.rule_id == "S01")
        # Feature spec has ## Intent — S01 should find it and PASS (no conjunctions)
        assert s01.status == Status.PASS, f"S01 should pass on clean feature spec: {s01.message}"

    def test_component_kind_uses_purpose_header(self) -> None:
        """S01 with kind=COMPONENT uses ## 1. Purpose header."""
        results = _run_spec_rules_with_kind(SpecKind.COMPONENT, _COMPONENT_SPEC)

        s01 = next(r for r in results if r.rule_id == "S01")
        assert s01.status == Status.PASS, f"S01 should pass on clean component spec: {s01.message}"

    def test_feature_pipeline_skips_s04(self) -> None:
        """Feature pipeline (validation_spec_feature.yaml) removes S04."""
        results = _run_feature_pipeline(_FEATURE_SPEC)
        rule_ids = {r.rule_id for r in results}
        assert "S04" not in rule_ids, "S04 should be absent from feature pipeline"

    def test_component_kind_does_not_skip_s04(self) -> None:
        """Default pipeline runs S04 normally for component specs."""
        results = _run_spec_rules_with_kind(SpecKind.COMPONENT, _COMPONENT_SPEC)
        s04 = next(r for r in results if r.rule_id == "S04")
        assert s04.status != Status.SKIP, "S04 should not be SKIP for component kind"

    def test_feature_kind_enables_s03_abstraction_leak_mode(self) -> None:
        """S03 with kind=FEATURE detects abstraction leaks (file paths, method refs)."""
        results = _run_spec_rules_with_kind(SpecKind.FEATURE, _FEATURE_WITH_LEAKS)

        s03 = next(r for r in results if r.rule_id == "S03")
        assert s03.status in (Status.WARN, Status.FAIL), (
            f"S03 should detect abstraction leaks: {s03.message}"
        )
        assert len(s03.findings) > 0
        assert any("leak" in f.message.lower() or "path" in f.message.lower() for f in s03.findings)

    def test_same_spec_different_results_by_kind(self) -> None:
        """Same spec produces different results for FEATURE vs COMPONENT."""
        feature_results = _run_spec_rules_with_kind(SpecKind.FEATURE, _FEATURE_SPEC)
        component_results = _run_spec_rules_with_kind(SpecKind.COMPONENT, _FEATURE_SPEC)

        # S04 is present in both (default pipeline), but feature preset skips it
        f_s04 = next(r for r in feature_results if r.rule_id == "S04")
        c_s04 = next(r for r in component_results if r.rule_id == "S04")
        assert f_s04.status == Status.SKIP
        assert c_s04.status != Status.SKIP

        # S01: feature finds ## Intent → PASS; component looks for ## 1. Purpose → WARN
        f_s01 = next(r for r in feature_results if r.rule_id == "S01")
        c_s01 = next(r for r in component_results if r.rule_id == "S01")
        assert f_s01.status == Status.PASS
        assert c_s01.status == Status.WARN  # Can't find ## 1. Purpose in _FEATURE_SPEC

    def test_feature_conjunctions_fail_threshold(self) -> None:
        """Feature spec with many conjunctions in Intent → S01 FAIL."""
        results = _run_spec_rules_with_kind(SpecKind.FEATURE, _FEATURE_SPEC_MANY_CONJUNCTIONS)

        s01 = next(r for r in results if r.rule_id == "S01")
        assert s01.status == Status.FAIL, f"S01 should fail on many conjunctions: {s01.message}"
        assert len(s01.findings) > 0


class TestRunnerSettingsOverrideIntegration:
    """Settings overrides correctly layer on top of kind presets."""

    def test_settings_override_beats_preset(self) -> None:
        """Settings warn_threshold overrides kind preset for S05."""
        # Feature preset for S05: warn=60, fail=100 (from spec_kind.py)
        # Override: warn=999 (so lenient it will always PASS)
        settings = ValidationSettings(
            overrides={
                "S05": RuleOverride(rule_id="S05", warn_threshold=999),
            }
        )
        results = _run_spec_rules_with_kind(SpecKind.FEATURE, _FEATURE_SPEC, settings)

        s05 = next(r for r in results if r.rule_id == "S05")
        # With warn_threshold=999, almost any spec passes
        assert s05.status == Status.PASS, f"S05 should pass with lenient override: {s05.message}"

    def test_none_kind_uses_defaults(self) -> None:
        """COMPONENT presets (close to defaults) produce results for all rules."""
        results_no_preset = _run_spec_rules_with_kind(SpecKind.COMPONENT, _FEATURE_SPEC)
        results_feature = _run_spec_rules_with_kind(SpecKind.FEATURE, _FEATURE_SPEC)

        # Both should produce results for all pipeline rules
        assert len(results_no_preset) == len(results_feature)

    def test_rule_count_same_regardless_of_kind(self) -> None:
        """Number of rules doesn't change based on kind — only behaviour changes."""
        results_feature = _run_spec_rules_with_kind(SpecKind.FEATURE, _FEATURE_SPEC)
        results_component = _run_spec_rules_with_kind(SpecKind.COMPONENT, _FEATURE_SPEC)

        assert len(results_feature) == len(results_component)
