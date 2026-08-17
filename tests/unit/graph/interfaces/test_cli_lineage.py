# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw lineage tag`: adopting an untagged file, and recording who wrote it.

Proves: B-SENS-01 FR-6

Cited under `specweaver-dev` §3.2c, from `INT-US-15-SF01-MIG`. Mutant: `model_id=author` replaced by a
constant, so a human edit is logged under the wrong provenance — 6 fail.

FR-6 exists so that manual code is not a hole in the lineage graph: the tag is injected and the event
records `model_id=human`. Provenance that always says the same thing carries no information, which is
what the mutant demonstrates — the row is still written, still complete, and no longer true.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from specweaver.graph.interfaces.cli import lineage_app as app
from specweaver.graph.lineage.scanner import check_lineage

runner = CliRunner()

#: Real uuid4s. A lineage id is always `str(uuid.uuid4())` in production and the shared
#: `extract_artifact_uuid` validates that shape — the made-up ids these fixtures used
#: (`filebase-uuid-999`, `existing-uuid-456`) passed only while the CLI hand-rolled
#: `line.split(": ")[1]`, which accepted anything after the colon.
_FILE_UUID = "9c4f1a2b-7d3e-4c5a-8b6f-1e2d3c4b5a60"
_EXISTING_UUID = "5b8e0d7c-2a41-4f6b-9c3d-7e1a2b4c6d80"


def test_check_lineage_empty_dir(tmp_path):
    """Empty directory should return no orphans."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    orphans = check_lineage(src_dir)
    assert orphans == []


def test_check_lineage_fully_tagged(tmp_path):
    """Files with # sw-artifact: tag are not orphans."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    file1 = src_dir / "file1.py"
    file1.write_text("# sw-artifact: 1234-5678\\nprint('hello')", encoding="utf-8")

    file2 = src_dir / "file2.py"
    file2.write_text("import os\\n# sw-artifact: abcd-efgh\\n", encoding="utf-8")

    orphans = check_lineage(src_dir)
    assert orphans == []


def test_check_lineage_detects_orphans(tmp_path):
    """Files without the tag are reported as orphans."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    tagged = src_dir / "tagged.py"
    tagged.write_text("# sw-artifact: 111\\n", encoding="utf-8")

    orphan1 = src_dir / "orphan1.py"
    orphan1.write_text("print('no tag here')", encoding="utf-8")

    orphan2 = src_dir / "orphan2.py"
    orphan2.write_text("# sw-art-fact: typo\\n", encoding="utf-8")

    orphans = check_lineage(src_dir)
    assert len(orphans) == 2
    assert str(orphan1.resolve()) in orphans
    assert str(orphan2.resolve()) in orphans


def test_check_lineage_skips_excluded_dirs(tmp_path):
    """Scanner should skip .tmp, .venv, __pycache__ etc."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    tmp_dir = src_dir / ".tmp"
    tmp_dir.mkdir()
    tmp_file = tmp_dir / "temp_orphan.py"
    tmp_file.write_text("x=1", encoding="utf-8")

    venv_dir = src_dir / ".venv"
    venv_dir.mkdir()
    venv_file = venv_dir / "venv_orphan.py"
    venv_file.write_text("x=1", encoding="utf-8")

    cache_dir = src_dir / "__pycache__"
    cache_dir.mkdir()
    cache_file = cache_dir / "cache_orphan.py"
    cache_file.write_text("x=1", encoding="utf-8")

    regular_orphan = src_dir / "regular_orphan.py"
    regular_orphan.write_text("x=1", encoding="utf-8")

    orphans = check_lineage(src_dir)
    assert len(orphans) == 1
    assert str(regular_orphan.resolve()) in orphans


