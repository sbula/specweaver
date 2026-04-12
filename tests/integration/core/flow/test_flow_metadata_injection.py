# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests for ProjectMetadata flowing through Pipeline Handlers."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from specweaver.core.flow._base import RunContext
from specweaver.core.flow._generation import GenerateTestsHandler, PlanSpecHandler
from specweaver.core.flow._review import ReviewSpecHandler
from specweaver.core.flow.models import PipelineStep, StepAction, StepTarget
from specweaver.infrastructure.llm.models import LLMResponse, ProjectMetadata, PromptSafeConfig


@pytest.fixture
def mock_metadata() -> ProjectMetadata:
    return ProjectMetadata(
        project_name="integ-test-metadata",
        archetype="pure-logic",
        language_target="python",
        date_iso="now",
        safe_config=PromptSafeConfig(llm_provider="test", llm_model="test", validation_rules={}),
    )


@pytest.fixture
def dummy_step() -> PipelineStep:
    return PipelineStep(name="dummy", action=StepAction.REVIEW, target=StepTarget.SPEC)


@pytest.mark.asyncio
async def test_metadata_flows_to_reviewer_handler(
    tmp_path: Path, mock_metadata: ProjectMetadata, dummy_step: PipelineStep
) -> None:
    mock_llm = AsyncMock()
    del mock_llm.generate_with_tools
    mock_llm.generate.return_value = LLMResponse(
        text="VERDICT: ACCEPTED\n", model="test", cached=False
    )

    (tmp_path / "test.md").write_text("# Target Spec", encoding="utf-8")
    context = RunContext(
        llm=mock_llm,
        project_path=tmp_path,
        spec_path=tmp_path / "test.md",
        project_metadata=mock_metadata,
    )

    handler = ReviewSpecHandler()
    res = await handler.execute(dummy_step, context)
    assert res.status != "FAILED", res.error_message

    prompt = mock_llm.generate.call_args[0][0][1].content
    assert "<project_metadata>" in prompt
    assert '"project_name": "integ-test-metadata"' in prompt


@pytest.mark.asyncio
async def test_metadata_flows_to_generator_handler(
    tmp_path: Path, mock_metadata: ProjectMetadata, dummy_step: PipelineStep
) -> None:
    mock_llm = AsyncMock()
    del mock_llm.generate_with_tools
    mock_llm.generate.return_value = LLMResponse(
        text="```python\n# code\n```", model="test", cached=False
    )

    (tmp_path / "test.md").write_text("# Target Spec", encoding="utf-8")
    context = RunContext(
        llm=mock_llm,
        project_path=tmp_path,
        spec_path=tmp_path / "test.md",
        test_path=tmp_path / "out.py",
        code_path=tmp_path / "src.py",
        project_metadata=mock_metadata,
    )

    handler = GenerateTestsHandler()
    await handler.execute(dummy_step, context)

    prompt = mock_llm.generate.call_args[0][0][1].content
    assert "<project_metadata>" in prompt
    assert '"project_name": "integ-test-metadata"' in prompt


@pytest.mark.asyncio
async def test_metadata_flows_to_planner_handler(
    tmp_path: Path, mock_metadata: ProjectMetadata, dummy_step: PipelineStep
) -> None:
    mock_llm = AsyncMock()
    del mock_llm.generate_with_tools
    plan_data = {
        "spec_path": "x",
        "spec_name": "x",
        "spec_hash": "x",
        "file_layout": [],
        "architecture": {
            "module_layout": "flat",
            "dependency_direction": "downward",
            "archetype": "plugin",
        },
        "reasoning": "ok",
        "confidence": 100,
    }
    mock_llm.generate.return_value = LLMResponse(
        text=f"<plan>\n{json.dumps(plan_data)}\n</plan>", model="test", cached=False
    )

    (tmp_path / "test.md").write_text("# Target Spec", encoding="utf-8")
    context = RunContext(
        llm=mock_llm,
        project_path=tmp_path,
        spec_path=tmp_path / "test.md",
        project_metadata=mock_metadata,
    )

    handler = PlanSpecHandler()
    await handler.execute(dummy_step, context)

    prompt = mock_llm.generate.call_args[0][0][1].content
    assert "<project_metadata>" in prompt
    assert '"project_name": "integ-test-metadata"' in prompt
