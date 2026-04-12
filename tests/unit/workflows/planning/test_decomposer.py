# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for FeatureDecomposer."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from specweaver.workflows.planning.decomposer import FeatureDecomposer
from specweaver.workflows.planning.decomposition import DecompositionPlan


@pytest.fixture
def mock_llm() -> AsyncMock:
    llm = AsyncMock()
    # Mock LLM generation to return a structured response later
    return llm

@pytest.fixture
def mock_context_provider() -> AsyncMock:
    return AsyncMock()

@pytest.mark.asyncio
async def test_decompose_returns_plan(mock_llm: AsyncMock, mock_context_provider: AsyncMock, tmp_path: Path) -> None:
    """Test that FeatureDecomposer returns a DecompositionPlan using LLM structured output."""
    decomposer = FeatureDecomposer(llm=mock_llm, context_provider=mock_context_provider)

    # Let's mock the LLM response to return a valid JSON-like payload parsing to DecompositionPlan
    # Since we might use the LLM structured output pattern later,
    # we'll just mock the decompose() method's internal LLM generation output
    mock_response = AsyncMock()
    mock_response.text = '{"feature_spec": "path.md", "components": [], "integration_seams": [], "build_sequence": [], "coverage_score": 1.0, "timestamp": "2026-01-01T00:00:00Z"}'
    mock_llm.generate.return_value = mock_response

    # Test executing decompose
    plan = await decomposer.decompose(
        feature_name="test_feature",
        spec_content="Feature Spec Content Dummy"
    )

    assert isinstance(plan, DecompositionPlan)
    assert plan.coverage_score == 1.0
    mock_llm.generate.assert_called_once()

@pytest.mark.asyncio
async def test_decompose_llm_exception(mock_llm: AsyncMock, mock_context_provider: AsyncMock) -> None:
    # FR-4/FR-1 Exception Propagation
    decomposer = FeatureDecomposer(llm=mock_llm, context_provider=mock_context_provider)
    mock_llm.generate.side_effect = Exception("API Connect Timeout")

    with pytest.raises(Exception, match="API Connect Timeout"):
        await decomposer.decompose(feature_name="test", spec_content="spec")

@pytest.mark.asyncio
async def test_decompose_pydantic_validation_error(mock_llm: AsyncMock, mock_context_provider: AsyncMock) -> None:
    # FR-1 Validation formatting
    decomposer = FeatureDecomposer(llm=mock_llm, context_provider=mock_context_provider)

    mock_response = AsyncMock()
    # Missing crucial fields like components, build_sequence
    mock_response.text = '{"feature_spec": "path.md"}'
    mock_llm.generate.return_value = mock_response

    with pytest.raises(ValueError, match="structurally valid"):
        await decomposer.decompose(feature_name="test", spec_content="spec")
