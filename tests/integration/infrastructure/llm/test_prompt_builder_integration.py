from __future__ import annotations

from specweaver.infrastructure.llm._prompt_profiles import PromptSlot, RenderProfile
from specweaver.infrastructure.llm.models import TokenBudget
from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

FULL = RenderProfile(
    name="full",
    active_slots=frozenset(PromptSlot),
    order=tuple(PromptSlot),
)

MINIMAL = RenderProfile(
    name="minimal",
    active_slots=frozenset([PromptSlot.INSTRUCTIONS, PromptSlot.METADATA, PromptSlot.TOPOLOGY]),
    order=(PromptSlot.INSTRUCTIONS, PromptSlot.METADATA, PromptSlot.TOPOLOGY),
)


def test_profile_truncation_minimal_tight_budget() -> None:
    # I1: MINIMAL profile under tight budget -> only 3 slots compete for space
    budget = TokenBudget(limit=100)
    builder = PromptBuilder(profile=MINIMAL, budget=budget)

    builder.add_instructions("A" * 40)  # ~10 tokens, priority 0
    builder.add_project_metadata(None)  # will skip

    # Normally, context is priority 3.
    # But MINIMAL doesn't include CONTEXT, so it's skipped entirely.
    builder.add_context("B" * 400, "label")  # ~100 tokens, priority 3

    output = builder.build()

    assert "A" * 40 in output
    assert "<context" not in output


def test_profile_truncation_full_priority_dropping() -> None:
    # I2: FULL profile under tight budget -> low-priority slots dropped first
    budget = TokenBudget(limit=100)
    builder = PromptBuilder(profile=FULL, budget=budget)

    builder.add_instructions("X" * 40)  # ~10 tokens, priority 0
    builder.add_context("Y" * 200, "high", priority=1)  # ~50 tokens
    builder.add_context("Z" * 2000, "low", priority=3)  # ~500 tokens

    output = builder.build()

    assert "X" * 40 in output
    assert "high" in output
    # low priority is dropped or truncated
    assert "low" not in output or "[truncated]" in output
