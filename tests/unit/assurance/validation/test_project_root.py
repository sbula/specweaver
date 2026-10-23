# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One walk up from a file, never above the project root.

Proves: TECH-077 FR-9

| Bucket | Case |
|---|---|
| Happy | the walk yields the file's folder, then each parent, ending at the stop |
| Boundary | a start that is the stop yields only the stop; no stop walks to the filesystem root |
| Degradation | a start outside the stop yields its own folders only, never the stop's parents |
| Hostile | a folder above the stop is never yielded |
"""

from __future__ import annotations

from pathlib import Path

from specweaver.assurance.validation.project_root import walk_up


def test_the_walk_ends_at_the_stop(tmp_path: Path) -> None:
    deep = tmp_path / "proj" / "a" / "b"
    deep.mkdir(parents=True)

    assert list(walk_up(deep, tmp_path / "proj")) == [
        deep,
        tmp_path / "proj" / "a",
        tmp_path / "proj",
    ]


def test_a_start_at_the_stop_is_only_the_stop(tmp_path: Path) -> None:
    assert list(walk_up(tmp_path, tmp_path)) == [tmp_path]


def test_no_stop_walks_to_the_filesystem_root(tmp_path: Path) -> None:
    walked = list(walk_up(tmp_path, None))

    assert walked[0] == tmp_path
    assert walked[-1] == Path(tmp_path.anchor)


def test_nothing_above_the_stop_is_yielded(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()

    assert tmp_path not in list(walk_up(proj, proj))


def test_a_start_outside_the_stop_never_reaches_the_stops_parents(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    other = tmp_path / "other"
    proj.mkdir()
    other.mkdir()

    assert list(walk_up(other, proj)) == [other]
