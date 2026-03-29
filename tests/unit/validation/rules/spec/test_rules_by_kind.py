# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for SpecKind-aware rule behavior.

Covers S01 (header + thresholds), S03 (abstraction leak mode),
S04 (skip for FEATURE), S05 (thresholds), S08 (thresholds).
"""

from __future__ import annotations

from specweaver.validation.models import Status
from specweaver.validation.spec_kind import SpecKind

# ---------------------------------------------------------------------------
# S01: One-Sentence Test — kind-aware header and thresholds
# ---------------------------------------------------------------------------


class TestS01KindAware:
    """S01 uses different headers and thresholds per SpecKind."""

    def test_feature_uses_intent_header(self) -> None:
        """Feature Specs use '## Intent' instead of '## 1. Purpose'."""
        from specweaver.validation.rules.spec.s01_one_sentence import OneSentenceRule

        spec = """\
## Intent

The system enables users to sell their shares.
"""
        rule = OneSentenceRule(kind=SpecKind.FEATURE)
        result = rule.check(spec)
        assert result.status == Status.PASS

    def test_feature_no_purpose_but_has_intent(self) -> None:
        """Feature Spec with ## Intent should NOT warn about missing purpose."""
        from specweaver.validation.rules.spec.s01_one_sentence import OneSentenceRule

        spec = """\
## Intent

The system enables users to sell their shares.
"""
        rule = OneSentenceRule(kind=SpecKind.FEATURE)
        result = rule.check(spec)
        # Should pass — it found the Intent section
        assert result.status == Status.PASS
        # Should not have findings about missing section
        assert not any("Could not find" in f.message for f in result.findings)

    def test_feature_purpose_header_not_matched(self) -> None:
        """Feature Spec with only ## 1. Purpose and no ## Intent warns."""
        from specweaver.validation.rules.spec.s01_one_sentence import OneSentenceRule

        spec = """\
## 1. Purpose

The system enables users to sell their shares.
"""
        rule = OneSentenceRule(kind=SpecKind.FEATURE)
        result = rule.check(spec)
        # Feature mode looks for ## Intent, so ## 1. Purpose is not found
        assert result.status == Status.WARN

    def test_feature_higher_conjunction_threshold(self) -> None:
        """Feature Specs tolerate 2 conjunctions (warn=2, fail=4)."""
        from specweaver.validation.rules.spec.s01_one_sentence import OneSentenceRule

        spec = """\
## Intent

This feature handles authentication and also manages session tokens.
"""
        # 1 conjunction: "and also" — below warn=2 for feature
        rule = OneSentenceRule(kind=SpecKind.FEATURE, warn_conjunctions=2, fail_conjunctions=4)
        result = rule.check(spec)
        assert result.status == Status.PASS

    def test_feature_many_conjunctions_fails(self) -> None:
        """Feature Specs fail at 4+ conjunctions."""
        from specweaver.validation.rules.spec.s01_one_sentence import OneSentenceRule

        spec = """\
## Intent

This feature handles auth and also manages sessions,
additionally provides rate limiting, furthermore logs events,
as well as managing profiles, along with tracking metrics.
"""
        rule = OneSentenceRule(kind=SpecKind.FEATURE, warn_conjunctions=2, fail_conjunctions=4)
        result = rule.check(spec)
        assert result.status == Status.FAIL

    def test_component_default_still_works(self) -> None:
        """Component kind still uses ## 1. Purpose and default thresholds."""
        from specweaver.validation.rules.spec.s01_one_sentence import OneSentenceRule

        spec = """\
## 1. Purpose

The Greeter Service generates personalized welcome messages.
"""
        rule = OneSentenceRule(kind=SpecKind.COMPONENT)
        result = rule.check(spec)
        assert result.status == Status.PASS

    def test_no_kind_backwards_compatible(self) -> None:
        """kind=None behaves exactly as before (uses ## 1. Purpose, default thresholds)."""
        from specweaver.validation.rules.spec.s01_one_sentence import OneSentenceRule

        spec = """\
## 1. Purpose

The Greeter Service generates personalized welcome messages.
"""
        rule = OneSentenceRule()
        result = rule.check(spec)
        assert result.status == Status.PASS


