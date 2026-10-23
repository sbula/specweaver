# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A broken project setting stops `load_settings`, naming the file, key and line.

Proves: TECH-076 FR-1, TECH-076 FR-2, TECH-076 NFR-1, TECH-076 NFR-2

A real database row → `load_settings` → the project's `specweaver.toml`. Nothing is mocked.

| Bucket | Case |
|---|---|
| Happy | a valid `[sandbox]` and `[standards]` are read |
| Boundary | no file, and a file without the sections, give the defaults |
| Degradation | a file that is not valid TOML stops, naming `(syntax)` and its line |
| Hostile | a misspelt key or a bad value in either section stops, naming the key and its line |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.bootstrap.settings_loader import load_settings
from specweaver.core.config.database import Database
from specweaver.core.config.settings_file import SettingsFileError
from tests.fixtures.db_utils import register_test_project

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture()
def project(tmp_path: Path) -> tuple[Database, Path]:
    bootstrap_database(str(tmp_path / "specweaver.db"))
    db = Database(tmp_path / "specweaver.db")
    root = tmp_path / "proj"
    root.mkdir()
    register_test_project(db, "proj", str(root))
    return db, root


def _write(root: Path, text: str) -> None:
    (root / "specweaver.toml").write_text(text, encoding="utf-8")


def test_valid_sections_are_read(project: tuple[Database, Path]) -> None:
    db, root = project
    _write(root, '[sandbox]\nexecution_mode = "container"\n\n[standards]\nmode = "best_practice"\n')

    settings = load_settings(db, "proj")

    assert settings.sandbox.execution_mode == "container"
    assert settings.standards.mode == "best_practice"


@pytest.mark.parametrize("text", [None, "[llm]\nschema_version = 1\n"])
def test_no_file_or_no_section_gives_the_defaults(
    project: tuple[Database, Path], text: str | None
) -> None:
    db, root = project
    if text is not None:
        _write(root, text)

    settings = load_settings(db, "proj")

    assert settings.sandbox.execution_mode == "host"
    assert settings.standards.mode == "mimicry"


@pytest.mark.parametrize(
    ("text", "key", "line"),
    [
        ('[sandbox\nexecution_mode = "container"\n', "(syntax)", 1),
        ('[sandbox]\n\nexecution_mod = "container"\n', "sandbox.execution_mod", 3),
        ('[sandbox]\nexecution_mode = "containr"\n', "sandbox.execution_mode", 2),
        (
            '[sandbox]\nenforce_worktree_isolation = "yes please"\n',
            "sandbox.enforce_worktree_isolation",
            2,
        ),
        ('[standards]\nmod = "best_practice"\n', "standards.mod", 2),
        ('[standards]\nmode = "copycat"\n', "standards.mode", 2),
    ],
)
def test_a_broken_section_stops_naming_the_key_and_line(
    project: tuple[Database, Path], text: str, key: str, line: int
) -> None:
    db, root = project
    _write(root, text)

    with pytest.raises(SettingsFileError) as caught:
        load_settings(db, "proj")

    assert caught.value.source == str(root / "specweaver.toml")
    assert (caught.value.key, caught.value.line) == (key, line)
