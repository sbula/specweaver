# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the workspace repository hands back for a row, on a real `specweaver.db`.

The repository's one-row and many-row reads build their dicts in one place each; these tests pin
what that place returns, and that the two reads agree.

Proves: TECH-090 FR-13, FR-14

| Bucket | Case |
|---|---|
| Happy | a registered project reads back with every field; a saved standard reads back with every field |
| Boundary | the one-row and the many-row reads of the same row are equal |
| Degradation | not applicable: a read of a row that exists has no failing input here |
| Hostile | renaming a project carries its memory rows along (the foreign key's `ON UPDATE CASCADE`) |
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pytest

from specweaver.commons.async_bridge import run_sync
from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.infrastructure.database import Database
from specweaver.workspace.store import WorkspaceRepository

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    path = tmp_path / "specweaver.db"
    bootstrap_database(str(path))
    return Database(path)


def _repo(db: Database, action):
    async def _run():
        async with db.async_session_scope() as session:
            return await action(WorkspaceRepository(session))

    return run_sync(_run)


def test_a_project_reads_back_with_every_field(db: Database) -> None:
    _repo(db, lambda r: r.register_project("demo", "/w/demo"))

    project = _repo(db, lambda r: r.get_project("demo"))

    assert isinstance(project["created_at"], str)
    datetime.fromisoformat(project["created_at"])
    assert {k: v for k, v in project.items() if k not in ("created_at", "last_used_at")} == {
        "name": "demo",
        "root_path": "/w/demo",
        "log_level": "DEBUG",
        "constitution_max_size": 5120,
        "domain_profile": None,
        "auto_bootstrap_constitution": "prompt",
        "default_dal": "DAL_C",
    }
    assert isinstance(project["last_used_at"], str)


def test_one_project_and_the_list_agree(db: Database) -> None:
    _repo(db, lambda r: r.register_project("demo", "/w/demo"))

    assert _repo(db, lambda r: r.list_projects()) == [_repo(db, lambda r: r.get_project("demo"))]


def test_a_standard_reads_back_with_every_field(db: Database) -> None:
    _repo(db, lambda r: r.register_project("demo", "/w/demo"))
    _repo(db, lambda r: r.save_standard("demo", ".", "python", "naming", {"style": "snake"}, 0.9))

    (listed,) = _repo(db, lambda r: r.get_standards("demo"))
    single = _repo(db, lambda r: r.get_standard("demo", ".", "python", "naming"))

    assert listed == single
    assert isinstance(single["scanned_at"], str)
    datetime.fromisoformat(single["scanned_at"])
    assert {k: v for k, v in single.items() if k != "scanned_at"} == {
        "project_name": "demo",
        "scope": ".",
        "language": "python",
        "category": "naming",
        "data": '{"style": "snake"}',
        "confidence": 0.9,
        "confirmed_by": None,
    }


def test_renaming_a_project_carries_its_memory_rows(db: Database) -> None:
    _repo(db, lambda r: r.register_project("demo", "/w/demo"))
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO memory_epics (id, project_name, title, status, created_at, updated_at)"
            " VALUES ('0123456789abcdef0123456789abcdef', 'demo', 'e', 'OPEN',"
            " '2026-11-07T00:00:00+00:00', '2026-11-07T00:00:00+00:00')"
        )
        conn.execute("UPDATE workspace_projects SET name = 'renamed' WHERE name = 'demo'")
        conn.commit()
        rows = conn.execute("SELECT project_name FROM memory_epics").fetchall()

    assert [row[0] for row in rows] == ["renamed"]
