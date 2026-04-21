# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from pathlib import Path

from specweaver.core.loom.commons.filesystem.search import find_by_glob, iter_text_files


def test_find_by_glob_excludes_directories(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()

    (root / "good").mkdir()
    (root / "good" / "test.py").touch()

    (root / "bad").mkdir()
    (root / "bad" / "test.py").touch()

    excludes = {"bad"}
    results = find_by_glob(root, "*.py", exclude_dirs=excludes)

    paths = [r["path"] for r in results]
    assert "good/test.py" in paths or r"good\test.py" in paths
    assert "bad/test.py" not in paths and r"bad\test.py" not in paths


def test_iter_text_files_excludes_directories(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()

    (root / "good").mkdir()
    (root / "good" / "test.txt").touch()

    (root / "node_modules").mkdir()
    (root / "node_modules" / "test.txt").touch()

    excludes = {
        "node_modules/"
    }  # Note: trailing slash or not, the implementation strips it if we pass properly? Wait, does iter_text_files strip? No! The caller is expected to strip!
    excludes_stripped = {e.rstrip("/") for e in excludes}

    results = iter_text_files(root, exclude_dirs=excludes_stripped)
    names = [p.name for p in results]

    assert len(names) == 1
    assert "test.txt" in names
