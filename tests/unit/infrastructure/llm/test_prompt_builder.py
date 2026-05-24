# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for PromptBuilder: assembly, XML tags, reminders, topology, language detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from specweaver.infrastructure.llm.prompt_builder import PromptBuilder, detect_language

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------


class TestLanguageDetection:
    """Extension-to-language mapping."""

    @pytest.mark.parametrize(
        ("ext", "expected"),
        [
            (".py", "python"),
            (".js", "javascript"),
            (".ts", "typescript"),
            (".md", "markdown"),
            (".yaml", "yaml"),
            (".yml", "yaml"),
            (".json", "json"),
            (".toml", "toml"),
            (".html", "html"),
            (".css", "css"),
            (".sql", "sql"),
            (".sh", "bash"),
            (".rs", "rust"),
            (".go", "go"),
            (".java", "java"),
            (".rb", "ruby"),
            (".xml", "xml"),
        ],
    )
    def test_known_extensions(self, ext: str, expected: str) -> None:
        p = Path(f"test{ext}")
        assert detect_language(p) == expected

    def test_unknown_extension_returns_text(self) -> None:
        assert detect_language(Path("file.xyz")) == "text"

    def test_no_extension_returns_text(self) -> None:
        assert detect_language(Path("Makefile")) == "text"

    def test_case_insensitive(self) -> None:
        assert detect_language(Path("FILE.PY")) == "python"
        assert detect_language(Path("README.MD")) == "markdown"


# ---------------------------------------------------------------------------
# Basic builder
# ---------------------------------------------------------------------------


class TestPromptBuilderBasic:
    """Core assembly without truncation."""

    def test_empty_build(self) -> None:
        """No blocks → empty string."""
        assert PromptBuilder().build() == ""

    def test_instructions_only(self) -> None:
        result = PromptBuilder().add_instructions("Do the thing.").build()
        assert "<instructions>" in result
        assert "Do the thing." in result
        assert "</instructions>" in result

    def test_add_file(self, tmp_path: Path) -> None:
        f = tmp_path / "spec.md"
        f.write_text("# Hello", encoding="utf-8")
        result = PromptBuilder().add_file(f).build()
        assert "<file_contents>" in result
        assert '<file path="spec.md" language="markdown">' in result
        assert "# Hello" in result
        assert "</file>" in result

    def test_add_file_skeleton(self, tmp_path: Path) -> None:
        """skeleton=True delegates to the pure-logic AST parser for python files."""
        f = tmp_path / "code.py"
        f.write_text("def my_func():\n    print('hello world')\n", encoding="utf-8")

        # When skeleton=True, the parser truncates the inner logic into b" ... "
        result = PromptBuilder().add_file(f, skeleton=True).build()
        assert "def my_func():" in result
        assert " ... " in result
        assert "hello world" not in result

    def test_add_context(self) -> None:
        result = PromptBuilder().add_context("Some context", "topology").build()
        assert '<context label="topology">' in result
        assert "Some context" in result
        assert "</context>" in result

    def test_method_chaining(self, tmp_path: Path) -> None:
        f = tmp_path / "code.py"
        f.write_text("pass", encoding="utf-8")
        pb = PromptBuilder()
        result = pb.add_instructions("Review").add_file(f).add_context("ctx", "extra")
        assert result is pb  # chaining returns self

    def test_full_assembly_order(self, tmp_path: Path) -> None:
        """Instructions → files → context."""
        f = tmp_path / "code.py"
        f.write_text("pass", encoding="utf-8")

        result = (
            PromptBuilder()
            .add_instructions("Instruction text")
            .add_file(f, priority=1)
            .add_context("Context text", "topo")
            .build()
        )

        # Order check: instructions before file_contents, file_contents before context
        instr_pos = result.index("<instructions>")
        file_pos = result.index("<file_contents>")
        ctx_pos = result.index('<context label="topo">')
        assert instr_pos < file_pos < ctx_pos


# ---------------------------------------------------------------------------
# XML tag structure
# ---------------------------------------------------------------------------


