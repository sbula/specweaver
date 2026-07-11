# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests verifying RenderProfile behavior with PromptBuilder truncation."""

import pytest

from specweaver.assurance.graph.topology import TopologyContext
from specweaver.core.flow.handlers._profiles import FULL, MINIMAL
from specweaver.infrastructure.llm.models import ProjectMetadata, TokenBudget
from specweaver.infrastructure.llm.prompt_builder import PromptBuilder


@pytest.fixture
def mock_metadata() -> ProjectMetadata:
    return ProjectMetadata(
        project_name="test-project",
        summary="A test project.",
        archetype="orchestrator",
        language_target="python",
        date_iso="2026-05-13",
        safe_config={
            "llm_model": "test-model",
            "llm_provider": "test-provider",
        },
    )


@pytest.fixture
def mock_topology() -> TopologyContext:
    return TopologyContext(
        name="test_service",
        purpose="Testing.",
        archetype="adapter",
        relationship="direct dependency",
        constraints=[],
    )


def test_profile_truncation_minimal(mock_metadata, mock_topology):
    """[Boundary] MINIMAL profile under a tight budget strictly drops slots correctly.

    The MINIMAL profile has active slots: INSTRUCTIONS, METADATA, TOPOLOGY.
    If we provide a tiny budget, it should truncate or drop TOPOLOGY before METADATA.
    """
    # 50 token budget (~200 chars), small enough to force dropping
    budget = TokenBudget(limit=50)
    builder = PromptBuilder(budget=budget, profile=MINIMAL)

    builder.add_instructions("Decompose this feature. " * 5)  # 120 chars
    builder.add_project_metadata(mock_metadata)  # ~150 chars
    builder.add_topology([mock_topology])  # ~100 chars

    prompt = builder.build()

    # We expect MINIMAL profile to be active.
    assert "<instructions>" in prompt

    # Under tight budget, topology might be dropped entirely
    # It checks priority based truncation in builder
    assert "<topology>" not in prompt


def test_profile_truncation_full(mock_metadata, mock_topology):
    """[Boundary] FULL profile uses priority-based slot dropping when budget is exceeded.

    The FULL profile has all slots active. Priority dropping should ensure
    essential slots remain while low-priority slots drop.
    """
    budget = TokenBudget(limit=400)
    builder = PromptBuilder(budget=budget, profile=FULL)

    builder.add_instructions("Write code for this spec.")
    builder.add_project_metadata(mock_metadata)
    builder.add_topology([mock_topology])
    builder.add_constitution("Follow solid principles.")

    # Add a huge context that forces truncation
    huge_context = "This is a very long string that will eat up the budget." * 50
    builder.add_context(huge_context, "huge_context")

    prompt = builder.build()

    # High priority slots must remain
    assert "<instructions>" in prompt
    assert "<project_metadata>" in prompt
    assert "<topology>" in prompt

    # The context should be truncated
    assert "[truncated]" in prompt
    # Ensure it's bounded by token limit (roughly 400 * 4 = 1600 chars)
    assert len(prompt) <= 1600
