"""E2E test for the scenario_integration.yaml pipeline execution flow."""

import importlib.resources
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from specweaver.core.flow.handlers import RunContext
from specweaver.core.flow.models import PipelineDefinition
from specweaver.core.flow.runner import PipelineRunner
from specweaver.core.flow.state import StepResult, StepStatus

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_e2e_scenario_integration_pipeline_happy_path(tmp_path: Path):
    """Verifies that the runner can load scenario_integration.yaml, execute its steps in order,
    trigger a loop back, and eventually pass.
    """
    pipeline_text = (
        importlib.resources.files("specweaver.workflows.pipelines") / "scenario_integration.yaml"
    ).read_text("utf-8")
    pipeline_def = PipelineDefinition(**yaml.safe_load(pipeline_text))

    project_path = tmp_path / "project"
    project_path.mkdir()
    spec_path = project_path / "specs" / "test_spec.md"
    spec_path.parent.mkdir()
    spec_path.write_text("dummy", encoding="utf-8")

    config = MagicMock()
    config.validation = MagicMock()
    config.validation.overrides = {}

    ctx = RunContext(
        project_path=project_path,
        spec_path=spec_path,
        config=config,
    )
    ctx.llm = AsyncMock()
    ctx.llm.generate.return_value = '{"verdict": "code_bug", "coding_feedback": "fixed"}'

    runner = PipelineRunner(pipeline=pipeline_def, context=ctx)

    visited_actions = []

    loop_counter = {"count": 0}

    async def mock_execute_looping(self, step, context):
        visited_actions.append(step.action.value)
        if step.action.value == "arbitrate":
            loop_counter["count"] += 1
            if loop_counter["count"] == 1:
                # First time: return failed to trigger loop_back
                return StepResult(
                    status=StepStatus.FAILED,
                    error_message="mock failure",
                    started_at="",
                    completed_at="",
                )
            else:
                # Second time: pass
                return StepResult(status=StepStatus.PASSED, started_at="", completed_at="")
        return StepResult(status=StepStatus.PASSED, started_at="", completed_at="")

    class MockHandler:
        async def execute(self, step, context):
            return await mock_execute_looping(self, step, context)

    mock_handler_inst = MockHandler()

    with patch(
        "specweaver.core.flow.runner.StepHandlerRegistry.get", return_value=mock_handler_inst
    ):
        result = await runner.run()

        from specweaver.core.flow.state import RunStatus

        assert result.status == RunStatus.COMPLETED
        # Expect generate -> orchestrate -> validate -> arbitrate -> orchestrate -> validate -> arbitrate
        # total 7 actions visited
        assert visited_actions == [
            "generate",
            "orchestrate",
            "validate",
            "arbitrate",
            "orchestrate",
            "validate",
            "arbitrate",
        ]
