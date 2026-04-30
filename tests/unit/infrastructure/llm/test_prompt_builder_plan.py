# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for PromptBuilder plan integration and _render_files edge case."""

from __future__ import annotations

from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

# ---------------------------------------------------------------------------
# add_plan() tests
# ---------------------------------------------------------------------------


class TestAddPlan:
    """Test add_plan() method and plan rendering."""

    def test_add_plan_renders_plan_tags(self) -> None:
        """add_plan() renders <plan> tags in the output."""
        result = PromptBuilder().add_plan("File layout: 3 files\nArchitecture: adapter").build()
        assert "<plan>" in result
        assert "</plan>" in result
        assert "File layout: 3 files" in result
        assert "Architecture: adapter" in result

    def test_render_includes_plan_tags(self) -> None:
        """_render output includes <plan> section."""
        result = (
            PromptBuilder()
            .add_instructions("Generate code")
            .add_plan("## Tasks\n1. Create module\n2. Add tests")
            .build()
        )
        assert "<plan>" in result
        assert "Create module" in result

    def test_plan_positioned_between_standards_and_topology(self) -> None:
        """Plan renders after standards, before topology."""
        from specweaver.assurance.graph.topology import TopologyContext

        ctx = [
            TopologyContext(
                name="svc",
                purpose="A service.",
                archetype="pure-logic",
                relationship="direct dependency",
            ),
        ]
        result = (
            PromptBuilder()
            .add_instructions("Instruction")
            .add_standards("PEP 8 required")
            .add_plan("Plan content here")
            .add_topology(ctx)
            .build()
        )

        standards_pos = result.index("<standards>")
        plan_pos = result.index("<plan>")
        topo_pos = result.index("<topology>")
        assert standards_pos < plan_pos < topo_pos

    def test_plan_chaining(self) -> None:
        """add_plan returns self for chaining."""
        pb = PromptBuilder()
        ret = pb.add_plan("some plan")
        assert ret is pb


# ---------------------------------------------------------------------------
# _render_files edge case
# ---------------------------------------------------------------------------


class TestRenderFilesEdge:
    """Test _render_files returns None when no file blocks exist."""

    def test_render_files_returns_none_without_file_blocks(self) -> None:
        """_render_files returns None when no file blocks present."""
        result = (
            PromptBuilder()
            .add_instructions("No files here")
            .add_context("Just context", "ctx")
            .build()
        )
        assert "<file_contents>" not in result

    def test_render_files_static_method_returns_none_for_empty(self) -> None:
        """Calling _render_files with empty list returns None."""
        assert PromptBuilder._render_files([]) is None
