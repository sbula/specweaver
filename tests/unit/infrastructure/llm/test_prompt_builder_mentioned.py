# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from pathlib import Path

from specweaver.infrastructure.llm.mention_scanner.models import ResolvedMention
from specweaver.infrastructure.llm.prompt_builder import PromptBuilder


class TestMentionedFilesIntegration:
    """Verify integration of add_mentioned_files with AST skeleton context builder."""

    def test_mentioned_files_skeleton_default(self, tmp_path: Path) -> None:
        """Mentioned files default to skeleton=True to massively save tokens."""
        f = tmp_path / "code_test.py"
        f.write_text("class Logic:\n    def __init__(self):\n        self.a = 1", encoding="utf-8")

        mentions = [ResolvedMention(original="code_test.py", resolved_path=f, kind="code")]

        result = PromptBuilder().add_mentioned_files(mentions).build()
        assert "class Logic:" in result
        assert "def __init__(self):" in result
        assert "self.a = 1" not in result
        assert " ... " in result

    def test_mentioned_files_skeleton_false(self, tmp_path: Path) -> None:
        """Mentioned files retains full text if skeleton=False."""
        f = tmp_path / "code_test.py"
        f.write_text("class Logic:\n    def __init__(self):\n        self.a = 1", encoding="utf-8")

        mentions = [ResolvedMention(original="code_test.py", resolved_path=f, kind="code")]

        result = PromptBuilder().add_mentioned_files(mentions, skeleton=False).build()
        assert "self.a = 1" in result

    def test_mentioned_files_skeleton_reduces_token_count(self, tmp_path: Path) -> None:
        """Verify that the tokens representation scales down due to AST application."""
        f = tmp_path / "heavy.py"
        # Massive inner body block
        f.write_text(
            "class Logic:\n    def load(self):\n" + "        x = 1\n" * 500, encoding="utf-8"
        )
        mentions = [ResolvedMention(original="heavy.py", resolved_path=f, kind="code")]

        # Test full block without skeleton limits
        builder_full = PromptBuilder().add_mentioned_files(mentions, skeleton=False)
        assert len(builder_full._blocks) == 1
        count_full = builder_full._blocks[0].tokens

        # Test scaled down with skeleton limits
        builder_skel = PromptBuilder().add_mentioned_files(mentions, skeleton=True)
        assert len(builder_skel._blocks) == 1
        count_skel = builder_skel._blocks[0].tokens

        # Skeleton tokens should be fundamentally smaller
        assert count_skel < count_full
        assert count_full > 100
        assert count_skel < 50
