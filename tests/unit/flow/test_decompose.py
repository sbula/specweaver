# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for decompose step handlers."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.flow._base import RunContext
from specweaver.flow._decompose import DecomposeFeatureHandler, OrchestrateComponentsHandler
from specweaver.flow.models import PipelineStep, StepAction, StepTarget
from specweaver.flow.state import StepStatus


@pytest.fixture
def mock_context(tmp_path: Path) -> RunContext:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return RunContext(
        run_id="test_run",
        project_path=workspace,
        spec_path=workspace / "docs" / "specs" / "test_feature_spec.md"
    )

@pytest.fixture
def mock_step() -> PipelineStep:
    return PipelineStep(
        name="decompose_step",
        action=StepAction.DECOMPOSE,
        target=StepTarget.FEATURE,
        params={}
    )

@pytest.mark.asyncio
async def test_decompose_feature_handler_success(mock_context: RunContext, mock_step: PipelineStep, tmp_path: Path) -> None:
    # Setup feature spec
    specs_dir = mock_context.project_path / "docs" / "specs" / "features"
    specs_dir.mkdir(parents=True)
    spec_path = specs_dir / "test_feature_spec.md"
    spec_path.write_text("# Test Feature")
    mock_context.spec_path = spec_path

    mock_step.params = {"feature_name": "test_feature", "output_dir": str(specs_dir)}

    with patch("specweaver.flow._decompose.FeatureDecomposer") as mock_decomposer_cls:
        mock_decomposer = AsyncMock()
        mock_plan = MagicMock()
        mock_plan.coverage_score = 1.0 # 100% coverage
        mock_plan.model_dump.return_value = {"coverage_score": 1.0}
        mock_decomposer.decompose.return_value = mock_plan
        mock_decomposer_cls.return_value = mock_decomposer

        handler = DecomposeFeatureHandler()
        result = await handler.execute(mock_step, mock_context)

        assert result.status == StepStatus.PASSED
        mock_decomposer.decompose.assert_called_once()
        assert result.output.get("coverage_score") == 1.0

@pytest.mark.asyncio
async def test_decompose_feature_handler_coverage_fail(mock_context: RunContext, mock_step: PipelineStep, tmp_path: Path) -> None:
    specs_dir = mock_context.project_path / "docs" / "specs" / "features"
    specs_dir.mkdir(parents=True)
    spec_path = specs_dir / "test_feature_spec.md"
    spec_path.write_text("# Test Feature")
    mock_context.spec_path = spec_path

    mock_step.params = {"feature_name": "test_feature"}

    with patch("specweaver.flow._decompose.FeatureDecomposer") as mock_decomposer_cls:
        mock_decomposer = AsyncMock()
        mock_plan = MagicMock()
        mock_plan.coverage_score = 0.5 # FR-5 bounds fail
        mock_decomposer.decompose.return_value = mock_plan
        mock_decomposer_cls.return_value = mock_decomposer

        handler = DecomposeFeatureHandler()
        result = await handler.execute(mock_step, mock_context)

        # Should fail autonomously because of DMZ 3-strike loop rule
        assert result.status == StepStatus.FAILED
        assert "below 1.0" in str(result.error_message)

@pytest.fixture
def mock_orchestrate_step() -> PipelineStep:
    return PipelineStep(
        name="orchestrate_step",
        action=StepAction.ORCHESTRATE,
        target=StepTarget.COMPONENTS,
        params={}
    )

@pytest.mark.asyncio
async def test_orchestrate_components_handler_success(mock_context: RunContext, mock_orchestrate_step: PipelineStep, tmp_path: Path) -> None:
    # Context now should have a 'plan' JSON string pre-loaded by previous HITL review step
    # We simulate this by dumping a fake plan into context.plan
    import json
    mock_plan_dict = {
        "feature_spec": "path.md",
        "components": [
            {"component": "service_a", "exists": True, "change_nature": "behavior", "description": "Update", "proposed_dal": "DAL_B", "dependencies": [], "confidence": 100},
            {"component": "service_b", "exists": False, "change_nature": "new", "description": "Create", "proposed_dal": "DAL_C", "dependencies": [], "confidence": 100}
        ],
        "integration_seams": [],
        "build_sequence": ["service_a", "service_b"],
        "coverage_score": 1.0,
        "timestamp": "2026-01-01T00:00:00Z"
    }
    mock_context.plan = json.dumps(mock_plan_dict)


    mock_runner = AsyncMock()
    mock_run_result = MagicMock()
    mock_run_result.status = "completed"
    mock_run_result.run_id = "child_123"
    mock_runner.fan_out.return_value = [mock_run_result, mock_run_result]
    mock_context.pipeline_runner = mock_runner

    handler = OrchestrateComponentsHandler()
    result = await handler.execute(mock_orchestrate_step, mock_context)

    assert result.status == StepStatus.PASSED
    assert len(result.output["sub_runs"]) == 2
    mock_runner.fan_out.assert_called_once()
    args, kwargs = mock_runner.fan_out.call_args
    assert len(args[0]) == 2 # 2 matching components in mock
    assert kwargs["parent_run_id"] == "test_run"


