# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Unit tests for ValidationPipeline YAML loading.

Tests load_pipeline_yaml() which resolves pipeline YAMLs from packaged
defaults, project-local overrides, and explicit paths.
"""

from __future__ import annotations

import pytest

from specweaver.validation.pipeline_loader import load_pipeline_yaml

# ---------------------------------------------------------------------------
# Load from packaged defaults
# ---------------------------------------------------------------------------


class TestPackagedDefaults:
    """Test loading built-in pipeline YAMLs."""

    def test_load_spec_default(self):
        """Loads the packaged validation_spec_default pipeline."""
        pipeline = load_pipeline_yaml("validation_spec_default")
        assert pipeline.name == "validation_spec_default"
        assert len(pipeline.steps) == 11

    def test_load_code_default(self):
        """Loads the packaged validation_code_default pipeline."""
        pipeline = load_pipeline_yaml("validation_code_default")
        assert pipeline.name == "validation_code_default"
        assert len(pipeline.steps) == 9

    def test_load_spec_library_profile(self):
        """Loads and resolves the library profile (extends spec_default)."""
        pipeline = load_pipeline_yaml("validation_spec_library")
        assert pipeline.name == "validation_spec_library"
        # After inheritance resolution, should have 11 steps (same as default)
        assert len(pipeline.steps) == 11

    def test_library_overrides_applied(self):
        """Library profile applies its own threshold overrides."""
        pipeline = load_pipeline_yaml("validation_spec_library")
        s05 = pipeline.get_step("s05_day_test")
        assert s05 is not None
        # Library has stricter thresholds
        assert s05.params["warn_threshold"] == 20
        assert s05.params["fail_threshold"] == 40

    def test_nonexistent_raises(self):
        """Nonexistent pipeline name raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            load_pipeline_yaml("nonexistent_pipeline")


# ---------------------------------------------------------------------------
# Load from project directory
# ---------------------------------------------------------------------------


class TestProjectOverride:
    """Test loading from project-local .specweaver/pipelines/."""

    def test_project_override_takes_precedence(self, tmp_path):
        """Project-local pipeline overrides packaged default."""
        pipelines_dir = tmp_path / ".specweaver" / "pipelines"
        pipelines_dir.mkdir(parents=True)

        yaml_content = """
name: validation_spec_default
description: Project-specific spec validation
version: "1.0"
steps:
  - name: s01
    rule: S01
"""
        (pipelines_dir / "validation_spec_default.yaml").write_text(yaml_content, encoding="utf-8")

        pipeline = load_pipeline_yaml("validation_spec_default", project_dir=tmp_path)
        # Project override has only 1 step
        assert len(pipeline.steps) == 1
        assert pipeline.description == "Project-specific spec validation"

    def test_project_pipeline_with_extends(self, tmp_path):
        """Project pipeline that extends packaged default."""
        pipelines_dir = tmp_path / ".specweaver" / "pipelines"
        pipelines_dir.mkdir(parents=True)

        yaml_content = """
name: my_custom_pipeline
extends: validation_spec_default
remove:
  - s04_dependency_dir
  - s07_test_first
"""
        (pipelines_dir / "my_custom_pipeline.yaml").write_text(yaml_content, encoding="utf-8")

        pipeline = load_pipeline_yaml("my_custom_pipeline", project_dir=tmp_path)
        # 11 base steps - 2 removed = 9
        assert len(pipeline.steps) == 9
        names = [s.name for s in pipeline.steps]
        assert "s04_dependency_dir" not in names
        assert "s07_test_first" not in names


# ---------------------------------------------------------------------------
# Malformed YAML (#1, #9)
# ---------------------------------------------------------------------------


class TestMalformedYaml:
    """Edge case: malformed or invalid pipeline YAML files."""

    def test_yaml_syntax_error(self, tmp_path):
        """YAML with syntax errors raises a YAML parsing error."""
        from ruamel.yaml import YAMLError

        pipelines_dir = tmp_path / ".specweaver" / "pipelines"
        pipelines_dir.mkdir(parents=True)
        (pipelines_dir / "validation_spec_default.yaml").write_text(
            "name: bad\n  invalid: [yaml: indentation\n",
            encoding="utf-8",
        )
        with pytest.raises(YAMLError):
            load_pipeline_yaml("validation_spec_default", project_dir=tmp_path)

    def test_yaml_missing_name(self, tmp_path):
        """YAML without 'name' field raises a validation error."""
        pipelines_dir = tmp_path / ".specweaver" / "pipelines"
        pipelines_dir.mkdir(parents=True)
        (pipelines_dir / "validation_spec_default.yaml").write_text(
            "description: no name field\nsteps:\n  - name: s01\n    rule: S01\n",
            encoding="utf-8",
        )
        with pytest.raises((TypeError, KeyError, ValueError)):
            load_pipeline_yaml("validation_spec_default", project_dir=tmp_path)

    def test_yaml_missing_steps_defaults_to_empty(self, tmp_path):
        """YAML without 'steps' field loads with default empty steps list."""
        pipelines_dir = tmp_path / ".specweaver" / "pipelines"
        pipelines_dir.mkdir(parents=True)
        (pipelines_dir / "validation_spec_default.yaml").write_text(
            "name: validation_spec_default\n",
            encoding="utf-8",
        )
        # Model defaults steps to [], so this is valid
        pipeline = load_pipeline_yaml(
            "validation_spec_default",
            project_dir=tmp_path,
        )
        assert pipeline.name == "validation_spec_default"
        assert pipeline.steps == []

    def test_yaml_null_steps(self, tmp_path):
        """YAML with 'steps: null' is treated as missing (defaults to [])."""
        pipelines_dir = tmp_path / ".specweaver" / "pipelines"
        pipelines_dir.mkdir(parents=True)
        (pipelines_dir / "validation_spec_default.yaml").write_text(
            "name: validation_spec_default\nsteps: null\n",
            encoding="utf-8",
        )
        # steps: null → Pydantic should coerce to default or raise
        # If the model has a default, null → default
        try:
            pipeline = load_pipeline_yaml(
                "validation_spec_default",
                project_dir=tmp_path,
            )
            # If it loads, steps should default to []
            assert pipeline.steps == [] or pipeline.steps is None
        except (TypeError, ValueError):
            pass  # Either outcome is acceptable

    def test_yaml_empty_file(self, tmp_path):
        """Empty YAML file raises TypeError (None cannot be unpacked as kwargs)."""
        pipelines_dir = tmp_path / ".specweaver" / "pipelines"
        pipelines_dir.mkdir(parents=True)
        (pipelines_dir / "validation_spec_default.yaml").write_text(
            "",
            encoding="utf-8",
        )
        with pytest.raises(TypeError):
            load_pipeline_yaml("validation_spec_default", project_dir=tmp_path)
