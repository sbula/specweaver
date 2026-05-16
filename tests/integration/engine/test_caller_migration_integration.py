# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests verifying complete injection pathways for handlers."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from specweaver.core.flow.engine.models import PipelineStep
from specweaver.core.flow.handlers._profiles import ARBITER, MINIMAL
from specweaver.core.flow.handlers.arbiter import ArbitrateVerdictHandler
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.decompose import DecomposeFeatureHandler


@pytest.fixture
def mock_run_context(tmp_path: Path) -> RunContext:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    context = RunContext(
        run_id="test_run",
        project_path=workspace,
        spec_path=workspace / "docs" / "specs" / "test_spec.md",
    )
    context.llm = AsyncMock()
    return context


@pytest.mark.asyncio
@patch("specweaver.core.flow.handlers.base._build_base_prompt", new_callable=AsyncMock)
async def test_integration_arbitrate_verdict_full_path(mock_build, mock_run_context, tmp_path):
    """I1: Verify Arbiter full path execution injects correct profile and builds properly."""
    # Setup mock to return a builder that returns a fake prompt
    mock_builder = AsyncMock()
    mock_builder.build.return_value = "fake prompt"
    mock_build.return_value = mock_builder

    mock_run_context.llm.generate.return_value = '{"verdict": "code_bug", "spec_clause": "test", "coding_feedback": "test", "scenario_feedback": "test"}'

    handler = ArbitrateVerdictHandler()
    step = PipelineStep(name="arb", module="feature", action="arbitrate", target="verdict", handler="ArbitrateVerdictHandler")

    result = await handler.execute(step, mock_run_context)

    assert result.status.value in ["passed", "failed"]  # It executes without crashing

    # Verify the injection pathway
    mock_build.assert_called_once()
    _args, kwargs = mock_build.call_args
    assert kwargs.get("profile") == ARBITER
    mock_builder.add_context.assert_called()
    mock_builder.build.assert_called_once()
    mock_run_context.llm.generate.assert_called_once()


@pytest.mark.asyncio
@patch("specweaver.core.flow.handlers.decompose.FeatureDecomposer")
@patch("specweaver.core.flow.handlers.base._build_base_prompt", new_callable=AsyncMock)
async def test_integration_decompose_feature_full_path(mock_build, mock_decomposer_class, mock_run_context, tmp_path):
    """I2: Verify Decomposer full path execution injects correct profile and builds properly."""
    mock_builder = AsyncMock()
    mock_build.return_value = mock_builder

    mock_decomposer = mock_decomposer_class.return_value
    from unittest.mock import MagicMock
    mock_plan = MagicMock()
    mock_plan.coverage_score = 1.0
    mock_plan.model_dump.return_value = {"coverage_score": 1.0}
    mock_decomposer.decompose = AsyncMock(return_value=mock_plan)

    # We must ensure the spec path actually exists or mock it
    mock_run_context.spec_path.parent.mkdir(parents=True, exist_ok=True)
    mock_run_context.spec_path.write_text("# Test", encoding="utf-8")

    handler = DecomposeFeatureHandler()
    step = PipelineStep(name="dec", module="feature", action="decompose", target="feature", handler="DecomposeFeatureHandler")

    result = await handler.execute(step, mock_run_context)

    assert result.status.value in ["passed", "failed"]

    # Verify the injection pathway
    mock_build.assert_called_once()
    _args, kwargs = mock_build.call_args
    assert kwargs.get("profile") == MINIMAL

    # Verify the base_prompt was passed to decomposer
    mock_decomposer.decompose.assert_called_once()
    _d_args, d_kwargs = mock_decomposer.decompose.call_args
    assert d_kwargs.get("base_prompt") == mock_builder