# ---------------------------------------------------------------------------
# S03: Stranger Test — abstraction leak mode for Feature Specs
# ---------------------------------------------------------------------------


class TestS03KindAware:
    """S03 switches to abstraction-leak detection for Feature Specs."""

    def test_feature_flags_file_paths(self) -> None:
        """File paths are abstraction leaks in Feature Specs."""
        from specweaver.validation.rules.spec.s03_stranger import StrangerTestRule

        spec = """\
## Intent

The feature updates the billing module.
See [TaxCalculator](src/billing/taxes/vat.py) for details.
"""
        rule = StrangerTestRule(mode="abstraction_leak")
        result = rule.check(spec)
        assert result.status in (Status.WARN, Status.FAIL)
        assert any(
            "abstraction" in f.message.lower()
            or "file path" in f.message.lower()
            or ".py" in f.message
            for f in result.findings
        )

    def test_feature_flags_class_method(self) -> None:
        """Class.method references are abstraction leaks."""
        from specweaver.validation.rules.spec.s03_stranger import StrangerTestRule

        spec = """\
## Intent

The feature calls `TaxCalculator.calculate()` to compute taxes.
"""
        rule = StrangerTestRule(mode="abstraction_leak")
        result = rule.check(spec)
        assert result.status in (Status.WARN, Status.FAIL)
        assert any(
            "abstraction" in f.message.lower() or "class" in f.message.lower() or "." in f.message
            for f in result.findings
        )

    def test_feature_flags_import_paths(self) -> None:
        """Dotted import paths (3+ segments) are abstraction leaks."""
        from specweaver.validation.rules.spec.s03_stranger import StrangerTestRule

        spec = """\
## Intent

Imports from `specweaver.validation.runner` to process specs.
"""
        rule = StrangerTestRule(mode="abstraction_leak")
        result = rule.check(spec)
        assert result.status in (Status.WARN, Status.FAIL)

    def test_feature_allows_service_references(self) -> None:
        """Service and module references are valid in Feature Specs."""
        from specweaver.validation.rules.spec.s03_stranger import StrangerTestRule

        spec = """\
## Intent

This feature involves services: depotManager, broker, trader.
It affects the billing module.
"""
        rule = StrangerTestRule(mode="abstraction_leak")
        result = rule.check(spec)
        assert result.status == Status.PASS

    def test_feature_ignores_code_blocks(self) -> None:
        """Abstraction leaks inside code blocks are ignored."""
        from specweaver.validation.rules.spec.s03_stranger import StrangerTestRule

        spec = """\
## Intent

The feature updates billing.

```python
from specweaver.validation.runner import run_rules
class TaxCalculator:
    pass
```
"""
        rule = StrangerTestRule(mode="abstraction_leak")
        result = rule.check(spec)
        assert result.status == Status.PASS

    def test_component_mode_unchanged(self) -> None:
        """Without mode='abstraction_leak', S03 counts external references."""
        from specweaver.validation.rules.spec.s03_stranger import StrangerTestRule

        spec = """\
## 1. Purpose

The Greeter Service generates personalized welcome messages.
"""
        rule = StrangerTestRule()
        result = rule.check(spec)
        assert result.status == Status.PASS


# ---------------------------------------------------------------------------
# S04: Dependency Direction — skip for Feature Specs
# ---------------------------------------------------------------------------


