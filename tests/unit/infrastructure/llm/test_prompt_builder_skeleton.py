from pathlib import Path
from unittest.mock import patch

from specweaver.infrastructure.llm.mention_scanner.models import ResolvedMention
from specweaver.infrastructure.llm.prompt_builder import PromptBuilder


def test_prompt_builder_init_skeleton_files() -> None:
    """Story 4: Configuration explicitly maps skeleton_files dict properly."""
    skeleton_map = {"c:/test/file.py": "def test(): pass"}
    builder = PromptBuilder(skeleton_files=skeleton_map)
    assert builder._skeleton_files == skeleton_map


def test_prompt_builder_add_file_skips_native_parsing(tmp_path: Path) -> None:
    """Story 5: Appending target logic correctly bypasses native execution natively."""
    file_path = tmp_path / "foo.py"
    file_path.write_text("def raw_code(): return 1")

    # Pre-condensed
    skeleton_map = {str(file_path): "def raw_code(): pass"}
    builder = PromptBuilder(skeleton_files=skeleton_map)

    with patch("specweaver.infrastructure.llm._skeleton.extract_ast_skeleton") as mock_extract:
        builder.add_file(file_path, skeleton=True)
        prompt = builder.build()

        # Should NOT call native extraction
        mock_extract.assert_not_called()
        assert "def raw_code(): pass" in prompt


def test_prompt_builder_add_mentioned_files_uses_dict(tmp_path: Path) -> None:
    """Story 6: Bulk-dependency mention hydration prioritizes structural boundaries."""
    f1 = tmp_path / "dep1.py"
    f2 = tmp_path / "dep2.py"
    f1.write_text("import os")
    f2.write_text("import sys")

    mentions = [
        ResolvedMention(original="dep1", resolved_path=f1, kind="import"),
        ResolvedMention(original="dep2", resolved_path=f2, kind="import"),
    ]

    skeleton_map = {str(f1): "# skeleton 1", str(f2): "# skeleton 2"}

    builder = PromptBuilder(skeleton_files=skeleton_map)
    with patch("specweaver.infrastructure.llm._skeleton.extract_ast_skeleton") as mock_extract:
        builder.add_mentioned_files(mentions)
        prompt = builder.build()

        mock_extract.assert_not_called()
        assert "# skeleton 1" in prompt
        assert "# skeleton 2" in prompt
