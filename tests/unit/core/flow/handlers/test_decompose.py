# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for decompose step handlers."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.decompose import DecomposeFeatureHandler, OrchestrateComponentsHandler
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus


@pytest.fixture
def mock_context(tmp_path: Path) -> RunContext:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return RunContext(
        run_id="test_run",
        project_path=workspace,
        spec_path=workspace / "docs" / "specs" / "test_feature_spec.md",
    )


@pytest.fixture
def mock_step() -> PipelineStep:
    return PipelineStep(
        name="decompose_step", action=StepAction.DECOMPOSE, target=StepTarget.FEATURE, params={}
    )


@pytest.mark.asyncio
async def test_decompose_feature_handler_success(
    mock_context: RunContext, mock_step: PipelineStep, tmp_path: Path
) -> None:
    # Setup feature spec
    specs_dir = mock_context.project_path / "docs" / "specs" / "features"
    specs_dir.mkdir(parents=True)
    spec_path = specs_dir / "test_feature_spec.md"
    spec_path.write_text("# Test Feature")
    mock_context.spec_path = spec_path

    mock_step.params = {"feature_name": "test_feature", "output_dir": str(specs_dir)}

    with patch("specweaver.core.flow.handlers.decompose.FeatureDecomposer") as mock_decomposer_cls:
        mock_decomposer = AsyncMock()
        mock_plan = MagicMock()
        mock_plan.coverage_score = 1.0  # 100% coverage
        mock_plan.model_dump.return_value = {"coverage_score": 1.0}
        mock_decomposer.decompose.return_value = mock_plan
        mock_decomposer_cls.return_value = mock_decomposer

        handler = DecomposeFeatureHandler()
        result = await handler.execute(mock_step, mock_context)

        assert result.status == StepStatus.PASSED
        mock_decomposer.decompose.assert_called_once()
        assert result.output.get("coverage_score") == 1.0


@pytest.mark.asyncio
async def test_decompose_feature_handler_coverage_fail(
    mock_context: RunContext, mock_step: PipelineStep, tmp_path: Path
) -> None:
    specs_dir = mock_context.project_path / "docs" / "specs" / "features"
    specs_dir.mkdir(parents=True)
    spec_path = specs_dir / "test_feature_spec.md"
    spec_path.write_text("# Test Feature")
    mock_context.spec_path = spec_path

    mock_step.params = {"feature_name": "test_feature"}

    with patch("specweaver.core.flow.handlers.decompose.FeatureDecomposer") as mock_decomposer_cls:
        mock_decomposer = AsyncMock()
        mock_plan = MagicMock()
        mock_plan.coverage_score = 0.5  # FR-5 bounds fail
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
        params={},
    )


@pytest.mark.asyncio
@patch("specweaver.core.flow.engine.runner.PipelineRunner")
async def test_orchestrate_components_handler_success_dag(
    mock_pipeline_runner_cls: MagicMock,
    mock_context: RunContext,
    mock_orchestrate_step: PipelineStep,
    tmp_path: Path,
) -> None:
    # Context now should have a 'plan' JSON string pre-loaded by previous HITL review step
    import json

    mock_plan_dict = {
        "feature_spec": "path.md",
        "components": [
            {
                "component": "service_a",
                "exists": True,
                "change_nature": "behavior",
                "description": "Update",
                "proposed_dal": "DAL_B",
                "dependencies": [],
                "target_modules": ["service_a"],
                "confidence": 100,
            },
            {
                "component": "service_b",
                "exists": False,
                "change_nature": "new",
                "description": "Create",
                "proposed_dal": "DAL_C",
                "dependencies": ["service_a"],
                "target_modules": ["service_b"],
                "confidence": 100,
            },
        ],
        "integration_seams": [],
        "build_sequence": ["service_a", "service_b"],
        "coverage_score": 1.0,
        "timestamp": "2026-01-01T00:00:00Z",
    }
    mock_context.plan = json.dumps(mock_plan_dict)

    mock_runner_instance = AsyncMock()
    mock_run_result = MagicMock()
    mock_run_result.status = "completed"
    mock_run_result.run_id = "child_123"
    mock_runner_instance.run.return_value = mock_run_result
    mock_pipeline_runner_cls.return_value = mock_runner_instance

    # To satisfy not None check in handler
    mock_context.pipeline_runner = MagicMock()

    # Provide a dummy TopologyGraph
    mock_topology = MagicMock()
    # No physical collisions
    mock_topology.impact_of.side_effect = lambda module: {module}
    mock_context.topology = mock_topology

    handler = OrchestrateComponentsHandler()
    result = await handler.execute(mock_orchestrate_step, mock_context)

    assert result.status == StepStatus.PASSED, f"Failed: {result.error_message}"
    assert len(result.output["sub_runs"]) == 2

    # runner.run should be called twice (once for service_a, once for service_b)
    assert mock_runner_instance.run.call_count == 2
    # Ensure it was passed parent_run_id as kwargs
    _, kwargs = mock_runner_instance.run.call_args
    assert kwargs.get("parent_run_id") == "test_run"