class TestS04KindAware:
    """S04 is skipped entirely for Feature Specs."""

    def test_feature_skips(self) -> None:
        """Feature Specs skip S04 — dependency direction is an architecture concern."""
        from specweaver.validation.rules.spec.s04_dependency_dir import DependencyDirectionRule

        spec = """\
## Intent

This feature has many cross-references:
See [auth](auth_spec.md) and [session](session_spec.md).
Also see [rate_limit](rate_limit_spec.md).
Also see [cache](cache_spec.md) and [db](db_spec.md).
Also see [queue](queue_spec.md) and [events](events_spec.md).
Also see [metrics](metrics_spec.md) and [logging](logging_spec.md).
"""
        rule = DependencyDirectionRule(skip=True)
        result = rule.check(spec)
        assert result.status == Status.SKIP

    def test_component_not_skipped(self) -> None:
        """Component Specs still run S04 normally."""
        from specweaver.validation.rules.spec.s04_dependency_dir import DependencyDirectionRule

        spec = """\
## 1. Purpose

The Greeter Service generates personalized welcome messages.
"""
        rule = DependencyDirectionRule()
        result = rule.check(spec)
        assert result.status != Status.SKIP


# ---------------------------------------------------------------------------
# S05: Day Test — kind-aware thresholds
# ---------------------------------------------------------------------------


class TestS05KindAware:
    """S05 uses higher thresholds for Feature Specs."""

    def test_feature_higher_threshold_passes(self) -> None:
        """A moderately complex spec that would WARN for component passes for feature."""
        from specweaver.validation.rules.spec.s05_day_test import DayTestRule

        # Build a spec with score ~30 (above component warn=25, below feature warn=60)
        spec = "## Intent\n\nModerately complex feature.\n"
        for i in range(30):
            spec += f"\n### Section {i}\n\n"
            spec += "If condition then handle, when state changes unless.\n"
            spec += f"Handle `STATE_{i}` transitions.\n"
            spec += "```python\ncode_block()\n```\n"

        # With component defaults (warn=25), this might warn
        component_rule = DayTestRule()
        component_result = component_rule.check(spec)

        # With feature thresholds (warn=60), this should pass
        feature_rule = DayTestRule(warn_threshold=60, fail_threshold=100)
        feature_result = feature_rule.check(spec)

        # The feature threshold should be more lenient
        if component_result.status in (Status.WARN, Status.FAIL):
            assert feature_result.status == Status.PASS

    def test_feature_very_complex_still_warns(self) -> None:
        """Even with feature thresholds, extremely complex specs warn."""
        from specweaver.validation.rules.spec.s05_day_test import DayTestRule

        # Build an extremely complex spec
        spec = "## Intent\n\nExtremely complex feature.\n"
        for i in range(100):
            spec += f"\n## Section {i}\n\n"
            spec += "If condition then handle, when state changes unless otherwise.\n"
            spec += f"Handle `STATE_{i}` and `STATUS_{i}` transitions.\n"
            spec += "```python\nclass Complex:\n    pass\n```\n"

        rule = DayTestRule(warn_threshold=60, fail_threshold=100)
        result = rule.check(spec)
        assert result.status in (Status.WARN, Status.FAIL)


# ---------------------------------------------------------------------------
# S08: Ambiguity Test — kind-aware thresholds
# ---------------------------------------------------------------------------


