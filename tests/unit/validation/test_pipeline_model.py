# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Unit tests for ValidationStep and ValidationPipeline models."""

from __future__ import annotations

from specweaver.validation.pipeline import ValidationPipeline, ValidationStep

# ---------------------------------------------------------------------------
# ValidationStep
# ---------------------------------------------------------------------------


class TestValidationStep:
    """Test ValidationStep model."""

    def test_minimal_step(self):
        """Step with just name and rule."""
        step = ValidationStep(name="s01_one_sentence", rule="S01")
        assert step.name == "s01_one_sentence"
        assert step.rule == "S01"
        assert step.params == {}
        assert step.path is None

    def test_step_with_params(self):
        """Step with threshold params."""
        step = ValidationStep(
            name="s05_day_test",
            rule="S05",
            params={"warn_threshold": 30, "fail_threshold": 60},
        )
        assert step.params["warn_threshold"] == 30
        assert step.params["fail_threshold"] == 60

    def test_step_with_custom_path(self):
        """Custom rule step with path to .py file."""
        step = ValidationStep(
            name="d01_schema",
            rule="D01",
            path="./rules/d01_schema.py",
            params={"strict_mode": True},
        )
        assert step.path == "./rules/d01_schema.py"
        assert step.rule == "D01"


# ---------------------------------------------------------------------------
# ValidationPipeline
# ---------------------------------------------------------------------------


class TestValidationPipeline:
    """Test ValidationPipeline model."""

    def test_minimal_pipeline(self):
        """Pipeline with name and steps."""
        pipeline = ValidationPipeline(
            name="test_pipeline",
            steps=[
                ValidationStep(name="s01", rule="S01"),
                ValidationStep(name="s02", rule="S02"),
            ],
        )
        assert pipeline.name == "test_pipeline"
        assert len(pipeline.steps) == 2
        assert pipeline.extends is None
        assert pipeline.override is None
        assert pipeline.remove is None
        assert pipeline.add is None

    def test_pipeline_with_description(self):
        """Pipeline with description and version."""
        pipeline = ValidationPipeline(
            name="spec_default",
            description="Default spec validation",
            version="1.0",
            steps=[ValidationStep(name="s01", rule="S01")],
        )
        assert pipeline.description == "Default spec validation"
        assert pipeline.version == "1.0"

    def test_pipeline_with_inheritance_fields(self):
        """Pipeline using extends/override/remove/add."""
        pipeline = ValidationPipeline(
            name="spec_custom",
            steps=[],  # will be resolved from extends
            extends="validation_spec_default",
            override={"s05_day_test": {"params": {"warn_threshold": 80}}},
            remove=["s04_dependency_dir"],
            add=[{
                "name": "d01_schema",
                "rule": "D01",
                "after": "s03_stranger",
                "params": {"strict_mode": True},
            }],
        )
        assert pipeline.extends == "validation_spec_default"
        assert "s05_day_test" in pipeline.override
        assert "s04_dependency_dir" in pipeline.remove
        assert len(pipeline.add) == 1

    def test_empty_steps_allowed(self):
        """Pipeline with empty steps is valid (extends provides steps)."""
        pipeline = ValidationPipeline(
            name="inheriting",
            steps=[],
            extends="base",
        )
        assert pipeline.steps == []

    def test_get_step_by_name(self):
        """get_step() returns step by name or None."""
        pipeline = ValidationPipeline(
            name="test",
            steps=[
                ValidationStep(name="s01", rule="S01"),
                ValidationStep(name="s05", rule="S05"),
            ],
        )
        step = pipeline.get_step("s05")
        assert step is not None
        assert step.rule == "S05"

        assert pipeline.get_step("nonexistent") is None


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


class TestYamlLoading:
    """Test loading ValidationPipeline from YAML dict (as if parsed by yaml.safe_load)."""

    def test_from_yaml_dict(self):
        """Pipeline can be created from a YAML-like dict."""
        data = {
            "name": "validation_spec_default",
            "description": "Default spec validation",
            "version": "1.0",
            "steps": [
                {"name": "s01", "rule": "S01"},
                {"name": "s05", "rule": "S05", "params": {"warn_threshold": 30}},
            ],
        }
        pipeline = ValidationPipeline(**data)
        assert pipeline.name == "validation_spec_default"
        assert len(pipeline.steps) == 2
        assert pipeline.steps[1].params["warn_threshold"] == 30

    def test_from_yaml_dict_with_inheritance(self):
        """Pipeline with extends from YAML-like dict."""
        data = {
            "name": "spec_library",
            "steps": [],
            "extends": "validation_spec_default",
            "override": {
                "s05": {"params": {"warn_threshold": 20}},
            },
            "remove": ["s04"],
        }
        pipeline = ValidationPipeline(**data)
        assert pipeline.extends == "validation_spec_default"
        assert pipeline.remove == ["s04"]
