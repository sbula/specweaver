# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for apply_settings_to_pipeline — overrides via DB settings.

Replaces the old qa_runner_settings.py which tested via the now-removed
``get_spec_rules()`` / ``get_code_rules()`` legacy functions.

All tests use the production pipeline executor path:
    load_pipeline_yaml → apply_settings_to_pipeline → execute_pipeline

This exercises the same per-rule threshold injection but through the
real ValidationPipeline machinery, including PARAM_MAP translation.
"""

from __future__ import annotations

import pytest

from specweaver.config.settings import RuleOverride, ValidationSettings
from specweaver.validation.executor import (
    apply_settings_to_pipeline,
    execute_validation_pipeline,
)
from specweaver.validation.pipeline_loader import load_pipeline_yaml

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_SPEC = "## 1. Purpose\nThis component does one simple thing.\n"
MINIMAL_CODE = "# empty\n"

_SPEC_PIPELINE = "validation_spec_default"
_CODE_PIPELINE = "validation_code_default"


@pytest.fixture()
def spec_pipeline():
    """Default spec pipeline, freshly loaded."""
    import specweaver.validation.rules.spec  # noqa: F401

    return load_pipeline_yaml(_SPEC_PIPELINE)


@pytest.fixture()
def code_pipeline():
    """Default code pipeline, freshly loaded."""
    import specweaver.validation.rules.code  # noqa: F401

    return load_pipeline_yaml(_CODE_PIPELINE)


# ===========================================================================
# ValidationSettings injection tests
# ===========================================================================


class TestPipelineSettingsThresholds:
    """DB settings apply threshold overrides via PARAM_MAP."""

    def test_no_settings_uses_yaml_defaults(self, spec_pipeline) -> None:
        """Without settings, pipeline runs with YAML step.params as-is."""
        results = execute_validation_pipeline(spec_pipeline, MINIMAL_SPEC)
        assert len(results) > 0

    def test_s08_threshold_override_lowers_fail(self, spec_pipeline) -> None:
        """S08 fail_threshold=0 causes FAIL on any ambiguous content."""
        settings = ValidationSettings(
            overrides={
                "S08": RuleOverride(rule_id="S08", warn_threshold=0.0, fail_threshold=0.0),
            }
        )
        pipeline = apply_settings_to_pipeline(spec_pipeline, settings)
        # Verify S08 step params were updated
        s08_step = next((s for s in pipeline.steps if s.rule == "S08"), None)
        assert s08_step is not None
        assert s08_step.params.get("fail_threshold") == 0

    def test_rule_disabled_removes_step(self, spec_pipeline) -> None:
        """Disabled rule is not present in the applied pipeline."""
        settings = ValidationSettings(
            overrides={
                "S08": RuleOverride(rule_id="S08", enabled=False),
            }
        )
        pipeline = apply_settings_to_pipeline(spec_pipeline, settings)
        step_ids = {s.rule for s in pipeline.steps}
        assert "S08" not in step_ids

    def test_disabled_does_not_affect_others(self, spec_pipeline) -> None:
        """Disabling one rule doesn't affect other steps."""
        original_count = len(spec_pipeline.steps)
        settings = ValidationSettings(
            overrides={
                "S08": RuleOverride(rule_id="S08", enabled=False),
            }
        )
        pipeline = apply_settings_to_pipeline(spec_pipeline, settings)
        assert len(pipeline.steps) == original_count - 1

    def test_s01_param_map_translation(self, spec_pipeline) -> None:
        """S01 warn_threshold → warn_conjunctions via PARAM_MAP."""
        settings = ValidationSettings(
            overrides={
                "S01": RuleOverride(rule_id="S01", warn_threshold=5.0, fail_threshold=10.0),
            }
        )
        pipeline = apply_settings_to_pipeline(spec_pipeline, settings)
        s01_step = next(s for s in pipeline.steps if s.rule == "S01")
        # PARAM_MAP translates: warn_threshold → warn_conjunctions
        assert s01_step.params.get("warn_conjunctions") == 5
        assert s01_step.params.get("fail_conjunctions") == 10

    def test_multiple_rules_disabled(self, spec_pipeline) -> None:
        """Disabling multiple rules removes all of them."""
        settings = ValidationSettings(
            overrides={
                "S01": RuleOverride(rule_id="S01", enabled=False),
                "S03": RuleOverride(rule_id="S03", enabled=False),
                "S05": RuleOverride(rule_id="S05", enabled=False),
            }
        )
        pipeline = apply_settings_to_pipeline(spec_pipeline, settings)
        step_ids = {s.rule for s in pipeline.steps}
        assert "S01" not in step_ids
        assert "S03" not in step_ids
        assert "S05" not in step_ids
        assert "S04" in step_ids
        assert "S08" in step_ids

    def test_disabled_with_threshold_excluded(self, spec_pipeline) -> None:
        """A rule with enabled=False + threshold should still be excluded."""
        settings = ValidationSettings(
            overrides={
                "S08": RuleOverride(rule_id="S08", enabled=False, warn_threshold=99.0),
            }
        )
        pipeline = apply_settings_to_pipeline(spec_pipeline, settings)
        step_ids = {s.rule for s in pipeline.steps}
        assert "S08" not in step_ids

    def test_unknown_rule_id_ignored(self, spec_pipeline) -> None:
        """Override for unknown rule IDs doesn't crash pipeline application."""
        settings = ValidationSettings(
            overrides={
                "Z99": RuleOverride(rule_id="Z99", enabled=False),
            }
        )
        pipeline = apply_settings_to_pipeline(spec_pipeline, settings)
        assert len(pipeline.steps) == len(spec_pipeline.steps)

    def test_empty_settings_unchanged_pipeline(self, spec_pipeline) -> None:
        """Empty ValidationSettings produces same pipeline as no settings."""
        pipeline = apply_settings_to_pipeline(spec_pipeline, ValidationSettings())
        assert len(pipeline.steps) == len(spec_pipeline.steps)

    def test_partial_override_only_affects_specified_field(self, spec_pipeline) -> None:
        """Overriding only warn_threshold merges with YAML fail_threshold."""
        settings = ValidationSettings(
            overrides={
                "S08": RuleOverride(rule_id="S08", warn_threshold=99.0),
            }
        )
        pipeline = apply_settings_to_pipeline(spec_pipeline, settings)
        s08_step = next(s for s in pipeline.steps if s.rule == "S08")
        assert s08_step.params.get("warn_threshold") == 99

    def test_code_rule_disabled(self, code_pipeline) -> None:
        """Disabling a code rule removes it from the pipeline."""
        settings = ValidationSettings(
            overrides={
                "C01": RuleOverride(rule_id="C01", enabled=False),
            }
        )
        pipeline = apply_settings_to_pipeline(code_pipeline, settings)
        step_ids = {s.rule for s in pipeline.steps}
        assert "C01" not in step_ids

    def test_all_spec_rules_disabled_empty_pipeline(self, spec_pipeline) -> None:
        """Disabling all spec rules produces an empty pipeline."""
        all_ids = [s.rule for s in spec_pipeline.steps]
        overrides = {rid: RuleOverride(rule_id=rid, enabled=False) for rid in all_ids}
        settings = ValidationSettings(overrides=overrides)
        pipeline = apply_settings_to_pipeline(spec_pipeline, settings)
        assert pipeline.steps == []

    def test_s07_param_map_warn_threshold_to_warn_score(self, spec_pipeline) -> None:
        """S07 warn_threshold → warn_score via PARAM_MAP."""
        settings = ValidationSettings(
            overrides={
                "S07": RuleOverride(rule_id="S07", warn_threshold=9.0, fail_threshold=2.0),
            }
        )
        pipeline = apply_settings_to_pipeline(spec_pipeline, settings)
        s07_step = next((s for s in pipeline.steps if s.rule == "S07"), None)
        if s07_step is None:
            pytest.skip("S07 not in default spec pipeline")
        assert s07_step.params.get("warn_score") == 9
        assert s07_step.params.get("fail_score") == 2


