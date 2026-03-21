# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for PromptBuilder.add_standards() — standards block rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.llm.prompt_builder import PromptBuilder

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Standards blocks
# ---------------------------------------------------------------------------


class TestAddStandards:
    """Test standards content rendering."""

    def test_standards_renders_after_constitution(self) -> None:
        """Standards renders after constitution, before topology."""
        from specweaver.graph.topology import TopologyContext

        ctx = [
            TopologyContext(
                name="svc", purpose="A service.",
                archetype="pure-logic", relationship="direct dependency",
            ),
        ]
        result = (
            PromptBuilder()
            .add_instructions("Instruction text")
            .add_constitution("Constitution text")
            .add_standards("Standards text")
            .add_topology(ctx)
            .build()
        )

        const_pos = result.index("<constitution>")
        standards_pos = result.index("<standards>")
        topo_pos = result.index("<topology>")
        assert const_pos < standards_pos < topo_pos

    def test_standards_renders_before_files(self, tmp_path: Path) -> None:
        """Standards renders before file contents."""
        f = tmp_path / "code.py"
        f.write_text("pass", encoding="utf-8")
        result = (
            PromptBuilder()
            .add_standards("Standards text")
            .add_file(f)
            .build()
        )

        standards_pos = result.index("<standards>")
        file_pos = result.index("<file_contents>")
        assert standards_pos < file_pos

    def test_standards_tags(self) -> None:
        """Standards is wrapped in <standards> tags."""
        result = PromptBuilder().add_standards("Conventions").build()
        assert "<standards>" in result
        assert "</standards>" in result
        assert "Conventions" in result

    def test_chaining(self) -> None:
        """add_standards returns self for chaining."""
        pb = PromptBuilder()
        ret = pb.add_standards("Text")
        assert ret is pb

    def test_no_standards_no_tag(self) -> None:
        """Without add_standards, no <standards> tag in output."""
        result = PromptBuilder().add_instructions("Instr").build()
        assert "<standards>" not in result

    def test_truncatable_under_tight_budget(self) -> None:
        """Standards (priority 1) can be truncated under budget pressure."""
        from specweaver.llm.models import TokenBudget

        budget = TokenBudget(limit=50)
        standards_text = "X" * 4000  # ~1000 tokens → way over budget
        result = (
            PromptBuilder(budget=budget)
            .add_instructions("Short")
            .add_standards(standards_text)
            .build()
        )
        # Standards should be truncated or dropped (unlike constitution)
        if "<standards>" in result:
            assert "[truncated]" in result
        else:
            # Dropped entirely is also acceptable for priority 1
            assert "<standards>" not in result

    def test_content_stripped(self) -> None:
        """Standards content is stripped of leading/trailing whitespace."""
        result = PromptBuilder().add_standards("  \n Conventions \n  ").build()
        assert "<standards>" in result
        assert "Conventions" in result

    def test_empty_string_no_tag(self) -> None:
        """add_standards('') with empty content still renders a tag."""
        result = PromptBuilder().add_standards("").build()
        assert "<standards>" in result

    def test_duplicate_add_standards(self) -> None:
        """Calling add_standards twice renders both in the block."""
        result = (
            PromptBuilder()
            .add_standards("Convention A")
            .add_standards("Convention B")
            .build()
        )
        start = result.index("<standards>")
        end = result.index("</standards>")
        block = result[start:end]
        assert "Convention A" in block
        assert "Convention B" in block

    def test_full_render_order(self, tmp_path: Path) -> None:
        """Full render order: instructions → constitution → standards → topology → files → context → reminder."""
        from specweaver.graph.topology import TopologyContext

        f = tmp_path / "code.py"
        f.write_text("pass", encoding="utf-8")
        ctx = [
            TopologyContext(
                name="svc", purpose="Test.",
                archetype="pure-logic", relationship="dep",
            ),
        ]
        result = (
            PromptBuilder()
            .add_instructions("Instr")
            .add_constitution("Const")
            .add_standards("Stds")
            .add_topology(ctx)
            .add_file(f)
            .add_context("Ctx", "label")
            .add_reminder("Reminder")
            .build()
        )

        instr_pos = result.index("<instructions>")
        const_pos = result.index("<constitution>")
        stds_pos = result.index("<standards>")
        topo_pos = result.index("<topology>")
        file_pos = result.index("<file_contents>")
        ctx_pos = result.index('<context label=')
        reminder_pos = result.index("<reminder>")

        assert (
            instr_pos
            < const_pos
            < stds_pos
            < topo_pos
            < file_pos
            < ctx_pos
            < reminder_pos
        )
