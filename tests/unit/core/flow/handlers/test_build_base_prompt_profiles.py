from __future__ import annotations

import logging
import warnings
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.core.flow.handlers._profiles import ARBITER, FULL, INTERACTIVE, MINIMAL
from specweaver.core.flow.handlers.base import RunContext, _build_base_prompt
from specweaver.infrastructure.llm._prompt_profiles import PromptSlot
from specweaver.infrastructure.llm.models import ProjectMetadata, PromptSafeConfig


@pytest.fixture
def mock_db():
    db = MagicMock()
    session = AsyncMock()
    session_scope = AsyncMock()
    session_scope.__aenter__.return_value = session
    db.async_session_scope.return_value = session_scope
    return db


@pytest.fixture
def run_context(mock_db):
    metadata = ProjectMetadata(
        project_name="fake_project",
        archetype="generic",
        language_target="python",
        date_iso="2026-05-09",
        safe_config=PromptSafeConfig(llm_provider="fake", llm_model="fake"),
    )
    return RunContext(
        project_path=Path("/tmp/fake_project"),
        spec_path=Path("/tmp/fake_project/spec.yaml"),
        constitution="Always be honest",
        standards="Use type hints",
        db=mock_db,
        project_metadata=metadata,
        parsers={},
    )


@pytest.mark.asyncio
@patch("specweaver.workspace.memory.hydrator.MemoryHydrator")
async def test_build_base_prompt_with_profile_full(mock_hydrator_class, run_context):
    # H1
    mock_hydrator = mock_hydrator_class.return_value
    mock_result = MagicMock()
    mock_result.task_count = 1
    mock_result.token_estimate = 100
    mock_result.format_prompt_block.return_value = "Memory Tasks"
    mock_hydrator.hydrate = AsyncMock(return_value=mock_result)

    builder = await _build_base_prompt(run_context, "Instr", profile=FULL)
    output = builder.build()
    
    assert "<constitution>" in output
    assert "<standards>" in output
    assert "<agent_memory>" in output


@pytest.mark.asyncio
@patch("specweaver.workspace.memory.hydrator.MemoryHydrator")
async def test_build_base_prompt_with_profile_interactive(mock_hydrator_class, run_context):
    # H2
    mock_hydrator = mock_hydrator_class.return_value
    mock_result = MagicMock()
    mock_result.task_count = 1
    mock_result.token_estimate = 100
    mock_result.format_prompt_block.return_value = "Memory Tasks"
    mock_hydrator.hydrate = AsyncMock(return_value=mock_result)

    builder = await _build_base_prompt(run_context, "Instr", profile=INTERACTIVE)
    output = builder.build()

    assert "<constitution>" not in output
    assert "<standards>" not in output
    assert "<agent_memory>" in output


@pytest.mark.asyncio
async def test_build_base_prompt_with_profile_arbiter(run_context):
    # H3
    builder = await _build_base_prompt(run_context, "Instr", profile=ARBITER)
    output = builder.build()
    assert "<constitution>" not in output
    assert "<standards>" not in output
    assert "<project_metadata>" not in output


@pytest.mark.asyncio
async def test_build_base_prompt_with_profile_minimal(run_context):
    # H4
    builder = await _build_base_prompt(run_context, "Instr", profile=MINIMAL)
    output = builder.build()
    assert "<constitution>" not in output
    assert "<standards>" not in output
    assert "<agent_memory>" not in output


@pytest.mark.asyncio
async def test_build_base_prompt_deprecated_include_rules(run_context):
    # H5
    with pytest.warns(DeprecationWarning, match="include_rules is deprecated"):
        builder = await _build_base_prompt(run_context, "Instr", include_rules=False)
    output = builder.build()
    assert "<constitution>" not in output


@pytest.mark.asyncio
async def test_build_base_prompt_profile_overrides_include_rules(run_context):
    # H6
    with pytest.warns(DeprecationWarning, match="Both profile and include_rules were passed"):
        builder = await _build_base_prompt(run_context, "Instr", profile=MINIMAL, include_rules=False)
    output = builder.build()
    assert "<constitution>" not in output


@pytest.mark.asyncio
@patch("specweaver.workspace.memory.hydrator.MemoryHydrator")
async def test_build_base_prompt_memory_skipped_when_slot_inactive(mock_hydrator_class, run_context):
    # H7
    builder = await _build_base_prompt(run_context, "Instr", profile=MINIMAL)
    output = builder.build()
    assert "<agent_memory>" not in output
    run_context.db.async_session_scope.assert_not_called()


@pytest.mark.asyncio
@patch("specweaver.workspace.memory.hydrator.MemoryHydrator")
async def test_build_base_prompt_memory_hydrated_when_slot_active(mock_hydrator_class, run_context):
    # H8
    mock_hydrator = mock_hydrator_class.return_value
    mock_result = MagicMock()
    mock_result.task_count = 1
    mock_result.token_estimate = 100
    mock_result.format_prompt_block.return_value = "Mem Content"
    mock_hydrator.hydrate = AsyncMock(return_value=mock_result)

    builder = await _build_base_prompt(run_context, "Instr", profile=FULL)
    mem_blocks = [b for b in builder._blocks if b.kind == "agent_memory"]
    assert len(mem_blocks) == 1
    assert mem_blocks[0].text == "Mem Content"


@pytest.mark.asyncio
async def test_build_base_prompt_memory_slot_active_but_db_none(run_context):
    # H9
    run_context.db = None
    builder = await _build_base_prompt(run_context, "Instr", profile=FULL)
    output = builder.build()
    assert "<agent_memory>" not in output
