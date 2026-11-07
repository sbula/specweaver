# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every connection the one opener makes has WAL, foreign keys on and the process's lock wait.

Proves: TECH-090 FR-2

| Bucket | Case |
|---|---|
| Happy | a new file reads back WAL, foreign keys 1 and a 30 s wait, sync and async |
| Boundary | a file already in WAL; the wait set to 5 s reads back 5000 ms |
| Degradation | a sync connection keeps the row factory and transaction mode it asked for |
| Hostile | a negative or zero wait is refused |
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from specweaver.infrastructure.database import (
    create_sqlite_engine,
    lock_wait_seconds,
    open_sqlite,
    set_lock_wait,
)

if TYPE_CHECKING:
    from pathlib import Path


def _pragmas(conn: sqlite3.Connection) -> tuple[str, int, int]:
    return (
        conn.execute("PRAGMA journal_mode").fetchone()[0],
        conn.execute("PRAGMA foreign_keys").fetchone()[0],
        conn.execute("PRAGMA busy_timeout").fetchone()[0],
    )


def test_a_new_file_gets_wal_foreign_keys_and_a_30_second_wait(tmp_path: Path) -> None:
    conn = open_sqlite(tmp_path / "a.db")

    assert _pragmas(conn) == ("wal", 1, 30000)
    conn.close()


def test_a_file_already_in_wal_keeps_it(tmp_path: Path) -> None:
    open_sqlite(tmp_path / "a.db").close()

    conn = open_sqlite(tmp_path / "a.db")

    assert _pragmas(conn) == ("wal", 1, 30000)
    conn.close()


def test_the_wait_the_door_sets_is_the_wait_every_connection_gets(tmp_path: Path) -> None:
    set_lock_wait(5)

    conn = open_sqlite(tmp_path / "a.db")

    assert lock_wait_seconds() == 5
    assert _pragmas(conn)[2] == 5000
    conn.close()


@pytest.mark.parametrize("seconds", [0, -1])
def test_a_wait_that_is_not_positive_is_refused(seconds: float) -> None:
    with pytest.raises(ValueError, match="lock wait"):
        set_lock_wait(seconds)


def test_a_connection_keeps_its_row_factory_and_transaction_mode(tmp_path: Path) -> None:
    conn = open_sqlite(tmp_path / "a.db", row_factory=sqlite3.Row, isolation_level="IMMEDIATE")

    assert conn.row_factory is sqlite3.Row
    assert conn.isolation_level == "IMMEDIATE"
    conn.close()


@pytest.mark.asyncio
async def test_the_async_engine_gets_the_same_three(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "a.db")
    try:
        async with engine.connect() as conn:
            got = []
            for name in ("journal_mode", "foreign_keys", "busy_timeout"):
                got.append((await conn.execute(text(f"PRAGMA {name}"))).scalar())
    finally:
        await engine.dispose()

    assert got == ["wal", 1, 30000]