@pytest.mark.asyncio
async def test_orchestrate_components_handler_empty_plan(
    mock_orchestrate_step: PipelineStep, mock_context: RunContext
) -> None:
    handler = OrchestrateComponentsHandler()
    mock_context.plan = None
    result = await handler.execute(mock_orchestrate_step, mock_context)
    assert result.status == StepStatus.FAILED
    assert "No DecompositionPlan" in str(result.error_message)


@pytest.mark.asyncio
async def test_orchestrate_components_handler_missing_runner(
    mock_orchestrate_step: PipelineStep, mock_context: RunContext
) -> None:
    handler = OrchestrateComponentsHandler()
    mock_context.plan = '{ "components": [{"component": "valid"}] }'
    mock_context.pipeline_runner = None
    result = await handler.execute(mock_orchestrate_step, mock_context)
    assert result.status == StepStatus.FAILED
    assert "pipeline_runner not found" in str(result.error_message)


@pytest.mark.asyncio
@patch("specweaver.core.flow.engine.runner.PipelineRunner")
async def test_orchestrate_components_handler_child_failure(
    mock_pipeline_runner_cls: MagicMock,
    mock_orchestrate_step: PipelineStep,
    mock_context: RunContext,
) -> None:
    handler = OrchestrateComponentsHandler()
    mock_context.plan = '{ "components": [{"component": "valid_a", "dependencies": [], "target_modules": ["a"]}, {"component": "valid_b", "dependencies": ["valid_a"], "target_modules": ["b"]}] }'

    mock_runner_instance = AsyncMock()
    # Mock a failed sub run for the first one, meaning valid_b should starve
    mock_run_result = MagicMock()
    mock_run_result.status = StepStatus.FAILED
    mock_run_result.run_id = "failed_child"
    mock_runner_instance.run.return_value = mock_run_result
    mock_pipeline_runner_cls.return_value = mock_runner_instance

    mock_context.pipeline_runner = MagicMock()

    mock_topology = MagicMock()
    mock_topology.impact_of.return_value = set()
    mock_context.topology = mock_topology

    result = await handler.execute(mock_orchestrate_step, mock_context)
    assert result.status == StepStatus.FAILED
    # Should only be called once because valid_b is starved (FR-6)
    assert mock_runner_instance.run.call_count == 1
    assert "Cascading failure" in str(result.error_message) or "pipeline" in str(
        result.error_message
    )


@pytest.mark.asyncio
async def test_orchestrate_components_malicious_name(
    mock_orchestrate_step: PipelineStep, mock_context: RunContext
) -> None:
    handler = OrchestrateComponentsHandler()
    mock_context.plan = '{ "components": [{"component": "../../../etc/shadow"}] }'
    mock_context.pipeline_runner = MagicMock()
    result = await handler.execute(mock_orchestrate_step, mock_context)
    assert result.status == StepStatus.FAILED
    assert "Invalid or malicious component name" in str(result.error_message)


@pytest.mark.asyncio
@patch("specweaver.core.flow.engine.runner.PipelineRunner")
async def test_orchestrate_loads_new_feature_yaml(
    mock_pipeline_runner_cls: MagicMock,
    mock_orchestrate_step: PipelineStep,
    mock_context: RunContext,
) -> None:
    # FR-3 / FR-4 Verification
    handler = OrchestrateComponentsHandler()
    mock_context.plan = '{ "components": [{"component": "valid_comp"}] }'

    mock_runner_instance = AsyncMock()
    mock_run_result = MagicMock()
    mock_run_result.status = "completed"
    mock_run_result.run_id = "child_id"
    mock_runner_instance.run.return_value = mock_run_result
    mock_pipeline_runner_cls.return_value = mock_runner_instance

    mock_context.pipeline_runner = MagicMock()

    result = await handler.execute(mock_orchestrate_step, mock_context)
    assert result.status == StepStatus.PASSED

    assert mock_pipeline_runner_cls.call_count == 1
    pipe_dict = mock_pipeline_runner_cls.call_args[1].get("pipeline")

    # Assert FR-3: It should target specific actions, and not hardcode simple targets
    assert pipe_dict.name == "auto_valid_comp"

    # Assert FR-4: Must include VALIDATE StepAction implicitly by loading the yaml
    actions = [
        s.get("action") if isinstance(s, dict) else getattr(s, "action", None)
        for s in pipe_dict.steps
    ]
    if isinstance(actions[0], str):
        actions_str = actions
    else:
        actions_str = [a.value for a in actions if a is not None]

    assert "validate" in actions_str, (
        "Sub pipeline MUST contain a validation step for FR-4 Compliance"
    )