@pytest.mark.asyncio
async def test_orchestrate_components_handler_empty_plan(mock_orchestrate_step: PipelineStep, mock_context: RunContext) -> None:
    handler = OrchestrateComponentsHandler()
    mock_context.plan = None
    result = await handler.execute(mock_orchestrate_step, mock_context)
    assert result.status == StepStatus.FAILED
    assert "No DecompositionPlan" in str(result.error_message)

@pytest.mark.asyncio
async def test_orchestrate_components_handler_missing_runner(mock_orchestrate_step: PipelineStep, mock_context: RunContext) -> None:
    handler = OrchestrateComponentsHandler()
    mock_context.plan = '{ "components": [{"component": "valid"}] }'
    mock_context.pipeline_runner = None
    result = await handler.execute(mock_orchestrate_step, mock_context)
    assert result.status == StepStatus.FAILED
    assert "pipeline_runner not found" in str(result.error_message)

@pytest.mark.asyncio
async def test_orchestrate_components_handler_child_failure(mock_orchestrate_step: PipelineStep, mock_context: RunContext) -> None:
    handler = OrchestrateComponentsHandler()
    mock_context.plan = '{ "components": [{"component": "valid"}] }'
    mock_runner = AsyncMock()
    # Mock a failed sub run
    mock_run_result = MagicMock()
    mock_run_result.status = StepStatus.FAILED
    mock_run_result.run_id = "failed_child"
    mock_runner.fan_out.return_value = [mock_run_result]
    mock_context.pipeline_runner = mock_runner

    result = await handler.execute(mock_orchestrate_step, mock_context)
    assert result.status == StepStatus.FAILED
    assert "1 sub-pipelines failed" in str(result.error_message)

@pytest.mark.asyncio
async def test_orchestrate_components_malicious_name(mock_orchestrate_step: PipelineStep, mock_context: RunContext) -> None:
    handler = OrchestrateComponentsHandler()
    mock_context.plan = '{ "components": [{"component": "../../../etc/shadow"}] }'
    result = await handler.execute(mock_orchestrate_step, mock_context)
    assert result.status == StepStatus.FAILED
    assert "Invalid or malicious component name" in str(result.error_message)

@pytest.mark.asyncio
async def test_orchestrate_loads_new_feature_yaml(mock_orchestrate_step: PipelineStep, mock_context: RunContext) -> None:
    # FR-3 / FR-4 Verification
    handler = OrchestrateComponentsHandler()
    mock_context.plan = '{ "components": [{"component": "valid_comp"}] }'
    mock_runner = AsyncMock()
    mock_run_result = MagicMock()
    mock_run_result.status = "completed"
    mock_run_result.run_id = "child_id"
    mock_runner.fan_out.return_value = [mock_run_result]
    mock_context.pipeline_runner = mock_runner

    result = await handler.execute(mock_orchestrate_step, mock_context)
    assert result.status == StepStatus.PASSED

    args, _ = mock_runner.fan_out.call_args
    sub_pipes = args[0]
    assert len(sub_pipes) == 1
    pipe = sub_pipes[0]

    # Assert FR-3: It should target specific actions, and not hardcode simple targets
    assert pipe.name == "auto_valid_comp"

    # Assert FR-4: Must include VALIDATE StepAction implicitly by loading the yaml
    actions = [s.get("action") if isinstance(s, dict) else getattr(s, "action", None) for s in pipe.steps]
    if isinstance(actions[0], str):
        actions_str = actions
    else:
        actions_str = [a.value for a in actions if a is not None]

    assert "validate" in actions_str, "Sub pipeline MUST contain a validation step for FR-4 Compliance"
