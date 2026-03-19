# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for pipeline YAML files — load, parse, and validate_flow."""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from specweaver.flow.models import PipelineDefinition

PIPELINES_DIR = Path(__file__).resolve().parents[3] / "src" / "specweaver" / "pipelines"


# ---------------------------------------------------------------------------
# feature_decomposition.yaml
# ---------------------------------------------------------------------------


class TestFeatureDecompositionPipeline:
    """feature_decomposition.yaml loads, parses, and validates."""

    @pytest.fixture()
    def pipeline_data(self) -> dict:
        yaml = YAML(typ="safe")
        path = PIPELINES_DIR / "feature_decomposition.yaml"
        assert path.exists(), f"Pipeline YAML not found: {path}"
        return yaml.load(path)

    def test_loads_and_parses(self, pipeline_data: dict) -> None:
        """YAML file loads into a valid PipelineDefinition."""
        pipeline = PipelineDefinition.model_validate(pipeline_data)
        assert pipeline.name == "feature_decomposition"

    def test_validate_flow_clean(self, pipeline_data: dict) -> None:
        """Pipeline passes validate_flow with no errors."""
        pipeline = PipelineDefinition.model_validate(pipeline_data)
        errors = pipeline.validate_flow()
        assert errors == [], f"Unexpected validation errors: {errors}"

    def test_has_three_steps(self, pipeline_data: dict) -> None:
        """Pipeline has exactly 3 steps: draft, validate, decompose."""
        pipeline = PipelineDefinition.model_validate(pipeline_data)
        assert len(pipeline.steps) == 3
        names = [s.name for s in pipeline.steps]
        assert names == ["draft_feature", "validate_feature", "decompose"]

    def test_params_kind_preserved(self, pipeline_data: dict) -> None:
        """validate_feature step has params.kind = 'feature'."""
        pipeline = PipelineDefinition.model_validate(pipeline_data)
        val_step = pipeline.get_step("validate_feature")
        assert val_step is not None
        assert val_step.params.get("kind") == "feature"


# ---------------------------------------------------------------------------
# Also verify existing pipelines remain valid
# ---------------------------------------------------------------------------


class TestExistingPipelines:
    """Existing pipelines still load and validate after enum changes."""

    @pytest.mark.parametrize("filename", ["new_feature.yaml", "validate_only.yaml"])
    def test_existing_pipeline_validates(self, filename: str) -> None:
        yaml = YAML(typ="safe")
        path = PIPELINES_DIR / filename
        if not path.exists():
            pytest.skip(f"{filename} not found")
        data = yaml.load(path)
        pipeline = PipelineDefinition.model_validate(data)
        errors = pipeline.validate_flow()
        assert errors == [], f"{filename} validation errors: {errors}"