def test_check_lineage_only_checks_py_files(tmp_path):
    """Scanner only evaluates .py files."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    md_file = src_dir / "readme.md"
    md_file.write_text("no tag needed here", encoding="utf-8")

    orphans = check_lineage(src_dir)
    assert orphans == []


def test_check_lineage_unreadable_file(tmp_path):
    """Scanner logs a warning and skips files raising read exceptions."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    bad_file = src_dir / "bad.py"
    bad_file.write_bytes(bytes.fromhex("ffffff"))  # Invalid utf-8 byte sequence

    with (
        check_lineage.__globals__.get("pytest", __import__("pytest")).raises(Exception)
        if False
        else __import__("contextlib").nullcontext()
    ):
        # Actually it won't raise, it will catch and log
        orphans = check_lineage(src_dir)

    assert orphans == []


def test_tag_command_adds_tag_and_logs_to_db(tmp_path):
    """sw lineage tag <file> should add a new UUID if missing, and log to DB."""
    target_file = tmp_path / "target.py"
    target_file.write_text("def foo():\n    pass\n", encoding="utf-8")

    with (
        patch("specweaver.graph.interfaces.cli.uuid.uuid4") as mock_uuid,
        patch("specweaver.graph.interfaces.cli.get_db") as mock_get_db,
        patch("specweaver.graph.interfaces.cli.LineageRepository") as mock_repo_class,
        patch("specweaver.interfaces.cli._core.run_repo_op") as mock_repo_op,
    ):
        mock_uuid.return_value = "mocked-uuid-123"
        mock_repo_op.side_effect = [
            "test-proj",  # get_active_project
            {"root_path": "/tmp/test-proj"},  # get_project
        ]
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo

        result = runner.invoke(app, ["tag", str(target_file), "--author", "test-user"])

        assert result.exit_code == 0, f"Command failed with {result.exit_code}: {result.output}"
        content = target_file.read_text(encoding="utf-8")
        assert content.startswith("# sw-artifact: mocked-uuid-123\n")

        mock_repo.log_artifact_event.assert_called_once_with(
            artifact_id="mocked-uuid-123",
            parent_id=None,
            run_id="manual",
            event_type="manual_tag",
            model_id="test-user",
        )


def test_tag_command_logs_edit_for_existing_tag(tmp_path):
    """sw lineage tag <file> should read existing UUID and log manual event."""
    target_file = tmp_path / "target.py"
    target_file.write_text(
        f"# sw-artifact: {_EXISTING_UUID}\ndef foo():\n    pass\n", encoding="utf-8"
    )

    with (
        patch("specweaver.graph.interfaces.cli.get_db") as mock_get_db,
        patch("specweaver.graph.interfaces.cli.LineageRepository") as mock_repo_class,
        patch("specweaver.interfaces.cli._core.run_repo_op") as mock_repo_op,
    ):
        mock_repo_op.side_effect = [
            "test-proj",  # get_active_project
            {"root_path": "/tmp/test-proj"},  # get_project
        ]
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo

        result = runner.invoke(app, ["tag", str(target_file), "--author", "other-user"])

        assert result.exit_code == 0, f"Command failed: {result.output}"

        mock_repo.log_artifact_event.assert_called_once_with(
            artifact_id=_EXISTING_UUID,
            parent_id=None,
            run_id="manual",
            event_type="manual_tag",
            model_id="other-user",
        )


def test_tree_command_displays_lineage():
    """sw lineage tree <uuid> should render a rich tree."""
    with (
        patch("specweaver.graph.interfaces.cli.get_db") as mock_get_db,
        patch("specweaver.graph.interfaces.cli.LineageEngine") as mock_engine_class,
        patch("specweaver.graph.interfaces.cli.LineageRepository"),
        patch("specweaver.interfaces.cli._core.run_repo_op") as mock_repo_op,
    ):
        mock_repo_op.side_effect = [
            "test-proj",  # get_active_project
            {"root_path": "/tmp/test-proj"},  # get_project
        ]
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_engine = MagicMock()
        mock_engine_class.return_value = mock_engine

        mock_engine.find_root.return_value = "root-uuid"
        mock_engine.build_tree.return_value = {
            "id": "root-uuid",
            "circular": False,
            "history": [{"event_type": "generated_code", "model_id": "human"}],
            "children": [
                {
                    "id": "child-uuid",
                    "circular": False,
                    "history": [{"event_type": "linted", "model_id": "human"}],
                    "children": [
                        {
                            "id": "leaf-uuid",
                            "circular": False,
                            "history": [{"event_type": "manual_tag", "model_id": "human"}],
                            "children": [],
                        }
                    ],
                }
            ],
        }

        result = runner.invoke(app, ["tree", "child-uuid"])

        assert result.exit_code == 0, f"Command failed: {result.output}"

        output = result.output
        assert "root-uuid" in output
        assert "child-uuid" in output
        assert "leaf-uuid" in output


