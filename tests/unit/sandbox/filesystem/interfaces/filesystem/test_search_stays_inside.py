# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Search tools never read or list through a symlink that leaves the project.

E-SENS-01, done when: an agent cannot read a file outside its granted boundary.

| Bucket | Case |
|---|---|
| Happy | a search finds the project's own file |
| Boundary | a symlinked file inside a granted folder is skipped |
| Degradation | not applicable — a broken link is covered by `test_search.py` |
| Hostile | a symlinked folder as the search path is refused |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from specweaver.sandbox.filesystem.core.executor import FileExecutor
from specweaver.sandbox.filesystem.interfaces.tool import FileSystemTool
from specweaver.sandbox.security import AccessMode, FolderGrant

if TYPE_CHECKING:
    from pathlib import Path

_SECRET = "TOPSECRET"


@pytest.fixture
def reviewer(tmp_path: Path) -> FileSystemTool:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text(_SECRET, encoding="utf-8")
    project = tmp_path / "proj"
    (project / "src").mkdir(parents=True)
    (project / "src" / "own.txt").write_text(f"own {_SECRET[:3]}", encoding="utf-8")
    (project / "src" / "leak.txt").symlink_to(outside / "secret.txt")
    (project / "src" / "outlink").symlink_to(outside, target_is_directory=True)
    grants = [FolderGrant(path="src", mode=AccessMode.READ, recursive=True)]
    return FileSystemTool(executor=FileExecutor(cwd=project), role="reviewer", grants=grants)


@pytest.fixture(autouse=True)
def _no_ripgrep():
    with patch("specweaver.sandbox.filesystem.core.search.shutil.which", return_value=None):
        yield


def test_grep_finds_the_projects_own_file(reviewer: FileSystemTool) -> None:
    result = reviewer.grep("src", "own")

    assert result.status == "success"
    assert [m["file"] for m in result.data if "file" in m] == ["own.txt"]


def test_grep_skips_a_symlinked_file(reviewer: FileSystemTool) -> None:
    result = reviewer.grep("src", _SECRET)

    assert _SECRET not in str(result.data)


@pytest.mark.parametrize("search", ["grep", "find_files"])
def test_a_symlinked_folder_is_refused_as_the_search_path(
    reviewer: FileSystemTool, search: str
) -> None:
    result = getattr(reviewer, search)("src/outlink", "*")

    assert result.status == "error"
    assert "secret" not in str(result.data)


def test_find_files_lists_no_symlink(reviewer: FileSystemTool) -> None:
    result = reviewer.find_files("src", "*")

    assert sorted(entry["path"] for entry in result.data) == ["own.txt"]