class TestS08KindAware:
    """S08 uses higher thresholds for Feature Specs."""

    def test_feature_two_weasels_passes(self) -> None:
        """Feature Specs pass with 2 weasel words (warn=2 means >2 warns)."""
        from specweaver.validation.rules.spec.s08_ambiguity import AmbiguityRule

        spec = """\
## Intent

The feature should handle authentication. Users may need to re-authenticate.
"""
        # Default (component): warn=1, fail=3 → 2 weasels = WARN
        # Feature: warn=2, fail=5 → 2 weasels = PASS
        feature_rule = AmbiguityRule(warn_threshold=2, fail_threshold=5)
        result = feature_rule.check(spec)
        assert result.status == Status.PASS

    def test_component_two_weasels_warns(self) -> None:
        """Component Specs warn with 2 weasel words (warn=1)."""
        from specweaver.validation.rules.spec.s08_ambiguity import AmbiguityRule

        spec = """\
## 1. Purpose

The component should handle authentication. Users may need to re-authenticate.
"""
        rule = AmbiguityRule()  # default: warn=1, fail=3
        result = rule.check(spec)
        assert result.status == Status.WARN

    def test_feature_many_weasels_warns(self) -> None:
        """Feature Specs warn when weasels exceed warn_threshold=2."""
        from specweaver.validation.rules.spec.s08_ambiguity import AmbiguityRule

        spec = """\
## Intent

The feature should handle authentication. Users may need tokens.
The system could also properly validate sessions.
"""
        feature_rule = AmbiguityRule(warn_threshold=2, fail_threshold=5)
        result = feature_rule.check(spec)
        assert result.status in (Status.WARN, Status.FAIL)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestS03MixedLeaks:
    """S03 correctly accumulates multiple leak types in one doc."""

    def test_multiple_leak_types_counted_together(self) -> None:
        """File path + class.method + import path all count as leaks."""
        from specweaver.validation.rules.spec.s03_stranger import StrangerTestRule

        spec = """\
## Intent

The feature updates billing.
See [TaxCalculator](src/billing/taxes/vat.py) for tax logic.
Use `TaxCalculator.calculate()` to compute.
Imports from `specweaver.validation.runner` for processing.
"""
        rule = StrangerTestRule(mode="abstraction_leak")
        result = rule.check(spec)
        assert result.status in (Status.WARN, Status.FAIL)
        assert len(result.findings) >= 3


class TestS03FalsePositives:
    """S03 abstraction leak detection avoids flagging valid content."""

    def test_service_names_not_flagged(self) -> None:
        """Two-segment dotted names like 'billing.module' are valid."""
        from specweaver.validation.rules.spec.s03_stranger import StrangerTestRule

        spec = """\
## Intent

The feature integrates with billing.service and auth.module.
"""
        rule = StrangerTestRule(mode="abstraction_leak")
        result = rule.check(spec)
        # Two-segment dotted names should not be flagged
        assert result.status == Status.PASS

    def test_unlisted_extension_not_flagged(self) -> None:
        """File extensions not in the hardcoded list (e.g. .kt, .rb) pass through."""
        from specweaver.validation.rules.spec.s03_stranger import StrangerTestRule

        spec = """\
## Intent

The feature involves src/billing/taxes/vat.kt for Kotlin code.
"""
        rule = StrangerTestRule(mode="abstraction_leak")
        result = rule.check(spec)
        # .kt is not in the hardcoded extension list, so no file-path leak
        file_leaks = [f for f in result.findings if "file path" in f.message.lower()]
        assert len(file_leaks) == 0


class TestS01EdgeCases:
    """S01 edge cases for kind-aware behavior."""

    def test_empty_spec_with_feature_kind(self) -> None:
        """Empty spec with kind=FEATURE warns about missing section."""
        from specweaver.validation.rules.spec.s01_one_sentence import OneSentenceRule

        rule = OneSentenceRule(kind=SpecKind.FEATURE)
        result = rule.check("")
        assert result.status == Status.WARN
        assert any("Intent" in f.message or "Could not find" in f.message for f in result.findings)

    def test_header_pattern_kwarg_overrides_kind(self) -> None:
        """Explicit header_pattern takes precedence over kind auto-resolve."""
        import re

        from specweaver.validation.rules.spec.s01_one_sentence import OneSentenceRule

        # Use component pattern with feature kind — explicit pattern should win
        component_pattern = re.compile(
            r"##\s*1\.?\s*Purpose\b(.*?)(?=\n##\s|\Z)",
            re.DOTALL | re.IGNORECASE,
        )
        spec = """\
## 1. Purpose

The system does one thing.
"""
        rule = OneSentenceRule(kind=SpecKind.FEATURE, header_pattern=component_pattern)
        result = rule.check(spec)
        # Should find the Purpose section via the explicit pattern, not look for Intent
        assert result.status == Status.PASS


