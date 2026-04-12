# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.
from __future__ import annotations

from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

# ---------------------------------------------------------------------------
# Dictator Overrides
# ---------------------------------------------------------------------------


class TestDictatorOverrides:
    """Test human-in-the-loop dictator override blocks."""

    def test_dictator_overrides_rendered_after_instructions(self) -> None:
        """Overrides render immediately after instructions, before other blocks."""
        result = (
            PromptBuilder()
            .add_instructions("Instruction text")
            .add_constitution("Constitution text")
            .add_dictator_overrides(["Fix the indentation", "Remove the print block"])
            .build()
        )

        instr_pos = result.index("<instructions>")
        dictator_pos = result.index("<dictator-overrides>")
        const_pos = result.index("<constitution>")
        assert instr_pos < dictator_pos < const_pos

    def test_empty_overrides_ignored(self) -> None:
        """Empty lists do not render a tag."""
        result = PromptBuilder().add_dictator_overrides([]).build()
        assert "<dictator-overrides>" not in result

    def test_overrides_content_formatting(self) -> None:
        """Overrides are formatted as a bulleted list."""
        result = PromptBuilder().add_dictator_overrides(["Do A", "Do B"]).build()
        assert "<dictator-overrides>" in result
        assert "- Do A" in result
        assert "- Do B" in result

    def test_priority_zero_not_truncated(self) -> None:
        """Dictator overrides must survive extreme truncation."""
        from specweaver.infrastructure.llm.models import TokenBudget

        budget = TokenBudget(limit=10)
        long_txt = "A" * 1000
        result = (
            PromptBuilder(budget=budget)
            .add_dictator_overrides(["MUST Keep this string absolute"])
            .add_context(long_txt, "big", priority=1)
            .build()
        )
        assert "MUST Keep this string absolute" in result