class TestXMLTagStructure:
    """Verify correct XML tag nesting and attributes."""

    def test_multiple_instructions_merged(self) -> None:
        result = PromptBuilder().add_instructions("Part A").add_instructions("Part B").build()
        assert result.count("<instructions>") == 1
        assert "Part A" in result
        assert "Part B" in result

    def test_multiple_files(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.md"
        f1.write_text("code", encoding="utf-8")
        f2.write_text("docs", encoding="utf-8")

        result = PromptBuilder().add_file(f1).add_file(f2).build()

        assert result.count("<file ") == 2
        assert result.count("<file_contents>") == 1
        assert 'language="python"' in result
        assert 'language="markdown"' in result

    def test_custom_file_label(self, tmp_path: Path) -> None:
        f = tmp_path / "spec.md"
        f.write_text("content", encoding="utf-8")
        result = PromptBuilder().add_file(f, label="specification").build()
        assert 'path="specification"' in result

    def test_multiple_context_blocks(self) -> None:
        result = PromptBuilder().add_context("A", "first").add_context("B", "second").build()
        assert result.count("<context ") == 2
        assert 'label="first"' in result
        assert 'label="second"' in result

    def test_file_priority_minimum_is_1(self, tmp_path: Path) -> None:
        """Files with priority=0 should be clamped to 1."""
        f = tmp_path / "x.py"
        f.write_text("pass", encoding="utf-8")
        pb = PromptBuilder()
        pb.add_file(f, priority=0)
        # Internal check: the block priority should be >= 1
        assert all(b.priority >= 1 for b in pb._blocks if b.kind == "file")


# ---------------------------------------------------------------------------
# Integration: real file on disk
# ---------------------------------------------------------------------------


class TestPromptBuilderIntegration:
    """Integration tests with real files."""

    def test_real_spec_file(self, tmp_path: Path) -> None:
        spec = tmp_path / "component_spec.md"
        spec.write_text(
            "# My Component\n\n## 1. Purpose\n\nDoes things.\n",
            encoding="utf-8",
        )

        result = (
            PromptBuilder().add_instructions("Review this spec.").add_file(spec, priority=1).build()
        )

        assert "<instructions>" in result
        assert "Review this spec." in result
        assert "<file_contents>" in result
        assert "component_spec.md" in result
        assert "# My Component" in result

    def test_multiple_file_types(self, tmp_path: Path) -> None:
        py_file = tmp_path / "main.py"
        md_file = tmp_path / "README.md"
        json_file = tmp_path / "config.json"
        py_file.write_text("def main(): pass", encoding="utf-8")
        md_file.write_text("# Readme", encoding="utf-8")
        json_file.write_text('{"key": "val"}', encoding="utf-8")

        result = PromptBuilder().add_file(py_file).add_file(md_file).add_file(json_file).build()

        assert 'language="python"' in result
        assert 'language="markdown"' in result
        assert 'language="json"' in result

    def test_with_adapter_token_estimation(self, tmp_path: Path) -> None:
        """PB uses adapter.estimate_tokens() when adapter provided."""
        from unittest.mock import MagicMock

        adapter = MagicMock()
        adapter.estimate_tokens.return_value = 42

        f = tmp_path / "x.py"
        f.write_text("pass", encoding="utf-8")

        pb = PromptBuilder(adapter=adapter)
        pb.add_instructions("test")
        pb.add_file(f)
        pb.build()

        # estimate_tokens should have been called
        assert adapter.estimate_tokens.call_count >= 2


# ---------------------------------------------------------------------------
# Trust signals (role parameter)
# ---------------------------------------------------------------------------


class TestFileRole:
    """Test role parameter on add_file for trust signals."""

    def test_role_reference_rendered(self, tmp_path: Path) -> None:
        f = tmp_path / "ref.py"
        f.write_text("x = 1", encoding="utf-8")
        result = PromptBuilder().add_file(f, role="reference").build()
        assert 'role="reference"' in result

    def test_role_target_rendered(self, tmp_path: Path) -> None:
        f = tmp_path / "target.py"
        f.write_text("y = 2", encoding="utf-8")
        result = PromptBuilder().add_file(f, role="target").build()
        assert 'role="target"' in result

    def test_no_role_no_attribute(self, tmp_path: Path) -> None:
        f = tmp_path / "plain.py"
        f.write_text("z = 3", encoding="utf-8")
        result = PromptBuilder().add_file(f).build()
        assert "role=" not in result


# ---------------------------------------------------------------------------
# Reminders
# ---------------------------------------------------------------------------


class TestReminder:
    """Test bottom-of-prompt reminder blocks."""

    def test_reminder_rendered_at_bottom(self, tmp_path: Path) -> None:
        f = tmp_path / "code.py"
        f.write_text("pass", encoding="utf-8")
        result = (
            PromptBuilder()
            .add_instructions("Instruction")
            .add_file(f)
            .add_reminder("Don't forget this!")
            .build()
        )
        assert "<reminder>" in result
        assert "Don't forget this!" in result
        # Reminder should be after all other content
        instr_pos = result.index("<instructions>")
        file_pos = result.index("<file_contents>")
        reminder_pos = result.index("<reminder>")
        assert instr_pos < file_pos < reminder_pos

    def test_multiple_reminders_merged(self) -> None:
        result = PromptBuilder().add_reminder("First").add_reminder("Second").build()
        assert result.count("<reminder>") == 1
        assert "First" in result
        assert "Second" in result

    def test_reminder_chaining(self) -> None:
        pb = PromptBuilder()
        ret = pb.add_reminder("test")
        assert ret is pb

    def test_reminder_not_truncated(self) -> None:
        from specweaver.infrastructure.llm.models import TokenBudget

        budget = TokenBudget(limit=50)
        result = (
            PromptBuilder(budget=budget)
            .add_instructions("Short")
            .add_reminder("This reminder must survive")
            .build()
        )
        assert "This reminder must survive" in result


# ---------------------------------------------------------------------------
# Topology blocks
# ---------------------------------------------------------------------------


class TestAddTopology:
    """Test topology context rendering."""

    def test_topology_renders_xml(self) -> None:
        from specweaver.assurance.graph.topology import TopologyContext

        contexts = [
            TopologyContext(
                name="auth",
                purpose="Authentication service.",
                archetype="adapter",
                relationship="direct dependency",
                constraints=["no-blocking"],
            ),
        ]
        result = PromptBuilder().add_topology(contexts).build()
        assert "<topology>" in result
        assert "auth (direct dependency)" in result
        assert "Authentication service." in result
        assert "archetype=adapter" in result
        assert "constraints=no-blocking" in result
        assert "</topology>" in result

    def test_topology_before_files(self, tmp_path: Path) -> None:
        from specweaver.assurance.graph.topology import TopologyContext

        f = tmp_path / "x.py"
        f.write_text("pass", encoding="utf-8")
        ctx = [
            TopologyContext(
                name="svc",
                purpose="A service.",
                archetype="pure-logic",
                relationship="direct consumer",
            ),
        ]
        result = PromptBuilder().add_instructions("Review").add_topology(ctx).add_file(f).build()
        topo_pos = result.index("<topology>")
        file_pos = result.index("<file_contents>")
        assert topo_pos < file_pos

    def test_topology_no_constraints_renders_none(self) -> None:
        from specweaver.assurance.graph.topology import TopologyContext

        ctx = [
            TopologyContext(
                name="mod",
                purpose="A module.",
                archetype="pure-logic",
                relationship="transitive neighbour",
            ),
        ]
        result = PromptBuilder().add_topology(ctx).build()
        assert "constraints=none" in result

    def test_empty_contexts_no_block(self) -> None:
        result = PromptBuilder().add_topology([]).build()
        assert "<topology>" not in result
        assert result == ""

    def test_topology_chaining(self) -> None:
        from specweaver.assurance.graph.topology import TopologyContext

        pb = PromptBuilder()
        ret = pb.add_topology(
            [
                TopologyContext(
                    name="x",
                    purpose="",
                    archetype="",
                    relationship="",
                ),
            ]
        )
        assert ret is pb
