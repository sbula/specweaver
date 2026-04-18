# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests — validation sub-pipeline (pipeline_loader → executor → rules).

Exercises the full sub-pipeline chain: load YAML → resolve inheritance →
execute against real rules → verify results. Uses real packaged pipeline YAML
and real built-in rules — only the file content is synthetic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.assurance.validation.models import Status
from specweaver.core.flow.handlers.validation import ValidateSpecHandler

if TYPE_CHECKING:
    from pathlib import Path


# Ensure built-in rules are registered
import specweaver.assurance.validation.rules.code
import specweaver.assurance.validation.rules.spec  # noqa: F401

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GOOD_SPEC = (
    "# Greeter — Component Spec\n\n"
    "> **Status**: DRAFT\n\n---\n\n"
    "## 1. Purpose\n\nGreets users by name.\n\n---\n\n"
    "## 2. Contract\n\n```python\n"
    "def greet(name: str) -> str:\n"
    '    return f"Hello {name}"\n```\n\n---\n\n'
    "## 3. Protocol\n\n"
    "1. Validate name is not empty.\n"
    "2. Return greeting string.\n\n---\n\n"
    "## 4. Policy\n\n"
    "| Error | Behavior |\n|:---|:---|\n"
    "| Empty name | Raise ValueError |\n\n---\n\n"
    "## 5. Boundaries\n\n"
    "| Concern | Owned By |\n|:---|:---|\n"
    "| Auth | AuthService |\n\n---\n\n"
    "## Done Definition\n\n"
    "- [ ] Unit tests pass\n"
    "- [ ] Coverage >= 70%\n"
)

_GOOD_CODE = (
    '"""Greeter module."""\n\n\n'
    "def greet(name: str) -> str:\n"
    '    """Return a greeting for the given name."""\n'
    "    if not name:\n"
    '        msg = "Name must not be empty"\n'
    "        raise ValueError(msg)\n"
    '    return f"Hello, {name}!"\n'
)


# ---------------------------------------------------------------------------
# Load + Execute: default spec pipeline with real rules
# ---------------------------------------------------------------------------


class TestDefaultSpecPipeline:
    """Integration: load default spec pipeline and execute against real rules."""

    def test_load_and_execute_default_pipeline(self, tmp_path: Path) -> None:
        """Load validation_spec_default → execute → returns 11 results."""
        from specweaver.assurance.validation.executor import execute_validation_pipeline
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml

        pipeline = load_pipeline_yaml("validation_spec_default")
        assert pipeline.name == "validation_spec_default"
        assert len(pipeline.steps) == 12

        spec_file = tmp_path / "greeter_spec.md"
        spec_file.write_text(_GOOD_SPEC, encoding="utf-8")

        results = execute_validation_pipeline(pipeline, _GOOD_SPEC, spec_file)
        assert len(results) == 12

        rule_ids = [r.rule_id for r in results]
        assert "S01" in rule_ids
        assert "S04" in rule_ids  # default pipeline includes S04

    def test_default_pipeline_step_order_preserved(self) -> None:
        """Pipeline steps are in the YAML-defined order (cheap-to-expensive)."""
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml

        pipeline = load_pipeline_yaml("validation_spec_default")
        rule_ids = [step.rule for step in pipeline.steps]
        # First step is S01 (cheapest), last is S12 (most expensive)
        assert rule_ids[0] == "S01"
        assert rule_ids[-1] == "S12"

    def test_default_pipeline_params_applied(self) -> None:
        """Pipeline step params are correctly loaded from YAML."""
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml

        pipeline = load_pipeline_yaml("validation_spec_default")
        s01_step = next(s for s in pipeline.steps if s.rule == "S01")
        assert s01_step.params["warn_conjunctions"] == 1
        assert s01_step.params["fail_conjunctions"] == 2
        assert s01_step.params["max_h2"] == 8

        s05_step = next(s for s in pipeline.steps if s.rule == "S05")
        assert s05_step.params["warn_threshold"] == 30
        assert s05_step.params["fail_threshold"] == 60


# ---------------------------------------------------------------------------
# Load + Execute: feature spec pipeline (inheritance)
# ---------------------------------------------------------------------------


