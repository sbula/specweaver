# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Integration tests for rule registry — verifies all 19 built-in rules
are auto-registered correctly and the runner still produces correct results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest

from specweaver.validation.models import Rule

if TYPE_CHECKING:
    from specweaver.validation.registry import RuleRegistry

# ---------------------------------------------------------------------------
# Fresh registry helpers
# ---------------------------------------------------------------------------


def _populated_registry() -> RuleRegistry:
    """Create a fresh registry and populate it by importing rule packages.

    We can't simply use get_registry() because the global singleton may
    already have rules from other test modules. Instead, we verify that
    importing the packages registers into the global registry.
    """
    # Trigger auto-registration (idempotent — already imported in many tests)
    import specweaver.validation.rules.code
    import specweaver.validation.rules.spec  # noqa: F401
    from specweaver.validation.registry import get_registry

    return get_registry()


# ---------------------------------------------------------------------------
# Built-in rule registration
# ---------------------------------------------------------------------------


class TestBuiltInRegistration:
    """Verify all 19 built-in rules are registered."""

    EXPECTED_SPEC_IDS: ClassVar[list[str]] = [
        "S01", "S02", "S03", "S04", "S05", "S06",
        "S07", "S08", "S09", "S10", "S11",
    ]
    EXPECTED_CODE_IDS: ClassVar[list[str]] = [
        "C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08",
    ]

    def test_all_spec_rules_registered(self):
        """All 11 spec rules (S01-S11) are registered."""
        reg = _populated_registry()
        spec_ids = [rid for rid, _cls in reg.list_spec()]
        assert spec_ids == self.EXPECTED_SPEC_IDS

    def test_all_code_rules_registered(self):
        """All 8 code rules (C01-C08) are registered."""
        reg = _populated_registry()
        code_ids = [rid for rid, _cls in reg.list_code()]
        assert code_ids == self.EXPECTED_CODE_IDS

    def test_total_rule_count(self):
        """Total of 19 rules registered."""
        reg = _populated_registry()
        assert len(reg.list_all()) == 19

    def test_all_rules_are_rule_subclasses(self):
        """Every registered class is a Rule subclass."""
        reg = _populated_registry()
        for _rid, cls, _cat in reg.list_all():
            assert issubclass(cls, Rule), f"{cls.__name__} is not a Rule subclass"

    def test_each_rule_can_be_instantiated(self):
        """Every registered rule can be instantiated with no args."""
        reg = _populated_registry()
        for rid, cls, _cat in reg.list_all():
            try:
                instance = cls()
            except Exception as exc:
                pytest.fail(f"Failed to instantiate {rid} ({cls.__name__}): {exc}")
            assert instance.rule_id == rid

    def test_spec_categories_correct(self):
        """All spec rules have category 'spec'."""
        reg = _populated_registry()
        for rid, _cls, cat in reg.list_all():
            if rid.startswith("S"):
                assert cat == "spec", f"{rid} has wrong category: {cat}"

    def test_code_categories_correct(self):
        """All code rules have category 'code'."""
        reg = _populated_registry()
        for rid, _cls, cat in reg.list_all():
            if rid.startswith("C"):
                assert cat == "code", f"{rid} has wrong category: {cat}"


# ---------------------------------------------------------------------------
# Runner ↔ registry integration
# ---------------------------------------------------------------------------


class TestRunnerRegistryIntegration:
    """Verify pipeline executor produces correct results via registry."""

    def test_get_spec_rules_returns_11(self):
        """Spec default pipeline produces 11 rule results (S01-S11)."""
        import specweaver.validation.rules.spec  # noqa: F401

        from specweaver.validation.executor import execute_validation_pipeline
        from specweaver.validation.pipeline_loader import load_pipeline_yaml

        pipeline = load_pipeline_yaml("validation_spec_default")
        results = execute_validation_pipeline(pipeline, "# Test")
        assert len(results) == 11

    def test_get_spec_rules_ids_match(self):
        """Spec default pipeline returns results in S01-S11 order."""
        import specweaver.validation.rules.spec  # noqa: F401

        from specweaver.validation.executor import execute_validation_pipeline
        from specweaver.validation.pipeline_loader import load_pipeline_yaml

        pipeline = load_pipeline_yaml("validation_spec_default")
        results = execute_validation_pipeline(pipeline, "# Test")
        ids = sorted([r.rule_id for r in results])
        assert ids == ["S01", "S02", "S03", "S04", "S05", "S06",
                        "S07", "S08", "S09", "S10", "S11"]

    def test_get_code_rules_without_subprocess(self):
        """Code default pipeline without subprocess rules returns 6 rules."""
        import specweaver.validation.rules.code  # noqa: F401

        from specweaver.validation.executor import execute_validation_pipeline
        from specweaver.validation.pipeline_loader import load_pipeline_yaml

        # Load the non-subprocess code pipeline
        # C03 (subprocess_test_runner) and C04 (coverage) are subprocess rules
        pipeline = load_pipeline_yaml("validation_code_default")
        # Filter out subprocess-based steps (C03, C04)
        subprocess_ids = {"C03", "C04"}
        from specweaver.validation.pipeline import ValidationStep
        filtered = [s for s in pipeline.steps if s.rule not in subprocess_ids]
        pipeline = pipeline.model_copy(update={"steps": filtered})
        results = execute_validation_pipeline(pipeline, "# Test")
        assert len(results) == 6
        ids = [r.rule_id for r in results]
        assert "C03" not in ids
        assert "C04" not in ids

    def test_get_code_rules_with_subprocess(self):
        """Code default pipeline with all rules returns 8 rules."""
        import specweaver.validation.rules.code  # noqa: F401

        from specweaver.validation.executor import execute_validation_pipeline
        from specweaver.validation.pipeline_loader import load_pipeline_yaml

        pipeline = load_pipeline_yaml("validation_code_default")
        results = execute_validation_pipeline(pipeline, "# Test")
        assert len(results) == 8
        ids = sorted([r.rule_id for r in results])
        assert ids == ["C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08"]
