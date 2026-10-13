# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The read tools do what their definitions tell the model: line ranges and a bounded tree.

Proves: E-SENS-01 FR-5

| Bucket | Case |
|---|---|
| Happy | lines 2 to 3 of a file; a tree two levels deep, directories marked with `/` |
| Boundary | a range past the end is cut to the end; `max_entries` cuts the tree and says so |
| Degradation | a start past the end names the file's length; a backwards or zero range is refused |
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


def test_a_start_past_the_end_names_the_files_length(project: Path) -> None:
    result = _tool(project).read_file("src/a.py", start_line=5)
    assert result.status == "error"
    assert "4 lines" in result.message


@pytest.mark.parametrize(("start", "end"), [(3, 2), (0, 2)])
def test_a_backwards_or_zero_range_is_refused(project: Path, start, end) -> None:
    result = _tool(project).read_file("src/a.py", start_line=start, end_line=end)
    assert result.status == "error"
    assert "not a range" in result.message


def test_no_range_reads_the_whole_file(project: Path) -> None:
    assert _tool(project).read_file("src/a.py").data == "one\ntwo\nthree\nfour\n"


def test_the_tree_goes_as_deep_as_asked(project: Path) -> None:
    # Proves: E-SENS-01 FR-5
    entries = _tool(project).list_directory("src", depth=2).data

    assert "src/a.py" in entries
    assert "src/pkg/" in entries
    assert "src/pkg/b.py" in entries
    assert "src/pkg/deep/" in entries
    assert "src/pkg/deep/c.py" not in entries  # level three


def test_depth_one_is_the_folder_itself(project: Path) -> None:
    entries = _tool(project).list_directory("src", depth=1).data
    assert "src/pkg/" in entries
    assert "src/pkg/b.py" not in entries


def test_max_entries_cuts_the_tree_and_says_so(project: Path) -> None:
    result = _tool(project).list_directory("src", depth=5, max_entries=2)
    assert result.status == "success"
    assert len([e for e in result.data if not e.startswith("…")]) == 2
    assert result.data[-1].startswith("…")


def test_the_tree_never_enters_a_link_or_an_excluded_folder(project: Path) -> None:
    # Proves: E-SENS-01 FR-5
    entries = _tool(project).list_directory("src", depth=5).data

    assert "src/link" in entries and "src/node_modules/" in entries  # listed, never entered
    assert not any(e.startswith("src/link/") for e in entries)
    assert not any(e.startswith("src/node_modules/") and e != "src/node_modules/" for e in entries)


def test_the_tree_stays_inside_the_grants(project: Path) -> None:
    grants = [FolderGrant(path="src", mode=AccessMode.READ, recursive=False)]
    entries = _tool(project, grants).list_directory("src", depth=3).data

    assert "src/pkg/" in entries
    assert not any(e.startswith("src/pkg/") and e != "src/pkg/" for e in entries)


def test_a_range_reads_part_of_a_file_too_big_to_read_whole(project: Path) -> None:
    # Proves: E-SENS-01 FR-5
    (project / "src" / "big.txt").write_text("line\n" * 60_000, encoding="utf-8")  # 300 KB
    tool = _tool(project)

    assert tool.read_file("src/big.txt").status == "error"
    part = tool.read_file("src/big.txt", start_line=59_999, end_line=60_000)
    assert part.status == "success"
    assert part.data == "line\nline\n"


def test_a_range_that_returns_too_much_is_refused(project: Path) -> None:
    (project / "src" / "big.txt").write_text("line\n" * 60_000, encoding="utf-8")
    result = _tool(project).read_file("src/big.txt", start_line=1, end_line=60_000)
    assert result.status == "error"
    assert "smaller range" in result.message


def test_a_start_past_the_end_says_so_plainly(project: Path) -> None:
    result = _tool(project).read_file("src/a.py", start_line=9)
    assert result.message == "src/a.py has 4 lines; line 9 does not exist"


def test_found_paths_are_from_the_project_root_and_readable(project: Path) -> None:
    # Proves: E-SENS-01 FR-5
    tool = _tool(project)
    found = [entry["path"] for entry in tool.find_files("src", "*.py", file_type="file").data]
    matched = [entry["file"] for entry in tool.grep("src/pkg", "x").data if "file" in entry]
    listed = [e for e in tool.list_directory("src", depth=2).data if e.endswith(".py")]

    assert "src/pkg/b.py" in found
    assert matched == ["src/pkg/b.py"]
    assert "src/pkg/b.py" in listed
    for path in {*found, *matched, *listed}:
        assert tool.read_file(path).status == "success", path