class TestFeatureSpecPipeline:
    """Integration: feature pipeline inherits default and removes S04."""

    def test_feature_pipeline_excludes_s04(self) -> None:
        """Feature pipeline resolves inheritance: S04 removed."""
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml

        pipeline = load_pipeline_yaml("validation_spec_feature")
        assert pipeline.name == "validation_spec_feature"

        rule_ids = [step.rule for step in pipeline.steps]
        assert "S04" not in rule_ids
        assert len(pipeline.steps) == 11  # 12 - 1 removed

    def test_feature_pipeline_inherits_params(self) -> None:
        """Feature pipeline inherits params from the default pipeline."""
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml

        pipeline = load_pipeline_yaml("validation_spec_feature")
        s01_step = next(s for s in pipeline.steps if s.rule == "S01")
        # Should inherit default's params
        assert s01_step.params["warn_conjunctions"] == 1
        assert s01_step.params["max_h2"] == 8

    def test_feature_pipeline_execute_produces_11_results(
        self,
        tmp_path: Path,
    ) -> None:
        """Feature pipeline runs 11 rules (no S04)."""
        from specweaver.assurance.validation.executor import execute_validation_pipeline
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml

        pipeline = load_pipeline_yaml("validation_spec_feature")
        spec_file = tmp_path / "feature_spec.md"
        spec_file.write_text(_GOOD_SPEC, encoding="utf-8")

        results = execute_validation_pipeline(pipeline, _GOOD_SPEC, spec_file)
        assert len(results) == 11
        assert all(r.rule_id != "S04" for r in results)

    def test_default_vs_feature_s04_difference(self, tmp_path: Path) -> None:
        """Same spec content: default has S04 result, feature does not."""
        from specweaver.assurance.validation.executor import execute_validation_pipeline
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml

        spec_file = tmp_path / "diff_test.md"
        spec_file.write_text(_GOOD_SPEC, encoding="utf-8")

        default = load_pipeline_yaml("validation_spec_default")
        feature = load_pipeline_yaml("validation_spec_feature")

        default_results = execute_validation_pipeline(default, _GOOD_SPEC, spec_file)
        feature_results = execute_validation_pipeline(feature, _GOOD_SPEC, spec_file)

        default_ids = {r.rule_id for r in default_results}
        feature_ids = {r.rule_id for r in feature_results}

        assert "S04" in default_ids
        assert "S04" not in feature_ids
        assert len(default_results) == len(feature_results) + 1


# ---------------------------------------------------------------------------
# Load + Execute: code pipeline
# ---------------------------------------------------------------------------


class TestCodePipeline:
    """Integration: load default code pipeline and execute against real rules."""

    def test_load_and_execute_code_pipeline(self, tmp_path: Path) -> None:
        """Load validation_code_default → execute → returns expected results."""
        from specweaver.assurance.validation.executor import execute_validation_pipeline
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml

        pipeline = load_pipeline_yaml("validation_code_default")
        assert pipeline.name == "validation_code_default"

        code_file = tmp_path / "greeter.py"
        code_file.write_text(_GOOD_CODE, encoding="utf-8")

        results = execute_validation_pipeline(pipeline, _GOOD_CODE, code_file)
        assert len(results) > 0

        rule_ids = [r.rule_id for r in results]
        assert "C01" in rule_ids  # syntax check always runs


# ---------------------------------------------------------------------------
# apply_settings_to_pipeline integration
# ---------------------------------------------------------------------------


