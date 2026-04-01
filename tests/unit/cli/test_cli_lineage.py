# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for the SpecWeaver lineage CLI scanner."""

from __future__ import annotations

from specweaver.cli.lineage import check_lineage


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

    with check_lineage.__globals__.get("pytest", __import__("pytest")).raises(Exception) if False else __import__("contextlib").nullcontext():
        # Actually it won't raise, it will catch and log
        orphans = check_lineage(src_dir)

    assert orphans == []

