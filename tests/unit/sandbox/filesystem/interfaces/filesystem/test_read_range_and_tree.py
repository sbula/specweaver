# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The read tools do what their definitions tell the model: line ranges and a bounded tree.

Proves: E-SENS-01 FR-5

| Bucket | Case |
|---|---|
| Happy | lines 2 to 3 of a file; a tree two levels deep, directories marked with `/` |
| Boundary | a range past the end is cut to the end; `max_entries` cuts the tree and says so |
| Degradation | a start past the end, or an end before the start, is an error naming the file's length |
| Hostile | the tree never descends a symlinked directory, an excluded directory or one outside the grants |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.filesystem.core.executor import FileExecutor
from specweaver.sandbox.filesystem.interfaces.tool import FileSystemTool
from specweaver.sandbox.security import AccessMode, FolderGrant

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "src" / "pkg" / "deep" / "deeper").mkdir(parents=True)
    (root / "src" / "a.py").write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")
    (root / "src" / "pkg" / "b.py").write_text("x\n", encoding="utf-8")
    (root / "src" / "pkg" / "deep" / "c.py").write_text("y\n", encoding="utf-8")
    (root / "src" / "node_modules" / "lib").mkdir(parents=True)
    outside = tmp_path / "outside"
    (outside / "inner").mkdir(parents=True)
    (root / "src" / "link").symlink_to(outside, target_is_directory=True)
    return root


def _tool(project: Path, grants: list[FolderGrant] | None = None) -> FileSystemTool:
    return FileSystemTool(
        executor=FileExecutor(cwd=project),
        role="reviewer",
        grants=grants or [FolderGrant(path="src", mode=AccessMode.READ, recursive=True)],
        exclude_dirs={"node_modules"},
    )


def test_a_line_range_reads_only_those_lines(project: Path) -> None:
    # Proves: E-SENS-01 FR-5
    result = _tool(project).read_file("src/a.py", start_line=2, end_line=3)
    assert result.status == "success"
    assert result.data == "two\nthree\n"


def test_a_range_past_the_end_stops_at_the_end(project: Path) -> None:
    assert _tool(project).read_file("src/a.py", start_line=4, end_line=99).data == "four\n"


def test_only_a_start_reads_to_the_end(project: Path) -> None:
    assert _tool(project).read_file("src/a.py", start_line=3).data == "three\nfour\n"


@pytest.mark.parametrize(("start", "end"), [(5, None), (3, 2), (0, 2)])
def test_an_impossible_range_names_the_files_length(project: Path, start, end) -> None:
    result = _tool(project).read_file("src/a.py", start_line=start, end_line=end)
    assert result.status == "error"
    assert "4 lines" in result.message


def test_no_range_reads_the_whole_file(project: Path) -> None:
    assert _tool(project).read_file("src/a.py").data == "one\ntwo\nthree\nfour\n"


def test_the_tree_goes_as_deep_as_asked(project: Path) -> None:
    # Proves: E-SENS-01 FR-5
    entries = _tool(project).list_directory("src", depth=2).data

    assert "a.py" in entries
    assert "pkg/" in entries
    assert "pkg/b.py" in entries
    assert "pkg/deep/" in entries
    assert "pkg/deep/c.py" not in entries  # level three


def test_depth_one_is_the_folder_itself(project: Path) -> None:
    entries = _tool(project).list_directory("src", depth=1).data
    assert "pkg/" in entries
    assert "pkg/b.py" not in entries


def test_max_entries_cuts_the_tree_and_says_so(project: Path) -> None:
    result = _tool(project).list_directory("src", depth=5, max_entries=2)
    assert result.status == "success"
    assert len([e for e in result.data if not e.startswith("…")]) == 2
    assert result.data[-1].startswith("…")


def test_the_tree_never_enters_a_link_or_an_excluded_folder(project: Path) -> None:
    # Proves: E-SENS-01 FR-5
    entries = _tool(project).list_directory("src", depth=5).data

    assert "link" in entries and "node_modules/" in entries  # listed, never entered
    assert not any(e.startswith("link/") for e in entries)
    assert not any(e.startswith("node_modules/") and e != "node_modules/" for e in entries)


def test_the_tree_stays_inside_the_grants(project: Path) -> None:
    grants = [FolderGrant(path="src", mode=AccessMode.READ, recursive=False)]
    entries = _tool(project, grants).list_directory("src", depth=3).data

    assert "pkg/" in entries
    assert not any(e.startswith("pkg/") and e != "pkg/" for e in entries)