class TestApplySettingsIntegration:
    """Integration: apply_settings_to_pipeline with real pipeline + real settings."""

    def test_disable_rule_removes_step(self) -> None:
        """Disabling S04 via settings removes S04 step from default pipeline."""
        from specweaver.assurance.validation.executor import apply_settings_to_pipeline
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml
        from specweaver.core.config.settings import RuleOverride, ValidationSettings

        pipeline = load_pipeline_yaml("validation_spec_default")
        assert any(s.rule == "S04" for s in pipeline.steps)

        settings = ValidationSettings(
            overrides={"S04": RuleOverride(rule_id="S04", enabled=False)},
        )
        modified = apply_settings_to_pipeline(pipeline, settings)

        assert all(s.rule != "S04" for s in modified.steps)
        assert len(modified.steps) == len(pipeline.steps) - 1

    def test_threshold_override_merges_into_params(self) -> None:
        """Threshold override merges into the step params."""
        from specweaver.assurance.validation.executor import apply_settings_to_pipeline
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml
        from specweaver.core.config.settings import RuleOverride, ValidationSettings

        pipeline = load_pipeline_yaml("validation_spec_default")
        s08_step = next(s for s in pipeline.steps if s.rule == "S08")
        assert s08_step.params["warn_threshold"] == 3  # YAML default

        settings = ValidationSettings(
            overrides={
                "S08": RuleOverride(
                    rule_id="S08",
                    warn_threshold=5,
                    fail_threshold=12,
                )
            },
        )
        modified = apply_settings_to_pipeline(pipeline, settings)

        s08_modified = next(s for s in modified.steps if s.rule == "S08")
        assert s08_modified.params["warn_threshold"] == 5
        assert s08_modified.params["fail_threshold"] == 12

    def test_settings_none_returns_same_pipeline(self) -> None:
        """None settings returns the pipeline unchanged."""
        from specweaver.assurance.validation.executor import apply_settings_to_pipeline
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml

        pipeline = load_pipeline_yaml("validation_spec_default")
        result = apply_settings_to_pipeline(pipeline, None)
        assert result is pipeline

    def test_disable_and_threshold_combined(self, tmp_path: Path) -> None:
        """Disable S04 + override S08 thresholds → execute with both applied."""
        from specweaver.assurance.validation.executor import (
            apply_settings_to_pipeline,
            execute_validation_pipeline,
        )
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml
        from specweaver.core.config.settings import RuleOverride, ValidationSettings

        pipeline = load_pipeline_yaml("validation_spec_default")
        settings = ValidationSettings(
            overrides={
                "S04": RuleOverride(rule_id="S04", enabled=False),
                "S08": RuleOverride(
                    rule_id="S08",
                    warn_threshold=99,
                    fail_threshold=99,
                ),
            },
        )
        modified = apply_settings_to_pipeline(pipeline, settings)

        spec_file = tmp_path / "test.md"
        spec_file.write_text(_GOOD_SPEC, encoding="utf-8")

        results = execute_validation_pipeline(modified, _GOOD_SPEC, spec_file)
        assert all(r.rule_id != "S04" for r in results)
        assert len(results) == 11  # 12 - S04

    def test_override_for_rule_not_in_pipeline(self) -> None:
        """Override for a rule not in the pipeline is silently ignored (#2)."""
        from specweaver.assurance.validation.executor import apply_settings_to_pipeline
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml
        from specweaver.core.config.settings import RuleOverride, ValidationSettings

        pipeline = load_pipeline_yaml("validation_spec_default")
        original_count = len(pipeline.steps)

        settings = ValidationSettings(
            overrides={
                "Z99": RuleOverride(
                    rule_id="Z99",
                    warn_threshold=5,
                    fail_threshold=10,
                )
            },
        )
        modified = apply_settings_to_pipeline(pipeline, settings)
        # Pipeline unchanged — Z99 override silently ignored
        assert len(modified.steps) == original_count

    def test_all_rules_disabled_produces_empty_pipeline(self) -> None:
        """Disabling all rules results in an empty pipeline (#10)."""
        from specweaver.assurance.validation.executor import (
            apply_settings_to_pipeline,
            execute_validation_pipeline,
        )
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml
        from specweaver.core.config.settings import RuleOverride, ValidationSettings

        pipeline = load_pipeline_yaml("validation_spec_default")
        overrides = {}
        for step in pipeline.steps:
            overrides[step.rule] = RuleOverride(rule_id=step.rule, enabled=False)

        settings = ValidationSettings(overrides=overrides)
        modified = apply_settings_to_pipeline(pipeline, settings)
        assert len(modified.steps) == 0

        # Executing an empty pipeline returns empty results
        results = execute_validation_pipeline(modified, "anything")
        assert results == []


# ---------------------------------------------------------------------------
# Project-local pipeline override
# ---------------------------------------------------------------------------


