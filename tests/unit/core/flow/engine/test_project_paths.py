# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`project_file` resolves a path from outside and refuses one that leaves the project.

Proves: TECH-075 FR-2, TECH-075 FR-3, TECH-075 NFR-2, TECH-075 NFR-3

| Bucket | Case |
|---|---|
| Happy | a file inside resolves under the root |
| Boundary | `.` is the root; a link inside that points inside is allowed |
| Degradation | a missing file inside is returned; the caller decides about existence |
| Hostile | `..`, absolute, an escaping link, a null byte, blank; the error names the input only |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.engine.project_paths import ProjectPathError, project_file

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    (project / "specs").mkdir(parents=True)
    (project / "specs" / "a.md").write_text("# A\n", encoding="utf-8")
    (tmp_path / "outside.md").write_text("secret\n", encoding="utf-8")
    return project


def test_a_file_inside_resolves_under_the_root(root: Path) -> None:
    assert project_file(root, "specs/a.md") == (root / "specs" / "a.md").resolve()


def test_dot_is_the_root(root: Path) -> None:
    assert project_file(root, ".") == root.resolve()


def test_a_link_inside_that_points_inside_is_allowed(root: Path) -> None:
    (root / "alias.md").symlink_to(root / "specs" / "a.md")
    assert project_file(root, "alias.md") == (root / "specs" / "a.md").resolve()


def test_a_missing_file_inside_is_returned(root: Path) -> None:
    assert project_file(root, "specs/none.md") == (root / "specs" / "none.md").resolve()


@pytest.mark.parametrize(
    "given",
    ["../outside.md", "specs/../../outside.md", "..", "spec\x00s/a.md", "", "   "],
)
def test_a_way_out_is_refused(root: Path, given: str) -> None:
    with pytest.raises(ProjectPathError):
        project_file(root, given)


def test_an_absolute_path_outside_is_refused(root: Path) -> None:
    with pytest.raises(ProjectPathError):
        project_file(root, str(root.parent / "outside.md"))


def test_a_link_that_points_outside_is_refused(root: Path) -> None:
    (root / "specs" / "leak.md").symlink_to(root.parent / "outside.md")
    with pytest.raises(ProjectPathError):
        project_file(root, "specs/leak.md")


def test_the_error_names_the_input_and_not_the_resolved_path(root: Path) -> None:
    (root / "leak.md").symlink_to(root.parent / "outside.md")
    with pytest.raises(ProjectPathError) as caught:
        project_file(root, "leak.md")
    assert "leak.md" in str(caught.value)
    assert str(root.parent) not in str(caught.value)


def test_the_error_is_a_value_error(root: Path) -> None:
    with pytest.raises(ValueError):
        project_file(root, "../outside.md")