class TestS04EdgeCases:
    """S04 edge cases for skip behavior."""

    def test_skip_does_not_read_content(self) -> None:
        """With skip=True, even garbage content returns SKIP."""
        from specweaver.validation.rules.spec.s04_dependency_dir import DependencyDirectionRule

        # Content that would normally cause errors if processed
        rule = DependencyDirectionRule(skip=True)
        result = rule.check("THIS IS NOT VALID SPEC CONTENT AT ALL §§§")
        assert result.status == Status.SKIP


class TestS03FailThreshold:
    """S03 abstraction leak mode FAIL branch (>fail_threshold leaks)."""

    def test_many_leaks_trigger_fail(self) -> None:
        """More than fail_threshold leaks → FAIL status."""
        from specweaver.validation.rules.spec.s03_stranger import StrangerTestRule

        spec = """\
## Intent

The feature updates billing.
See [TaxCalculator](src/billing/taxes/vat.py) for tax logic.
See [InvoiceGen](src/billing/invoices/gen.py) for invoicing.
See [PaymentGW](src/payments/gateway.py) for payments.
Use `TaxCalculator.calculate()` to compute taxes.
Use `InvoiceGen.render()` to render invoices.
"""
        # Default fail_threshold=10; use custom fail_threshold=3 to hit FAIL branch
        rule = StrangerTestRule(mode="abstraction_leak", fail_threshold=3)
        result = rule.check(spec)
        assert result.status == Status.FAIL
        assert len(result.findings) > 3

    def test_custom_fail_threshold(self) -> None:
        """Custom fail_threshold is respected."""
        from specweaver.validation.rules.spec.s03_stranger import StrangerTestRule

        spec = """\
## Intent

The feature updates billing.
See [TaxCalculator](src/billing/taxes/vat.py) for tax logic.
Use `TaxCalculator.calculate()` to compute taxes.
"""
        # 2 leaks; set fail_threshold=1 to trigger FAIL
        rule = StrangerTestRule(mode="abstraction_leak", fail_threshold=1)
        result = rule.check(spec)
        assert result.status == Status.FAIL


class TestS03CodeBlockStripping:
    """S03 code block stripping handles edge cases."""

    def test_adjacent_code_blocks_stripped(self) -> None:
        """Two consecutive code blocks are both stripped."""
        from specweaver.validation.rules.spec.s03_stranger import StrangerTestRule

        spec = """\
## Intent

The feature updates billing.

```python
from specweaver.validation.runner import run_rules
```

```python
from specweaver.drafting.decomposition import DecompositionPlan
```
"""
        rule = StrangerTestRule(mode="abstraction_leak")
        result = rule.check(spec)
        assert result.status == Status.PASS

    def test_empty_code_block_stripped(self) -> None:
        """Empty code blocks are removed without errors."""
        from specweaver.validation.rules.spec.s03_stranger import StrangerTestRule

        spec = """\
## Intent

The feature updates billing.

```
```
"""
        rule = StrangerTestRule(mode="abstraction_leak")
        result = rule.check(spec)
        assert result.status == Status.PASS


class TestS01MaxH2WithFeatureKind:
    """S01 max_h2 overflow with feature kind triggers warning."""

    def test_feature_spec_many_h2_warns(self) -> None:
        """Feature spec with >max_h2 sections triggers WARN."""
        from specweaver.validation.rules.spec.s01_one_sentence import OneSentenceRule

        # Build a spec with 10 H2 sections (default max_h2=8)
        spec = "## Intent\n\nThis feature enables selling.\n\n"
        for i in range(10):
            spec += f"\n## Section {i}\n\nContent.\n"

        rule = OneSentenceRule(kind=SpecKind.FEATURE)
        result = rule.check(spec)
        assert result.status == Status.WARN
        assert any("H2" in f.message or "section" in f.message.lower() for f in result.findings)
