# mypy: ignore-errors
"""Tests for PipelineRunner integration with Prompt Render Profiles."""

from unittest.mock import MagicMock, patch

import pytest

from specweaver.core.flow.engine.models import PipelineDefinition, PipelineStep
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.handlers._profiles import MINIMAL
from specweaver.core.flow.handlers.base import RunContext


@pytest.mark.asyncio
async def test_pipeline_runner_passes_render_profile_to_handler():
    """Verify that PipelineRunner passes step.params down to handlers and they resolve profiles correctly."""

    # 1. Setup a minimal pipeline with a step containing render_profile param
    pipeline = PipelineDefinition(
        id="test_profile_pipeline",
        name="Test Pipeline",
        description="A pipeline to test render profile overrides.",
        version="1.0",
        steps=[
            PipelineStep(
                name="generate_code",
                action="generate",
                target="code",
                params={"render_profile": "MINIMAL"},  # The override!
            )
        ],
    )

    # 2. Setup runner and context
    from pathlib import Path

    context = RunContext(
        workspace_dir=Path("/tmp/workspace"),
        project_path=Path("/tmp/workspace/project"),
        spec_path=Path("/tmp/workspace/project/spec.yaml"),
    )
    context.llm = MagicMock()
    context.context_provider = MagicMock()

    # Create the handler instance we will mock internally
    from specweaver.core.flow.handlers.generation import GenerateCodeHandler

    mock_handler_instance = GenerateCodeHandler()

    from specweaver.core.flow.handlers.registry import StepHandlerRegistry

    registry = StepHandlerRegistry()
    # Override the generate:code handler with our mock instance
    registry.register("generate", "code", mock_handler_instance)

    with (
        patch("specweaver.core.flow.handlers.base._build_base_prompt") as mock_build,
        patch("specweaver.core.flow.handlers.generation.Generator", new=MagicMock(), create=True),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_text", return_value="mock spec"),
    ):
        runner = PipelineRunner(pipeline, context, registry=registry)
        # Execute the pipeline
        await runner.run()

        # Verify the handler called _build_base_prompt
        assert mock_build.called

        # Verify that the handler resolved "MINIMAL" and passed the MINIMAL object
        call_kwargs = mock_build.call_args.kwargs
        assert call_kwargs.get("profile") is MINIMAL