@pytest.mark.asyncio
@patch("specweaver.core.flow.engine.runner.PipelineRunner")
async def test_orchestrate_components_preserves_params_gap_1(
    mock_pipeline_runner_cls: MagicMock,
    mock_orchestrate_step: PipelineStep,
    mock_context: RunContext,
) -> None:
    """Gap 1: Preserves existing `params` dict keys when injecting component target."""
    handler = OrchestrateComponentsHandler()
    mock_context.plan = '{ "components": [{"component": "valid_a"}] }'
    mock_runner_instance = AsyncMock()
    mock_success = MagicMock(status=StepStatus.PASSED, run_id="child")
    mock_runner_instance.run.return_value = mock_success
    mock_pipeline_runner_cls.return_value = mock_runner_instance
    mock_context.pipeline_runner = MagicMock()

    mock_topology = MagicMock()
    mock_topology.impact_of.return_value = set()
    mock_context.topology = mock_topology

    # Inject YAML with step containing existing pre-set params
    fake_yaml = {
        "name": "test",
        "steps": [
            {"name": "s1", "action": "generate", "target": "code", "params": {"existing": True}}
        ],
    }
    with patch("yaml.safe_load", return_value=fake_yaml), patch("importlib.resources.files"):
        await handler.execute(mock_orchestrate_step, mock_context)

    # Verify the pipe definition
    pipe_dict = mock_pipeline_runner_cls.call_args[1].get("pipeline")
    params = pipe_dict.steps[0].params
    assert params["existing"] is True
    assert params["component"] == "valid_a"


@pytest.mark.asyncio
@patch("specweaver.core.flow.engine.runner.PipelineRunner")
async def test_orchestrate_components_handles_gate_gaps_2_3_4(
    mock_pipeline_runner_cls: MagicMock,
    mock_orchestrate_step: PipelineStep,
    mock_context: RunContext,
) -> None:
    """Gaps 2, 3, 4: Safely handles missing/malformed gates without attribute errors, and does not strip non-join gates."""
    handler = OrchestrateComponentsHandler()
    mock_context.plan = '{ "components": [{"component": "valid_a"}] }'
    mock_runner_instance = AsyncMock()
    mock_success = MagicMock(status=StepStatus.PASSED, run_id="child")
    mock_runner_instance.run.return_value = mock_success
    mock_pipeline_runner_cls.return_value = mock_runner_instance
    mock_context.pipeline_runner = MagicMock()
    mock_context.topology = MagicMock(impact_of=MagicMock(return_value=set()))

    # s1: No gate (Gap 2)
    # s3: Non-JOIN hitl dict gate (Gap 4)
    # s4: valid JOIN gate string
    fake_yaml = {
        "name": "test",
        "steps": [
            {"name": "s1", "action": "generate", "target": "code"},
            {"name": "s3", "action": "generate", "target": "code", "gate": {"type": "hitl"}},
            {
                "name": "s4",
                "action": "generate",
                "target": "code",
                "gate": {"type": "join"},
            },  # Only one that matches correctly
        ],
    }

    with patch("yaml.safe_load", return_value=fake_yaml), patch("importlib.resources.files"):
        await handler.execute(mock_orchestrate_step, mock_context)

    # call_args_list[0] is the fan_out runner. call_args_list[1] is Wave N.
    pipe_dict = mock_pipeline_runner_cls.call_args_list[0][1].get("pipeline")

    # fan_out pipe should explicitly retain s1, s3. Since it strips s4, len == 2.
    assert len(pipe_dict.steps) == 2
    assert pipe_dict.steps[0].name == "s1"
    assert pipe_dict.steps[1].name == "s3"