def test_tag_command_exits_if_file_not_found(tmp_path):
    """sw lineage tag should exit nicely if the target file does not exist."""
    missing_file = tmp_path / "missing.py"
    result = runner.invoke(app, ["tag", str(missing_file)])
    assert result.exit_code == 1
    assert "does not exist" in result.output


def test_tree_command_reads_uuid_from_file_content(tmp_path):
    """sw lineage tree <file> should read the UUID from the sw-artifact tag."""
    target_file = tmp_path / "test_file.py"
    target_file.write_text(f"# sw-artifact: {_FILE_UUID}\n", encoding="utf-8")

    with (
        patch("specweaver.graph.interfaces.cli.get_db") as mock_get_db,
        patch("specweaver.graph.interfaces.cli.LineageEngine") as mock_engine_class,
        patch("specweaver.graph.interfaces.cli.LineageRepository"),
        patch("specweaver.interfaces.cli._core.run_repo_op") as mock_repo_op,
    ):
        mock_repo_op.side_effect = [
            "test-proj",  # get_active_project
            {"root_path": "/tmp/test-proj"},  # get_project
        ]
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_engine = MagicMock()
        mock_engine_class.return_value = mock_engine

        mock_engine.find_root.return_value = _FILE_UUID
        mock_engine.build_tree.return_value = {
            "id": _FILE_UUID,
            "circular": False,
            "history": [],
            "children": [],
        }

        result = runner.invoke(app, ["tree", str(target_file)])

        assert result.exit_code == 0
        assert _FILE_UUID in result.output
        mock_engine.find_root.assert_called_with(_FILE_UUID)


def test_tree_command_graceful_missing_history():
    """sw lineage tree should print the root UUID even if there is no db history."""
    with (
        patch("specweaver.graph.interfaces.cli.get_db") as mock_get_db,
        patch("specweaver.graph.interfaces.cli.LineageEngine") as mock_engine_class,
        patch("specweaver.graph.interfaces.cli.LineageRepository"),
        patch("specweaver.interfaces.cli._core.run_repo_op") as mock_repo_op,
    ):
        mock_repo_op.side_effect = [
            "test-proj",  # get_active_project
            {"root_path": "/tmp/test-proj"},  # get_project
        ]
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_engine = MagicMock()
        mock_engine_class.return_value = mock_engine

        mock_engine.find_root.return_value = "unknown-uuid"
        mock_engine.build_tree.return_value = {
            "id": "unknown-uuid",
            "circular": False,
            "history": [],
            "children": [],
        }

        result = runner.invoke(app, ["tree", "unknown-uuid"])
        assert result.exit_code == 0
        assert "Lineage Graph (Root: unknown-uuid)" in result.output
        assert "unknown-uuid" in result.output


