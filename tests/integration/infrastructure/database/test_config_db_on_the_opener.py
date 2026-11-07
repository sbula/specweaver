# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`specweaver.db` is opened through the one opener, however the code asks for it.

Proves: TECH-090 FR-1
Proves: TECH-090 FR-2

| Bucket | Case |
|---|---|
| Happy | `Database.connect()`, an async session and the sync engine read back WAL, foreign keys, 30 s |
| Boundary | the lineage repository, which opens the same file, gets the same settings |
| Degradation | a missing parent folder is created |
| Hostile | the 5 s wait the API door sets reaches all of them |
"""

from __future__ import annotations

from contextlib import closing
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from specweaver.graph.lineage.store.lineage_repository import LineageRepository
from specweaver.infrastructure.database import Database, set_lock_wait

if TYPE_CHECKING:
    from pathlib import Path

_NAMES = ("journal_mode", "foreign_keys", "busy_timeout")


def _settings(conn: object) -> list[object]:
    return [conn.execute(f"PRAGMA {name}").fetchone()[0] for name in _NAMES]  # type: ignore[attr-defined]


def test_a_plain_connection_gets_the_settings(tmp_path: Path) -> None:
    with closing(Database(tmp_path / "specweaver.db").connect()) as conn:
        assert _settings(conn) == ["wal", 1, 30000]


@pytest.mark.asyncio
async def test_an_async_session_gets_the_settings(tmp_path: Path) -> None:
    db = Database(tmp_path / "specweaver.db")

    async with db.async_session_scope() as session:
        got = [(await session.execute(text(f"PRAGMA {name}"))).scalar() for name in _NAMES]

    assert got == ["wal", 1, 30000]


def test_the_sync_engine_gets_the_settings(tmp_path: Path) -> None:
    engine = Database(tmp_path / "specweaver.db").sync_engine()
    try:
        with engine.connect() as conn:
            got = [conn.execute(text(f"PRAGMA {name}")).scalar() for name in _NAMES]
    finally:
        engine.dispose()

    assert got == ["wal", 1, 30000]


def test_the_lineage_repository_gets_the_settings(tmp_path: Path) -> None:
    repo = LineageRepository(str(tmp_path / "specweaver.db"))

    with closing(repo._get_connection()) as conn:
        assert _settings(conn) == ["wal", 1, 30000]


def test_a_missing_folder_is_created(tmp_path: Path) -> None:
    with closing(Database(tmp_path / "new" / "specweaver.db").connect()) as conn:
        assert _settings(conn)[0] == "wal"


@pytest.mark.asyncio
async def test_the_doors_wait_reaches_every_way_in(tmp_path: Path) -> None:
    set_lock_wait(5)
    db = Database(tmp_path / "specweaver.db")

    with closing(db.connect()) as conn:
        plain = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    async with db.async_session_scope() as session:
        session_wait = (await session.execute(text("PRAGMA busy_timeout"))).scalar()
    engine = db.sync_engine()
    try:
        with engine.connect() as conn:
            sync_wait = conn.execute(text("PRAGMA busy_timeout")).scalar()
    finally:
        engine.dispose()
    with closing(LineageRepository(str(tmp_path / "specweaver.db"))._get_connection()) as conn:
        lineage = conn.execute("PRAGMA busy_timeout").fetchone()[0]

    assert [plain, session_wait, sync_wait, lineage] == [5000] * 4