@pytest.mark.asyncio
@patch("specweaver.core.flow.engine.runner.PipelineRunner")
async def test_orchestrate_components_skips_wave_n_if_failed_gap_5(
    mock_pipeline_runner_cls: MagicMock,
    mock_orchestrate_step: PipelineStep,
    mock_context: RunContext,
) -> None:
    """Gap 5: Ensures Wave N is STRICTLY skipped if a primary `fan_out` pipeline crashed."""
    handler = OrchestrateComponentsHandler()
    mock_context.plan = '{ "components": [{"component": "valid_a"}] }'
    mock_runner_instance = AsyncMock()
    mock_fail = MagicMock(status=StepStatus.FAILED, run_id="child")
    mock_runner_instance.run.return_value = mock_fail
    mock_pipeline_runner_cls.return_value = mock_runner_instance
    mock_context.pipeline_runner = MagicMock()
    mock_context.topology = MagicMock(impact_of=MagicMock(return_value=set()))

    # Even right though there's a JOIN step, since the fan_out failed, Wave N must not run!
    fake_yaml = {
        "name": "test",
        "steps": [
            {"name": "fake", "action": "generate", "target": "code", "gate": {"type": "join"}}
        ],
    }
    with patch("yaml.safe_load", return_value=fake_yaml), patch("importlib.resources.files"):
        result = await handler.execute(mock_orchestrate_step, mock_context)

    assert result.status == StepStatus.FAILED
    assert "Cascading failure:" in str(result.error_message)
    # Runner is only called ONCE (for the failed fan_out pipeline). Wave N is skipped.
    assert mock_runner_instance.run.call_count == 1


@pytest.mark.asyncio
@patch("specweaver.core.flow.engine.runner.PipelineRunner")
async def test_orchestrate_components_skips_wave_n_if_empty_gap_6(
    mock_pipeline_runner_cls: MagicMock,
    mock_orchestrate_step: PipelineStep,
    mock_context: RunContext,
) -> None:
    """Gap 6: Ensures Wave N is STRICTLY skipped if no JOIN steps exist."""
    handler = OrchestrateComponentsHandler()
    mock_context.plan = '{ "components": [{"component": "valid_a"}] }'
    mock_runner_instance = AsyncMock()
    mock_success = MagicMock(status=StepStatus.PASSED, run_id="child")
    mock_runner_instance.run.return_value = mock_success
    mock_pipeline_runner_cls.return_value = mock_runner_instance
    mock_context.pipeline_runner = MagicMock()
    mock_context.topology = MagicMock(impact_of=MagicMock(return_value=set()))

    # Zero JOIN steps
    fake_yaml = {
        "name": "test",
        "steps": [{"name": "fake", "action": "generate", "target": "code"}],
    }
    with patch("yaml.safe_load", return_value=fake_yaml), patch("importlib.resources.files"):
        result = await handler.execute(mock_orchestrate_step, mock_context)

    assert result.status == StepStatus.PASSED
    # Runner is only called ONCE (for the successful fan_out). Wave N is skipped.
    assert mock_runner_instance.run.call_count == 1


@pytest.mark.asyncio
@patch("specweaver.core.flow.engine.runner.PipelineRunner")
async def test_orchestrate_components_wave_n_crash_gap_7(
    mock_pipeline_runner_cls: MagicMock,
    mock_orchestrate_step: PipelineStep,
    mock_context: RunContext,
) -> None:
    """Gap 7: Wave N cascade failure trap properly returns FAILED if it internally faults."""
    handler = OrchestrateComponentsHandler()
    mock_context.plan = '{ "components": [{"component": "valid_a"}] }'
    mock_runner_instance = AsyncMock()

    # We must mock that it SUCCEEDS the fan_out wave, but FAILS the wave_n synchronous execution.
    mock_success = MagicMock(status=StepStatus.PASSED, run_id="fan_out_child")
    mock_fail = MagicMock(status=StepStatus.FAILED, run_id="wave_n_child")

    mock_runner_instance.run.side_effect = [mock_success, mock_fail]
    mock_pipeline_runner_cls.return_value = mock_runner_instance
    mock_context.pipeline_runner = MagicMock()
    mock_context.topology = MagicMock(impact_of=MagicMock(return_value=set()))

    fake_yaml = {
        "name": "test",
        "steps": [
            {"name": "fake", "action": "generate", "target": "code", "gate": {"type": "join"}}
        ],
    }
    with patch("yaml.safe_load", return_value=fake_yaml), patch("importlib.resources.files"):
        result = await handler.execute(mock_orchestrate_step, mock_context)

    assert result.status == StepStatus.FAILED
    assert "Cascading failure: Wave N deferred join execution failed" in str(result.error_message)
    assert mock_runner_instance.run.call_count == 2
