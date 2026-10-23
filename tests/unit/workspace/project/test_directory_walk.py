# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The constitution walk lists only folders inside the project, judged by component.

Proves: TECH-075 FR-9

| Bucket | Case |
|---|---|
| Happy | a nested spec walks up to the root |
| Boundary | a spec at the root; a project reached through a link |
| Degradation | a spec outside the project gets the root constitution only |
| Hostile | a sibling `<root>c` is outside; a constitution above the project is never loaded |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.workspace.project.constitution import CONSTITUTION_FILENAME, find_constitution
from specweaver.workspace.project.directory_walk import walk_up_dirs

if TYPE_CHECKING:
    from pathlib import Path


class TestTheWalkStaysInsideTheProject:
    """TECH-075 FR-9: a folder is inside by its components, and only inside folders are searched."""

    def test_a_sibling_whose_name_starts_with_the_projects_is_outside(self, tmp_path: Path) -> None:
        project = tmp_path / "proj"
        project.mkdir()
        sibling = tmp_path / "projc"
        sibling.mkdir()

        assert walk_up_dirs(project, sibling / "s_spec.md") == [project.resolve()]

    def test_a_constitution_above_the_project_is_never_loaded(self, tmp_path: Path) -> None:
        (tmp_path / CONSTITUTION_FILENAME).write_text("# Above", encoding="utf-8")
        project = tmp_path / "proj"
        project.mkdir()
        sibling = tmp_path / "projc"
        sibling.mkdir()

        assert find_constitution(project, spec_path=sibling / "s_spec.md") is None

    def test_a_spec_outside_brings_no_constitution_of_its_own(self, tmp_path: Path) -> None:
        project = tmp_path / "proj"
        project.mkdir()
        (project / CONSTITUTION_FILENAME).write_text("# Root", encoding="utf-8")
        other = tmp_path / "other"
        other.mkdir()
        (other / CONSTITUTION_FILENAME).write_text("# Foreign", encoding="utf-8")

        result = find_constitution(project, spec_path=other / "s_spec.md")

        assert result is not None
        assert "Root" in result.content

    def test_a_nested_spec_walks_up_to_the_root(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b"
        deep.mkdir(parents=True)

        assert walk_up_dirs(tmp_path, deep / "s_spec.md") == [
            deep.resolve(),
            (tmp_path / "a").resolve(),
            tmp_path.resolve(),
        ]

    def test_a_spec_at_the_root(self, tmp_path: Path) -> None:
        assert walk_up_dirs(tmp_path, tmp_path / "s_spec.md") == [tmp_path.resolve()]

    def test_a_project_reached_through_a_link_still_walks(self, tmp_path: Path) -> None:
        real = tmp_path / "real"
        (real / "svc").mkdir(parents=True)
        (tmp_path / "linked").symlink_to(real)

        assert walk_up_dirs(tmp_path / "linked", tmp_path / "linked" / "svc" / "s_spec.md") == [
            (real / "svc").resolve(),
            real.resolve(),
        ]