class TestProjectLocalPipeline:
    """Integration: project-local pipeline YAML overrides packaged defaults."""

    def test_project_local_pipeline_takes_precedence(self, tmp_path: Path) -> None:
        """Project-local validation_spec_default.yaml overrides packaged one."""
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml

        # Create project-local pipeline with only 2 rules
        pipelines_dir = tmp_path / ".specweaver" / "pipelines"
        pipelines_dir.mkdir(parents=True)
        (pipelines_dir / "validation_spec_default.yaml").write_text(
            "name: validation_spec_default\n"
            "version: '1.0'\n"
            "steps:\n"
            "  - name: s01_one_sentence\n"
            "    rule: S01\n"
            "  - name: s02_single_setup\n"
            "    rule: S02\n",
            encoding="utf-8",
        )

        pipeline = load_pipeline_yaml(
            "validation_spec_default",
            project_dir=tmp_path,
        )
        assert len(pipeline.steps) == 2  # project override has only 2
        assert pipeline.steps[0].rule == "S01"
        assert pipeline.steps[1].rule == "S02"

    def test_unknown_pipeline_raises_file_not_found(self) -> None:
        """Loading a non-existent pipeline raises FileNotFoundError."""
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml

        with pytest.raises(FileNotFoundError, match="not found"):
            load_pipeline_yaml("nonexistent_pipeline_xyz")


# ---------------------------------------------------------------------------
# Profile pipeline loading (e.g. web-app, library)
# ---------------------------------------------------------------------------


class TestProfilePipelines:
    """Integration: profile-specific pipelines resolve correctly."""

    @pytest.mark.parametrize(
        "profile",
        [
            "validation_spec_web_app",
            "validation_spec_library",
            "validation_spec_microservice",
            "validation_spec_data_pipeline",
            "validation_spec_ml_model",
        ],
    )
    def test_profile_pipeline_loads_and_resolves(self, profile: str) -> None:
        """Every profile pipeline loads and resolves without error."""
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml

        pipeline = load_pipeline_yaml(profile)
        assert pipeline.name == profile
        assert len(pipeline.steps) > 0

    @pytest.mark.parametrize(
        "profile",
        [
            "validation_spec_web_app",
            "validation_spec_library",
            "validation_spec_microservice",
            "validation_spec_data_pipeline",
            "validation_spec_ml_model",
        ],
    )
    def test_profile_pipeline_executes_without_crash(
        self,
        profile: str,
        tmp_path: Path,
    ) -> None:
        """Every profile pipeline executes against a good spec without crashing."""
        from specweaver.assurance.validation.executor import execute_validation_pipeline
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml

        pipeline = load_pipeline_yaml(profile)
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(_GOOD_SPEC, encoding="utf-8")

        results = execute_validation_pipeline(pipeline, _GOOD_SPEC, spec_file)
        assert len(results) > 0
        assert all(r.status in (Status.PASS, Status.WARN, Status.FAIL) for r in results)


# ---------------------------------------------------------------------------
# Handler wiring: ValidateSpecHandler uses sub-pipeline
# ---------------------------------------------------------------------------


class TestHandlerSubPipelineWiring:
    """Integration: handlers use the sub-pipeline path correctly."""

    def test_handler_default_uses_validation_spec_default(
        self,
        tmp_path: Path,
    ) -> None:
        """ValidateSpecHandler without kind runs validation_spec_default."""


        handler = ValidateSpecHandler()

        spec_file = tmp_path / "spec.md"
        spec_file.write_text(_GOOD_SPEC, encoding="utf-8")

        results = handler._run_validation(spec_file, settings=None)
        assert len(results) == 12
        rule_ids = [r.rule_id for r in results]
        assert "S04" in rule_ids

    def test_handler_feature_kind_uses_feature_pipeline(
        self,
        tmp_path: Path,
    ) -> None:
        """ValidateSpecHandler with kind_str='feature' runs feature pipeline."""


        handler = ValidateSpecHandler()

        spec_file = tmp_path / "spec.md"
        spec_file.write_text(_GOOD_SPEC, encoding="utf-8")

        results = handler._run_validation(spec_file, settings=None, kind_str="feature")
        assert len(results) == 11
        rule_ids = [r.rule_id for r in results]
        assert "S04" not in rule_ids
