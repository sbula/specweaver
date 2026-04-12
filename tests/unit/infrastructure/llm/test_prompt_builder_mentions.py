# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for PromptBuilder.add_mentioned_files()."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from specweaver.infrastructure.llm.mention_scanner.models import ResolvedMention
from specweaver.infrastructure.llm.prompt_builder import PromptBuilder


class TestAddMentionedFiles:
    """PromptBuilder.add_mentioned_files() injects auto-detected references."""

    def test_adds_as_priority_4_block(self, tmp_path: Path) -> None:
        f = tmp_path / "auth_spec.md"
        f.write_text("# Auth Spec\nDetails here.")
        mention = ResolvedMention("auth_spec.md", f, "spec")

        builder = PromptBuilder()
        builder.add_mentioned_files([mention])
        prompt = builder.build()

        assert "[auto] auth_spec.md" in prompt
        assert "# Auth Spec" in prompt

    def test_skips_duplicate_already_in_builder(self, tmp_path: Path) -> None:
        f = tmp_path / "handler.py"
        f.write_text("def handle(): pass")
        mention = ResolvedMention("handler.py", f, "code")

        builder = PromptBuilder()
        builder.add_file(f, priority=1)
        builder.add_mentioned_files([mention])
        prompt = builder.build()

        # File should appear only once (from add_file, not add_mentioned_files)
        assert prompt.count("def handle(): pass") == 1

    def test_respects_max_files_cap(self, tmp_path: Path) -> None:
        mentions = []
        for i in range(10):
            f = tmp_path / f"file_{i}.py"
            f.write_text(f"content {i}")
            mentions.append(ResolvedMention(f"file_{i}.py", f, "code"))

        builder = PromptBuilder()
        builder.add_mentioned_files(mentions, max_files=3)
        prompt = builder.build()

        # Only 3 should be present
        count = sum(1 for i in range(10) if f"[auto] file_{i}.py" in prompt)
        assert count == 3

    def test_handles_read_failure(self, tmp_path: Path) -> None:
        # Point to a file that doesn't exist
        f = tmp_path / "missing.py"
        mention = ResolvedMention("missing.py", f, "code")

        builder = PromptBuilder()
        builder.add_mentioned_files([mention])
        prompt = builder.build()

        # Should not crash, and missing file should not appear
        assert "[auto] missing.py" not in prompt

    def test_empty_mentions_no_blocks(self) -> None:
        builder = PromptBuilder()
        builder.add_mentioned_files([])
        prompt = builder.build()
        assert "[auto]" not in prompt
