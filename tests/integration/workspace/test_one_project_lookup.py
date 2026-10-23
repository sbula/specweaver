# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Each project question has one lookup, and every door that asks it gets the same answer.

Proves: TECH-077 FR-10

A real database through the registration the CLI uses; the CLI helpers and the API's lookup are
asked the same questions as the store.

| Bucket | Case |
|---|---|
| Happy | a registered project's name, DAL, profile and root are found |
| Boundary | one folder spelled two ways is one project |
| Degradation | no project at a folder, or no project by a name, is None |
| Hostile | a name that is a prefix of another project's name does not match it |
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.workspace.store import (
    DEFAULT_DAL,
    default_dal_at,
    domain_profile_at,
    project_name_at,
    project_root_of,
)
from tests.fixtures.db_utils import register_test_project

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture()
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Database, Path]:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    bootstrap_database(str(data / "specweaver.db"))
    db = Database(data / "specweaver.db")
    root = tmp_path / "proj"
    root.mkdir()
    (tmp_path / "proj-two").mkdir()
    register_test_project(db, "proj", str(root))
    register_test_project(db, "proj-two", str(tmp_path / "proj-two"))
    return db, root


def test_a_registered_project_is_found(world: tuple[Database, Path]) -> None:
    db, root = world

    assert project_name_at(db, root) == "proj"
    assert default_dal_at(db, root) == DEFAULT_DAL
    assert domain_profile_at(db, root) is None
    assert project_root_of(db, "proj") == root.resolve()


def test_one_folder_spelled_two_ways_is_one_project(world: tuple[Database, Path]) -> None:
    db, root = world

    assert project_name_at(db, root / ".." / "proj") == "proj"


def test_nothing_registered_is_none(world: tuple[Database, Path], tmp_path: Path) -> None:
    db, _ = world

    assert project_name_at(db, tmp_path) is None
    assert project_root_of(db, "missing") is None


def test_a_prefix_name_does_not_match(world: tuple[Database, Path]) -> None:
    db, _ = world

    assert project_root_of(db, "pro") is None


def test_every_door_answers_alike(world: tuple[Database, Path]) -> None:
    """The CLI helpers and the API ask the store; they cannot disagree with it."""
    from specweaver.interfaces.api.v1.paths import resolve_project_root
    from specweaver.interfaces.cli import _core

    db, root = world

    assert _core.registered_project_at(root) == project_name_at(db, root) == "proj"
    assert _core.project_root("proj") == project_root_of(db, "proj")
    assert asyncio.run(resolve_project_root("proj", db)) == project_root_of(db, "proj")
