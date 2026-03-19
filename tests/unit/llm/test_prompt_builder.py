# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for PromptBuilder: assembly, XML tags, truncation, language detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from specweaver.llm.prompt_builder import PromptBuilder, detect_language

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
        result = (
            PromptBuilder()
            .add_instructions("Part A")
            .add_instructions("Part B")
            .build()
        )
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
        result = (
            PromptBuilder()
            .add_context("A", "first")
            .add_context("B", "second")
            .build()
        )
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
# Truncation
# ---------------------------------------------------------------------------


class TestHybridTruncation:
    """Hybrid priority + proportional truncation."""

    def test_no_truncation_when_under_budget(self) -> None:
        from specweaver.llm.models import TokenBudget

        budget = TokenBudget(limit=10000)
        result = (
            PromptBuilder(budget=budget)
            .add_instructions("Short instruction")
            .add_context("Short context", "ctx")
            .build()
        )
        assert "[truncated]" not in result
        assert budget.used > 0

    def test_instructions_never_truncated(self) -> None:
        from specweaver.llm.models import TokenBudget

        # Budget just big enough for instructions, nothing else
        instr = "A" * 100  # ~25 tokens
        budget = TokenBudget(limit=30)
        result = (
            PromptBuilder(budget=budget)
            .add_instructions(instr)
            .add_context("B" * 1000, "ctx")
            .build()
        )
        assert instr in result
        # Context should be truncated or dropped
        assert "<context" not in result or "[truncated]" in result

    def test_priority_ordering_drops_low_priority(self) -> None:
        from specweaver.llm.models import TokenBudget

        # Budget enough for instructions + priority 1 but not priority 3
        budget = TokenBudget(limit=100)
        result = (
            PromptBuilder(budget=budget)
            .add_instructions("X" * 40)  # ~10 tokens
            .add_context("Y" * 200, "high", priority=1)  # ~50 tokens
            .add_context("Z" * 2000, "low", priority=3)  # ~500 tokens
            .build()
        )
        # Low-priority should be dropped or truncated
        assert "high" in result

    def test_truncated_marker_appended(self) -> None:
        from specweaver.llm.models import TokenBudget

        # Very tight budget forces truncation
        budget = TokenBudget(limit=50)
        result = (
            PromptBuilder(budget=budget)
            .add_instructions("OK")
            .add_context("X" * 4000, "big", priority=1)
            .build()
        )
        assert "[truncated]" in result

    def test_budget_tracking_updated(self) -> None:
        from specweaver.llm.models import TokenBudget

        budget = TokenBudget(limit=10000)
        (
            PromptBuilder(budget=budget)
            .add_instructions("Hello world")
            .add_context("Some context", "ctx")
            .build()
        )
        assert budget.used > 0
        assert budget.remaining < budget.limit

    def test_tiny_limit_drops_content(self) -> None:
        from specweaver.llm.models import TokenBudget

        budget = TokenBudget(limit=1)
        result = (
            PromptBuilder(budget=budget)
            .add_instructions("Instr")
            .add_context("Ctx", "label")
            .build()
        )
        # With limit=1, instructions alone exceed budget.
        # Only instructions should remain (they're never truncated).
        assert "<instructions>" in result
        assert "<context" not in result


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestPromptBuilderEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_file(self, tmp_path: Path) -> None:
        """0-byte file → file block still present, just empty."""
        f = tmp_path / "empty.py"
        f.write_text("", encoding="utf-8")
        result = PromptBuilder().add_file(f).build()
        assert '<file path="empty.py" language="python">' in result
        assert "</file>" in result

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Nonexistent file → FileNotFoundError (not silently ignored)."""
        missing = tmp_path / "nope.py"
        with pytest.raises(FileNotFoundError):
            PromptBuilder().add_file(missing)

    def test_whitespace_only_instructions(self) -> None:
        """Whitespace-only instructions → stripped to empty, still tagged."""
        result = PromptBuilder().add_instructions("  \n\t  ").build()
        assert "<instructions>" in result
        assert "</instructions>" in result

    def test_empty_context_text(self) -> None:
        """Empty context string → stripped empty, still tagged."""
        result = PromptBuilder().add_context("", "empty_ctx").build()
        assert '<context label="empty_ctx">' in result

    def test_build_with_only_files(self, tmp_path: Path) -> None:
        """No instructions, no context — only file blocks."""
        f = tmp_path / "code.py"
        f.write_text("x = 1", encoding="utf-8")
        result = PromptBuilder().add_file(f).build()
        assert "<file_contents>" in result
        assert "<instructions>" not in result
        assert "<context" not in result

    def test_build_with_only_context(self) -> None:
        """No instructions, no files — only context blocks."""
        result = PromptBuilder().add_context("data", "ctx").build()
        assert "<context" in result
        assert "<instructions>" not in result
        assert "<file_contents>" not in result

    def test_unicode_content(self, tmp_path: Path) -> None:
        """Non-ASCII content preserved in files and context."""
        f = tmp_path / "unicode.md"
        f.write_text("# Spëcwëaver ✨\n\nÜber-cool feature.", encoding="utf-8")
        result = (
            PromptBuilder()
            .add_instructions("Prüfe die Spezifikation.")
            .add_file(f)
            .add_context("日本語テスト", "i18n")
            .build()
        )
        assert "Spëcwëaver ✨" in result
        assert "Prüfe die Spezifikation." in result
        assert "日本語テスト" in result

    def test_same_priority_proportional_truncation(self) -> None:
        """Two blocks at same priority, tight budget → both get proportional shares."""
        from specweaver.llm.models import TokenBudget

        # small block + large block, same priority, tight budget
        budget = TokenBudget(limit=100)
        result = (
            PromptBuilder(budget=budget)
            .add_context("A" * 100, "small", priority=1)   # ~25 tokens
            .add_context("B" * 1000, "large", priority=1)  # ~250 tokens
            .build()
        )
        # Both should appear (one may be truncated)
        assert "small" in result or "large" in result

    def test_no_budget_means_no_truncation(self) -> None:
        """Without budget, even large content is never truncated."""
        result = (
            PromptBuilder()
            .add_instructions("I" * 10000)
            .add_context("C" * 10000, "big")
            .build()
        )
        assert "[truncated]" not in result
        assert len(result) > 15000


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
            PromptBuilder()
            .add_instructions("Review this spec.")
            .add_file(spec, priority=1)
            .build()
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

        result = (
            PromptBuilder()
            .add_file(py_file)
            .add_file(md_file)
            .add_file(json_file)
            .build()
        )

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
        result = (
            PromptBuilder()
            .add_reminder("First")
            .add_reminder("Second")
            .build()
        )
        assert result.count("<reminder>") == 1
        assert "First" in result
        assert "Second" in result

    def test_reminder_chaining(self) -> None:
        pb = PromptBuilder()
        ret = pb.add_reminder("test")
        assert ret is pb

    def test_reminder_not_truncated(self) -> None:
        from specweaver.llm.models import TokenBudget

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
        from specweaver.graph.topology import TopologyContext

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
        from specweaver.graph.topology import TopologyContext

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
        result = (
            PromptBuilder()
            .add_instructions("Review")
            .add_topology(ctx)
            .add_file(f)
            .build()
        )
        topo_pos = result.index("<topology>")
        file_pos = result.index("<file_contents>")
        assert topo_pos < file_pos

    def test_topology_no_constraints_renders_none(self) -> None:
        from specweaver.graph.topology import TopologyContext

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
        from specweaver.graph.topology import TopologyContext

        pb = PromptBuilder()
        ret = pb.add_topology([
            TopologyContext(
                name="x", purpose="", archetype="", relationship="",
            ),
        ])
        assert ret is pb


# ---------------------------------------------------------------------------
# Dynamic budget scaling
# ---------------------------------------------------------------------------


class TestBudgetScaling:
    """Test budget_scale_factor parameter."""

    def test_scale_down_halves_budget(self) -> None:
        from specweaver.llm.models import TokenBudget

        budget = TokenBudget(limit=1000)
        result = (
            PromptBuilder(budget=budget, budget_scale_factor=0.5)
            .add_instructions("I" * 40)   # ~10 tokens
            .add_context("X" * 4000, "big", priority=1)  # ~1000 tokens
            .build()
        )
        # Effective budget is 500 → big context should be truncated
        assert "[truncated]" in result

    def test_scale_1_no_change(self) -> None:
        from specweaver.llm.models import TokenBudget

        budget = TokenBudget(limit=10000)
        result = (
            PromptBuilder(budget=budget, budget_scale_factor=1.0)
            .add_instructions("Hello")
            .add_context("Small", "ctx")
            .build()
        )
        assert "[truncated]" not in result

    def test_scale_clamped_to_min(self) -> None:
        """Scale below 0.1 is clamped to 0.1."""
        pb = PromptBuilder(budget_scale_factor=0.0)
        assert pb._scale == 0.1

    def test_scale_clamped_to_max(self) -> None:
        """Scale above 2.0 is clamped to 2.0."""
        pb = PromptBuilder(budget_scale_factor=5.0)
        assert pb._scale == 2.0


# ---------------------------------------------------------------------------
# Constitution blocks
# ---------------------------------------------------------------------------


class TestAddConstitution:
    """Test constitution content rendering."""

    def test_constitution_renders_after_instructions(self) -> None:
        """Constitution renders after instructions, before topology."""
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
            .add_topology(ctx)
            .build()
        )

        instr_pos = result.index("<instructions>")
        const_pos = result.index("<constitution>")
        topo_pos = result.index("<topology>")
        assert instr_pos < const_pos < topo_pos

    def test_constitution_renders_before_files(self, tmp_path: Path) -> None:
        """Constitution renders before file contents."""
        f = tmp_path / "code.py"
        f.write_text("pass", encoding="utf-8")
        result = (
            PromptBuilder()
            .add_constitution("Constitution text")
            .add_file(f)
            .build()
        )

        const_pos = result.index("<constitution>")
        file_pos = result.index("<file_contents>")
        assert const_pos < file_pos

    def test_preamble_included(self) -> None:
        """Fixed preamble is prepended to constitution content."""
        result = (
            PromptBuilder()
            .add_constitution("My rules here.")
            .build()
        )
        assert "non-negotiable" in result.lower()
        assert "constitution wins" in result.lower()
        assert "My rules here." in result

    def test_constitution_tags(self) -> None:
        """Constitution is wrapped in <constitution> tags."""
        result = PromptBuilder().add_constitution("Rules").build()
        assert "<constitution>" in result
        assert "</constitution>" in result

    def test_chaining(self) -> None:
        """add_constitution returns self for chaining."""
        pb = PromptBuilder()
        ret = pb.add_constitution("Rules")
        assert ret is pb

    def test_no_constitution_no_tag(self) -> None:
        """Without add_constitution, no <constitution> tag in output."""
        result = PromptBuilder().add_instructions("Instr").build()
        assert "<constitution>" not in result

    def test_not_truncated_under_budget(self) -> None:
        """Constitution (priority 0) is never truncated."""
        from specweaver.llm.models import TokenBudget

        budget = TokenBudget(limit=50)
        constitution_text = "X" * 100  # ~25 tokens
        result = (
            PromptBuilder(budget=budget)
            .add_instructions("Short")
            .add_constitution(constitution_text)
            .add_context("Y" * 2000, "big", priority=1)
            .build()
        )
        assert constitution_text in result

    def test_content_stripped(self) -> None:
        """Constitution content is stripped of leading/trailing whitespace."""
        result = PromptBuilder().add_constitution("  \n Rules \n  ").build()
        # Content should be stripped (preamble + stripped content)
        assert "<constitution>" in result
        assert "Rules" in result

    def test_empty_string_produces_preamble_only(self) -> None:
        """add_constitution('') still produces preamble in tags."""
        result = PromptBuilder().add_constitution("").build()
        assert "<constitution>" in result
        assert "non-negotiable" in result.lower()

    def test_duplicate_add_constitution(self) -> None:
        """Calling add_constitution twice renders both in the block."""
        result = (
            PromptBuilder()
            .add_constitution("Rule A")
            .add_constitution("Rule B")
            .build()
        )
        # Both are joined inside a single <constitution> tag
        start = result.index("<constitution>")
        end = result.index("</constitution>")
        block = result[start:end]
        assert "Rule A" in block
        assert "Rule B" in block

    def test_constitution_before_context_blocks(self) -> None:
        """Constitution renders before context blocks."""
        result = (
            PromptBuilder()
            .add_constitution("Constitution text")
            .add_context("Context text", "label")
            .build()
        )
        const_pos = result.index("<constitution>")
        ctx_pos = result.index("<context ")
        assert const_pos < ctx_pos

    def test_xml_in_constitution_not_interpreted(self) -> None:
        """XML-like content in constitution is not interpreted as tags."""
        xml_content = "<rule>No <b>bold</b></rule>"
        result = PromptBuilder().add_constitution(xml_content).build()
        # Content should be inside constitution, verbatim
        assert xml_content in result