# ===========================================================================
# Edge cases
# ===========================================================================


class TestPipelineSettingsEdgeCases:
    """Edge cases for pipeline settings injection."""

    def test_none_settings_returns_same_pipeline(self, spec_pipeline) -> None:
        """Returns the exact same pipeline if settings is None."""
        result = apply_settings_to_pipeline(spec_pipeline, None)
        assert result is spec_pipeline

    def test_execute_after_settings_produces_results(self, spec_pipeline) -> None:
        """Execution still returns results for remaining steps."""
        settings = ValidationSettings(
            overrides={
                "S08": RuleOverride(rule_id="S08", enabled=False),
            }
        )
        pipeline = apply_settings_to_pipeline(spec_pipeline, settings)
        results = execute_validation_pipeline(pipeline, MINIMAL_SPEC)
        result_ids = {r.rule_id for r in results}
        assert "S08" not in result_ids
        assert "S01" in result_ids

    def test_code_multiple_rules_disabled(self, code_pipeline) -> None:
        """Disabling multiple code rules with subprocess rules excluded."""
        settings = ValidationSettings(
            overrides={
                "C01": RuleOverride(rule_id="C01", enabled=False),
                "C05": RuleOverride(rule_id="C05", enabled=False),
            }
        )
        pipeline = apply_settings_to_pipeline(code_pipeline, settings)
        step_ids = {s.rule for s in pipeline.steps}
        assert "C01" not in step_ids
        assert "C05" not in step_ids
        assert "C02" in step_ids

    def test_override_for_non_threshold_rule_still_enables(self, spec_pipeline) -> None:
        """S02 has no threshold params — override only controls enabled."""
        settings = ValidationSettings(
            overrides={
                "S02": RuleOverride(rule_id="S02", enabled=False),
            }
        )
        pipeline = apply_settings_to_pipeline(spec_pipeline, settings)
        step_ids = {s.rule for s in pipeline.steps}
        assert "S02" not in step_ids

    def test_threshold_override_for_non_threshold_rule_ignored(self, spec_pipeline) -> None:
        """S02 has no PARAM_MAP entries — threshold override safely ignored."""
        settings = ValidationSettings(
            overrides={
                "S02": RuleOverride(rule_id="S02", warn_threshold=5.0),
            }
        )
        pipeline = apply_settings_to_pipeline(spec_pipeline, settings)
        step_ids = {s.rule for s in pipeline.steps}
        # S02 is still present (not disabled)
        assert "S02" in step_ids
        # params for S02 should not have leaked threshold
        s02_step = next(s for s in pipeline.steps if s.rule == "S02")
        assert "warn_threshold" not in s02_step.params
