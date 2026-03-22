# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Integration tests connecting Flow Engine handlers to Validation and LLM Adapters."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.flow.handlers import GenerateCodeHandler, RunContext, ValidateSpecHandler
from specweaver.flow.models import PipelineStep, StepAction, StepTarget
from specweaver.flow.state import StepStatus


@pytest.mark.asyncio
async def test_validate_spec_integration_real_rules(tmp_path: Path) -> None:
    """Verifies ValidateSpecHandler integrates effectively with the real validation rules engine."""
    spec_path = tmp_path / "spec.md"
    spec_path.write_text("# Test Spec\n\n## Intent\n\nThis is a test spec.\n")

    # We provide a real ProjectConfig since the validation framework relies on context
    from specweaver.config.settings import LLMSettings, SpecWeaverSettings

    # Create an empty specweaver.toml so config loader finds it
    settings = SpecWeaverSettings(llm=LLMSettings(model="mock-model"))

    context = RunContext(project_path=tmp_path, spec_path=spec_path, settings=settings)

    step = PipelineStep(name="val", action=StepAction.VALIDATE, target=StepTarget.SPEC)
    handler = ValidateSpecHandler()

    # Run the handler WITHOUT mocking _run_validation
    result = await handler.execute(step, context)

    # Wait, the default pipeline might require files to exist or have specific rules.
    # We verify the handler at least successfully runs the engine and catches results.
    assert result.status in (StepStatus.PASSED, StepStatus.FAILED)
    # Because FakeHitlHandler is parked, result.message might be None or a string
    assert "results" in result.output
    assert len(result.output["results"]) > 0


@pytest.mark.asyncio
async def test_handler_adapter_integration(tmp_path: Path) -> None:
    """Verifies that handlers correctly construct prompts and interface with the raw adapter interface."""
    spec_path = tmp_path / "spec.md"
    spec_path.write_text("# Generation Spec\n\n## Intent\n\nDo math.")

    out_dir = tmp_path / "src"
    out_dir.mkdir()

    mock_adapter = MagicMock()
    mock_adapter.generate = AsyncMock(return_value=MagicMock(text="```python\ndef add(): pass\n```", finish_reason=1, parsed=None))

    # Mock a settings object for the handler to use
    mock_config = MagicMock()
    mock_config.project_config.output_dir = out_dir
    mock_config.project_config.source_dir = tmp_path / "src" # Ensure source_dir is set for GitExecutor

    context = RunContext(project_path=tmp_path, spec_path=spec_path, output_dir=out_dir, llm=mock_adapter)

    step = PipelineStep(name="gen", action=StepAction.GENERATE, target=StepTarget.CODE)
    handler = GenerateCodeHandler()

    # Mute Git executor since it requires git repo to be valid
    with patch("specweaver.loom.commons.git.executor.GitExecutor.run", return_value=(0, "", "")):
        result = await handler.execute(step, context)

    # Ensure handler drove adapter.generate effectively
    assert result.status == StepStatus.PASSED
    mock_adapter.generate.assert_called_once()

    # Extract args passed to adapter
    args, _kwargs = mock_adapter.generate.call_args
    messages = args[0]

    # Should have constructed a valid prompt containing spec details
    joined_messages = " ".join([m.content for m in messages if hasattr(m, "content") and m.content])
    assert "Generation Spec" in joined_messages
