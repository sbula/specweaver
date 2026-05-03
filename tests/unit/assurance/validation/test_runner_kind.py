# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for SpecKind pipeline selection and spec_kind presets.

Replaces the old qa_runner_kind.py which tested via the now-removed
``get_spec_rules(kind=...)`` legacy function.

The correct pipeline-based design (Feature 3.5b) is:
- ``--level component`` (default) → ``validation_spec_default`` pipeline
- ``--level feature``             → ``validation_spec_feature`` pipeline
- DB settings on top via ``apply_settings_to_pipeline``

SpecKind presets (spec_kind.get_presets) are now for direct rule
instantiation only — they are NOT applied automatically by the runner.
These tests verify:
1. Pipeline YAML selection by level (via _resolve_pipeline_name)
2. Feature pipeline inherits default and removes S04
3. SpecKind presets are still accessible for direct use
4. Settings overrides interact correctly with the pipeline YAML params
"""

from __future__ import annotations

from specweaver.assurance.validation.executor import (
    apply_settings_to_pipeline,
    execute_validation_pipeline,
)
from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml
from specweaver.assurance.validation.spec_kind import SpecKind, get_presets
from specweaver.core.config.settings import RuleOverride, ValidationSettings

# ---------------------------------------------------------------------------
# Pipeline YAML selection by --level
# ---------------------------------------------------------------------------


class TestPipelineLevelSelection:
    """--level selects the correct YAML pipeline name via _resolve_pipeline_name."""

    def _load(self, name: str):
        """Load a pipeline by name, triggering rule registration."""
        import specweaver.assurance.validation.rules.spec  # noqa: F401

        return load_pipeline_yaml(name)

    def test_component_level_loads_default_pipeline(self) -> None:
        """component level → validation_spec_default."""
        from specweaver.assurance.validation.interfaces.cli import _resolve_pipeline_name

        assert _resolve_pipeline_name("component", None) == "validation_spec_default"

    def test_feature_level_loads_feature_pipeline(self) -> None:
        """feature level → validation_spec_feature."""
        from specweaver.assurance.validation.interfaces.cli import _resolve_pipeline_name

        assert _resolve_pipeline_name("feature", None) == "validation_spec_feature"

    def test_code_level_loads_code_pipeline(self) -> None:
        """code level → validation_code_default."""
        from specweaver.assurance.validation.interfaces.cli import _resolve_pipeline_name

        assert _resolve_pipeline_name("code", None) == "validation_code_default"

    def test_explicit_pipeline_overrides_level(self) -> None:
        """--pipeline always wins over --level."""
        from specweaver.assurance.validation.interfaces.cli import _resolve_pipeline_name

        result = _resolve_pipeline_name("component", "validation_spec_library")
        assert result == "validation_spec_library"

    def test_component_pipeline_has_twelve_steps(self) -> None:
        """Default component pipeline has 12 spec rules."""
        pipeline = self._load("validation_spec_default")
        assert len(pipeline.steps) == 12

    def test_feature_pipeline_excludes_s04(self) -> None:
        """Feature pipeline removes S04 (dependency direction)."""
        pipeline = self._load("validation_spec_feature")
        rule_ids = {s.rule for s in pipeline.steps}
        assert "S04" not in rule_ids

    def test_feature_pipeline_has_eleven_steps(self) -> None:
        """Feature pipeline has 11 steps (12 - S04 removed)."""
        pipeline = self._load("validation_spec_feature")
        assert len(pipeline.steps) == 11

    def test_feature_pipeline_inherits_component_rules(self) -> None:
        """Feature pipeline keeps S01, S02, S03, S08 etc."""
        pipeline = self._load("validation_spec_feature")
        rule_ids = {s.rule for s in pipeline.steps}
        assert "S01" in rule_ids
        assert "S08" in rule_ids


# ---------------------------------------------------------------------------
# SpecKind preset module
# ---------------------------------------------------------------------------


class TestSpecKindPresets:
    """spec_kind.get_presets returns the right constructor kwargs per kind."""

    def test_component_kind_returns_empty(self) -> None:
        """COMPONENT kind → no presets (use code defaults)."""
        assert get_presets("S08", SpecKind.COMPONENT) == {}

    def test_none_kind_returns_empty(self) -> None:
        """None kind → no presets."""
        assert get_presets("S08", None) == {}

    def test_feature_kind_s01_presets(self) -> None:
        """FEATURE S01 → warn_conjunctions=2, fail_conjunctions=4."""
        presets = get_presets("S01", SpecKind.FEATURE)
        assert presets.get("warn_conjunctions") == 2
        assert presets.get("fail_conjunctions") == 4
        assert presets.get("kind") == SpecKind.FEATURE

    def test_feature_kind_s03_mode(self) -> None:
        """FEATURE S03 → mode='abstraction_leak'."""
        presets = get_presets("S03", SpecKind.FEATURE)
        assert presets.get("mode") == "abstraction_leak"

    def test_feature_kind_s04_skip(self) -> None:
        """FEATURE S04 → skip=True."""
        presets = get_presets("S04", SpecKind.FEATURE)
        assert presets.get("skip") is True

    def test_feature_kind_s05_thresholds(self) -> None:
        """FEATURE S05 → warn=60, fail=100."""
        presets = get_presets("S05", SpecKind.FEATURE)
        assert presets.get("warn_threshold") == 60
        assert presets.get("fail_threshold") == 100

    def test_feature_kind_s08_thresholds(self) -> None:
        """FEATURE S08 → warn=2, fail=5."""
        presets = get_presets("S08", SpecKind.FEATURE)
        assert presets.get("warn_threshold") == 2
        assert presets.get("fail_threshold") == 5

    def test_unknown_rule_returns_empty(self) -> None:
        """Unknown rule_id → no presets."""
        assert get_presets("Z99", SpecKind.FEATURE) == {}

    def test_s02_feature_returns_empty(self) -> None:
        """S02 has no FEATURE presets."""
        assert get_presets("S02", SpecKind.FEATURE) == {}


# ---------------------------------------------------------------------------
# Settings override on top of feature pipeline
# ---------------------------------------------------------------------------


class TestFeaturePipelineWithSettings:
    """DB settings override can be layered on top of feature pipeline."""

    def _load_feature(self):
        import specweaver.assurance.validation.rules.spec  # noqa: F401

        return load_pipeline_yaml("validation_spec_feature")

    def test_settings_override_applies_to_feature_pipeline(self) -> None:
        """Settings override works on top of feature pipeline."""
        pipeline = self._load_feature()
        settings = ValidationSettings(
            overrides={
                "S08": RuleOverride(rule_id="S08", warn_threshold=99.0, fail_threshold=99.0),
            }
        )
        applied = apply_settings_to_pipeline(pipeline, settings)
        s08_step = next(s for s in applied.steps if s.rule == "S08")
        assert s08_step.params.get("warn_threshold") == 99

    def test_disable_rule_in_feature_pipeline(self) -> None:
        """Disabling a rule works in the feature pipeline too."""
        pipeline = self._load_feature()
        settings = ValidationSettings(
            overrides={
                "S08": RuleOverride(rule_id="S08", enabled=False),
            }
        )
        applied = apply_settings_to_pipeline(pipeline, settings)
        step_ids = {s.rule for s in applied.steps}
        assert "S08" not in step_ids
        # S04 was already removed by feature pipeline, still absent
        assert "S04" not in step_ids

    def test_feature_pipeline_execution_produces_results(self) -> None:
        """Execute the feature pipeline end-to-end and get results."""
        pipeline = self._load_feature()
        spec = "## Intent\nThis feature allows users to export data.\n"
        results = execute_validation_pipeline(pipeline, spec)
        assert len(results) == len(pipeline.steps)
        result_ids = {r.rule_id for r in results}
        assert "S04" not in result_ids
        assert "S01" in result_ids
