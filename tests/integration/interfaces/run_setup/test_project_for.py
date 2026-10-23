# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A run uses one project, chosen one way.

Proves: TECH-077 FR-4

A real database; projects registered and activated as the CLI does.

| Bucket | Case |
|---|---|
| Happy | the project registered at the run's folder is the project |
| Boundary | a project the request names wins; with no folder given, the active project |
| Degradation | no folder and no active project is refused |
| Hostile | a folder no project is registered at is refused, naming it and `sw init`, even when another project is active |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.interfaces.run_setup.builder import UnknownProjectError, project_for
from tests.fixtures.db_utils import register_test_project, set_test_active_project

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture()
def world(tmp_path: Path) -> tuple[Database, Path, Path]:
    bootstrap_database(str(tmp_path / "specweaver.db"))
    db = Database(tmp_path / "specweaver.db")
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    register_test_project(db, "alpha", str(a))
    register_test_project(db, "beta", str(b))
    set_test_active_project(db, "alpha")
    return db, a, b


def test_the_project_at_the_folder_is_the_project(world: tuple[Database, Path, Path]) -> None:
    db, _, b = world

    assert project_for(db, b) == "beta"


def test_a_named_project_wins(world: tuple[Database, Path, Path]) -> None:
    db, a, _ = world

    assert project_for(db, a, named="beta") == "beta"


def test_no_folder_means_the_active_project(world: tuple[Database, Path, Path]) -> None:
    db, _, _ = world

    assert project_for(db, None) == "alpha"


def test_no_folder_and_no_active_project_is_refused(tmp_path: Path) -> None:
    bootstrap_database(str(tmp_path / "specweaver.db"))
    db = Database(tmp_path / "specweaver.db")

    with pytest.raises(UnknownProjectError, match="No active project"):
        project_for(db, None)


def test_an_unregistered_folder_is_refused(
    world: tuple[Database, Path, Path], tmp_path: Path
) -> None:
    db, _, _ = world
    loose = tmp_path / "loose"
    loose.mkdir()

    with pytest.raises(UnknownProjectError) as caught:
        project_for(db, loose)

    assert str(loose) in str(caught.value)
    assert "sw init" in str(caught.value)
