from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.core.flow._base import RunContext
from specweaver.core.flow._dual_pipeline import ArbitrateDualPipelineHandler
from specweaver.core.flow.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.state import StepResult, StepStatus


@pytest.fixture
def run_context():
    ctx = MagicMock(spec=RunContext)
    ctx.run_id = "test_run_123"
    ctx.spec_path = Path("/mock/project/specs/login_spec.md")
    # Need to mock the pipeline_runner and its components
    ctx.pipeline_runner = MagicMock()
    ctx.pipeline_runner._context = ctx
    ctx.pipeline_runner._registry = MagicMock()
    ctx.pipeline_runner._store = MagicMock()
    ctx.pipeline_runner._on_event = MagicMock()
    return ctx


class TestArbitrateDualPipelineHandler:
    @pytest.mark.asyncio
    @patch("specweaver.core.flow.runner.PipelineRunner")
    @patch("importlib.resources.files")
    async def test_fans_out_both_pipelines(self, mock_files, mock_runner_cls, run_context):
        # Mock resource content
        mock_resource = MagicMock()
        mock_resource.joinpath.return_value.read_text.return_value = "name: mock_pipe\nsteps: []"
        mock_files.return_value = mock_resource

        # Mock Runner behavior
        mock_coding_runner = MagicMock()
        mock_coding_runner.run = AsyncMock(
            return_value=StepResult(status=StepStatus.PASSED, started_at="", completed_at="")
        )

        mock_scenario_runner = MagicMock()
        mock_scenario_runner.run = AsyncMock(
            return_value=StepResult(status=StepStatus.PASSED, started_at="", completed_at="")
        )

        # Return them in order of instantiation (first coding, then scenario)
        mock_runner_cls.side_effect = [mock_coding_runner, mock_scenario_runner]

        handler = ArbitrateDualPipelineHandler()
        step = PipelineStep(
            name="test", action=StepAction.ORCHESTRATE, target=StepTarget.COMPONENTS
        )

        result = await handler.execute(step, run_context)

        assert result.status == StepStatus.PASSED
        assert result.output["component"] == "login"

        mock_coding_runner.run.assert_awaited_once_with(parent_run_id="test_run_123")
        mock_scenario_runner.run.assert_awaited_once_with(parent_run_id="test_run_123")

    @pytest.mark.asyncio
    @patch("specweaver.core.flow.runner.PipelineRunner")
    @patch("importlib.resources.files")
    async def test_returns_failed_if_coding_fails(self, mock_files, mock_runner_cls, run_context):
        mock_resource = MagicMock()
        mock_resource.joinpath.return_value.read_text.return_value = "name: mock_pipe\nsteps: []"
        mock_files.return_value = mock_resource

        mock_coding_runner = MagicMock()
        mock_coding_runner.run = AsyncMock(
            return_value=StepResult(
                status=StepStatus.FAILED,
                error_message="Compile error",
                started_at="",
                completed_at="",
            )
        )

        mock_scenario_runner = MagicMock()
        mock_scenario_runner.run = AsyncMock(
            return_value=StepResult(status=StepStatus.PASSED, started_at="", completed_at="")
        )

        mock_runner_cls.side_effect = [mock_coding_runner, mock_scenario_runner]

        handler = ArbitrateDualPipelineHandler()
        step = PipelineStep(
            name="test", action=StepAction.ORCHESTRATE, target=StepTarget.COMPONENTS
        )

        result = await handler.execute(step, run_context)

        assert result.status == StepStatus.FAILED
        assert "Compile error" in result.error_message

    @pytest.mark.asyncio
    @patch("specweaver.core.flow.runner.PipelineRunner")
    @patch("importlib.resources.files")
    async def test_returns_failed_if_scenario_fails(self, mock_files, mock_runner_cls, run_context):
        mock_resource = MagicMock()
        mock_resource.joinpath.return_value.read_text.return_value = "name: mock_pipe\nsteps: []"
        mock_files.return_value = mock_resource

        mock_coding_runner = MagicMock()
        mock_coding_runner.run = AsyncMock(
            return_value=StepResult(status=StepStatus.PASSED, started_at="", completed_at="")
        )

        mock_scenario_runner = MagicMock()
        mock_scenario_runner.run = AsyncMock(
            return_value=StepResult(
                status=StepStatus.FAILED, error_message="LLM Error", started_at="", completed_at=""
            )
        )

        mock_runner_cls.side_effect = [mock_coding_runner, mock_scenario_runner]

        handler = ArbitrateDualPipelineHandler()
        step = PipelineStep(
            name="test", action=StepAction.ORCHESTRATE, target=StepTarget.COMPONENTS
        )

        result = await handler.execute(step, run_context)

        assert result.status == StepStatus.FAILED
        assert "LLM Error" in result.error_message

    def test_build_runner_injects_component_parameter(self, run_context):
        handler = ArbitrateDualPipelineHandler()
        with (
            patch("importlib.resources.files") as mock_files,
            patch("specweaver.core.flow.runner.PipelineRunner") as mock_runner_cls,
        ):
            mock_resource = MagicMock()
            mock_resource.joinpath.return_value.read_text.return_value = "name: mock_pipe\nsteps:\n  - name: dummy\n    action: orchestrate\n    target: components\n    params:\n      existing: val"
            mock_files.return_value = mock_resource

            _ = handler._build_runner("mock_pipe.yaml", "auth", run_context)
            _, kwargs = mock_runner_cls.call_args
            pipeline = kwargs["pipeline"]

            assert pipeline.name == "auto_dual_mock_pipe_auth"
            assert pipeline.steps[0].params["component"] == "auth"
            assert pipeline.steps[0].params["existing"] == "val"

    @pytest.mark.asyncio
    @patch("specweaver.core.flow.runner.PipelineRunner")
    @patch("importlib.resources.files")
    async def test_dual_pipeline_bubbles_exceptions(self, mock_files, mock_runner_cls, run_context):
        mock_resource = MagicMock()
        mock_resource.joinpath.return_value.read_text.return_value = "name: mock_pipe\nsteps:\n  - name: dummy\n    action: orchestrate\n    target: components"
        mock_files.return_value = mock_resource

        mock_coding_runner = MagicMock()
        mock_coding_runner.run = AsyncMock(side_effect=RuntimeError("Simulated runner crash"))
        mock_scenario_runner = MagicMock()
        mock_scenario_runner.run = AsyncMock(
            return_value=StepResult(status=StepStatus.PASSED, started_at="", completed_at="")
        )

        mock_runner_cls.side_effect = [mock_coding_runner, mock_scenario_runner]

        handler = ArbitrateDualPipelineHandler()
        step = PipelineStep(
            name="test", action=StepAction.ORCHESTRATE, target=StepTarget.COMPONENTS
        )

        result = await handler.execute(step, run_context)
        assert result.status == StepStatus.ERROR
        assert "Simulated runner crash" in result.error_message
