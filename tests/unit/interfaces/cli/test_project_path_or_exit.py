# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every command finds its project folder and its target file one way, and refuses one way.

Proves: TECH-076 FR-5, TECH-076 FR-7

| Bucket | Case |
|---|---|
| Happy | a project folder given by path answers its resolved path |
| Boundary | no path given means the working folder |
| Degradation | not applicable — the lookup has no dependency that can fail besides the disk |
| Hostile | a missing path or a file instead of a folder: exit 1, the reason printed |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import typer

from specweaver.interfaces.cli import _core
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path


def test_a_project_folder_answers_its_resolved_path(tmp_path: Path) -> None:
    (tmp_path / "proj").mkdir()

    assert (
        _core.project_path_or_exit(str(tmp_path / "proj" / ".." / "proj"))
        == (tmp_path / "proj").resolve()
    )


def test_no_path_means_the_working_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert _core.project_path_or_exit(None) == tmp_path.resolve()


@pytest.mark.parametrize("given", ["missing", "a_file.txt"])
def test_a_path_that_is_not_a_folder_exits(
    tmp_path: Path, given: str, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "a_file.txt").write_text("x")

    with pytest.raises(typer.Exit) as caught:
        _core.project_path_or_exit(str(tmp_path / given))

    assert caught.value.exit_code == 1
    assert shows(capsys.readouterr().out, given)


def test_an_existing_file_answers_its_path(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x")

    assert _core.file_or_exit(str(tmp_path / "a.py")) == tmp_path / "a.py"


def test_a_missing_file_exits_naming_it(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(typer.Exit) as caught:
        _core.file_or_exit(str(tmp_path / "gone.py"))

    assert caught.value.exit_code == 1
    assert shows(capsys.readouterr().out, "File not found")


def test_the_sections_a_run_needs_are_read_together(tmp_path: Path) -> None:
    (tmp_path / "specweaver.toml").write_text(
        '[autonomy]\nmode = "agentic"\n\n[implement]\nlanguage = "rust"\n', encoding="utf-8"
    )

    docs, autonomy, language = _core.project_sections_at(tmp_path)

    assert (docs.rule, autonomy.mode, language) == ([], "agentic", "rust")


def test_a_broken_section_exits_naming_its_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "specweaver.toml").write_text('[implement]\nlanguag = "rust"\n', encoding="utf-8")

    with pytest.raises(typer.Exit) as caught:
        _core.project_sections_at(tmp_path)

    assert caught.value.exit_code == 1
    assert shows(capsys.readouterr().out, "specweaver.toml:2: implement.languag")