def test_tree_command_handles_circular_references():
    """sw lineage tree should abort recursive rendering on circular graph links to prevent stack overflow."""
    with (
        patch("specweaver.graph.interfaces.cli.get_db") as mock_get_db,
        patch("specweaver.graph.interfaces.cli.LineageEngine") as mock_engine_class,
        patch("specweaver.graph.interfaces.cli.LineageRepository"),
        patch("specweaver.interfaces.cli._core.run_repo_op") as mock_repo_op,
    ):
        mock_repo_op.side_effect = [
            "test-proj",  # get_active_project
            {"root_path": "/tmp/test-proj"},  # get_project
        ]
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_engine = MagicMock()
        mock_engine_class.return_value = mock_engine

        mock_engine.find_root.return_value = "loop-a"
        mock_engine.build_tree.return_value = {
            "id": "loop-a",
            "circular": False,
            "history": [{"event_type": "manual", "model_id": "human"}],
            "children": [
                {
                    "id": "loop-b",
                    "circular": False,
                    "history": [{"event_type": "manual", "model_id": "human"}],
                    "children": [{"id": "loop-a", "circular": True, "history": [], "children": []}],
                }
            ],
        }

        result = runner.invoke(app, ["tree", "loop-a"])
        assert result.exit_code == 0
        assert "Circular reference: loop-a" in result.output


#: `wrap_artifact_tag` is language-aware, so a drafted spec carries `<!-- sw-artifact: … -->` and
#: a TypeScript file carries `// sw-artifact: …`. The CLI matched `"# sw-artifact: "` at line start
#: and nothing else, so it silently resolved none of them and treated the path string as a UUID.
#: Markdown is the sharpest case: every spec `draft.py` writes is tagged that way (`TECH-023`).
@pytest.mark.parametrize(
    ("language", "tag"),
    [
        ("markdown", f"<!-- sw-artifact: {_FILE_UUID} -->"),
        ("typescript", f"// sw-artifact: {_FILE_UUID}"),
        ("sql", f"-- sw-artifact: {_FILE_UUID}"),
        ("yaml", f"# sw-artifact: {_FILE_UUID}"),
    ],
)
def test_tree_command_resolves_a_tag_in_any_comment_syntax(tmp_path, language, tag):
    """`sw lineage tree <file>` must read the tag the writer actually wrote."""
    target_file = tmp_path / f"spec.{language}"
    target_file.write_text(f"{tag}\nbody\n", encoding="utf-8")

    with (
        patch("specweaver.graph.interfaces.cli.get_db"),
        patch("specweaver.graph.interfaces.cli.LineageEngine") as mock_engine_class,
        patch("specweaver.graph.interfaces.cli.LineageRepository"),
        patch("specweaver.interfaces.cli._core.run_repo_op") as mock_repo_op,
    ):
        mock_repo_op.side_effect = ["test-proj", {"root_path": "/tmp/test-proj"}]
        mock_engine = MagicMock()
        mock_engine_class.return_value = mock_engine
        mock_engine.find_root.return_value = _FILE_UUID
        mock_engine.build_tree.return_value = {
            "id": _FILE_UUID,
            "circular": False,
            "history": [],
            "children": [],
        }

        result = runner.invoke(app, ["tree", str(target_file)])

        assert result.exit_code == 0, result.output
        mock_engine.find_root.assert_called_with(_FILE_UUID)


def test_tree_command_falls_back_to_treating_the_argument_as_a_uuid(tmp_path):
    """An untagged file is not an error — the argument may simply be a UUID already."""
    untagged = tmp_path / "untagged.py"
    untagged.write_text("print('hi')\n", encoding="utf-8")

    with (
        patch("specweaver.graph.interfaces.cli.get_db"),
        patch("specweaver.graph.interfaces.cli.LineageEngine") as mock_engine_class,
        patch("specweaver.graph.interfaces.cli.LineageRepository"),
        patch("specweaver.interfaces.cli._core.run_repo_op") as mock_repo_op,
    ):
        mock_repo_op.side_effect = ["test-proj", {"root_path": "/tmp/test-proj"}]
        mock_engine = MagicMock()
        mock_engine_class.return_value = mock_engine
        mock_engine.find_root.return_value = "root"
        mock_engine.build_tree.return_value = {
            "id": "root",
            "circular": False,
            "history": [],
            "children": [],
        }

        result = runner.invoke(app, ["tree", str(untagged)])

        assert result.exit_code == 0, result.output
        mock_engine.find_root.assert_called_with(str(untagged))
