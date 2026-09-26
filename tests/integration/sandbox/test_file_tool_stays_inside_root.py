# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""No agent file operation reaches outside the project root, whatever the path says.

Proves: TECH-072 FR-7

`grep` and `find_files` walk the filesystem themselves instead of going through `FileExecutor`, so
the grant check is the only thing between `path=".."` and the parent directory. A grant on the
project root used to cover `../anything`, because the matcher compared `root/../anything` as text.

| Bucket | Case |
|---|---|
| Happy | `grep` and `find_files` inside the project still find the project's file |
| Boundary | `.` (the root itself) is searchable |
| Degradation | a refused path is an error, not an empty result |
| Hostile | `..`, `../`, `src/../..` and a sibling (`../proj2`) — refused, nothing outside is returned |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.filesystem.core.executor import FileExecutor
from specweaver.sandbox.filesystem.interfaces.tool import FileSystemTool
from specweaver.sandbox.security import AccessMode, FolderGrant

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def tool(tmp_path: Path) -> FileSystemTool:
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    (root / "src" / "a.py").write_text("NEEDLE = 1\n", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("NEEDLE outside\n", encoding="utf-8")
    (tmp_path / "proj2").mkdir()
    (tmp_path / "proj2" / "b.txt").write_text("NEEDLE sibling\n", encoding="utf-8")
    grants = [FolderGrant(str(root), AccessMode.FULL, recursive=True)]
    return FileSystemTool(FileExecutor(root), role="implementer", grants=grants)


@pytest.mark.parametrize("path", [".", "src"])
def test_searching_inside_the_project_still_works(tool: FileSystemTool, path: str) -> None:
    found = tool.grep(pattern="NEEDLE", path=path)

    assert found.status == "success", found.message
    assert len(found.data) == 1
    assert found.data[0]["file"].endswith("a.py")


@pytest.mark.parametrize("path", ["..", "../", "src/../..", "../proj2"])
def test_grep_cannot_leave_the_root(tool: FileSystemTool, path: str) -> None:
    found = tool.grep(pattern="NEEDLE", path=path)

    assert found.status == "error", f"grep read outside the project: {found.data}"


@pytest.mark.parametrize("path", ["..", "../", "src/../..", "../proj2"])
def test_find_files_cannot_leave_the_root(tool: FileSystemTool, path: str) -> None:
    found = tool.find_files(pattern="*", path=path)

    assert found.status == "error", f"find_files listed outside the project: {found.data}"
