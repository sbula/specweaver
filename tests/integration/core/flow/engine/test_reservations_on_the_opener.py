# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`reservations.db` is opened through the one opener and versioned like every other file.

Proves: TECH-090 FR-1
Proves: TECH-090 FR-2

| Bucket | Case |
|---|---|
| Happy | a new file reads back WAL, foreign keys and the 30 s wait, and is at version 1 |
| Boundary | a file from before versioning (`user_version` 0, today's table) keeps its locks |
| Degradation | a file from an old release (`sw_reservations`) keeps its locks under the new name |
| Hostile | a file from a newer SpecWeaver is refused, naming the file |
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.engine.reservation import SQLiteReservationSystem
from specweaver.infrastructure.database import SchemaTooNewError

if TYPE_CHECKING:
    from pathlib import Path


def _read(path: Path, sql: str) -> list[tuple[object, ...]]:
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute(sql).fetchall()


def _setup(path: Path, *statements: str) -> None:
    with closing(sqlite3.connect(path)) as conn:
        for statement in statements:
            conn.execute(statement)
        conn.commit()


def test_a_new_file_gets_the_settings_and_version_1(tmp_path: Path) -> None:
    system = SQLiteReservationSystem(tmp_path / "reservations.db")

    with closing(system._get_connection()) as conn:
        settings = [
            conn.execute(f"PRAGMA {name}").fetchone()[0]
            for name in ("journal_mode", "foreign_keys", "busy_timeout")
        ]
    assert settings == ["wal", 1, 30000]
    assert _read(tmp_path / "reservations.db", "PRAGMA user_version") == [(1,)]


def test_a_file_from_before_versioning_keeps_its_locks(tmp_path: Path) -> None:
    path = tmp_path / "reservations.db"
    _setup(
        path,
        "CREATE TABLE flow_reservations (resource_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,"
        " expires_at DATETIME)",
        "INSERT INTO flow_reservations VALUES ('pipeline:a', 'run-1', NULL)",
    )

    system = SQLiteReservationSystem(path)

    assert _read(path, "SELECT resource_id, run_id FROM flow_reservations") == [
        ("pipeline:a", "run-1")
    ]
    assert not system.acquire("pipeline:a", "run-2")


def test_a_file_from_an_old_release_keeps_its_locks_under_the_new_name(tmp_path: Path) -> None:
    path = tmp_path / "reservations.db"
    _setup(
        path,
        "CREATE TABLE sw_reservations (resource_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,"
        " expires_at DATETIME)",
        "INSERT INTO sw_reservations VALUES ('pipeline:a', 'run-1', NULL)",
    )

    SQLiteReservationSystem(path)

    assert _read(path, "SELECT resource_id FROM flow_reservations") == [("pipeline:a",)]
    assert _read(path, "SELECT name FROM sqlite_master WHERE name = 'sw_reservations'") == []


def test_a_file_from_a_newer_specweaver_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "reservations.db"
    _setup(path, "PRAGMA user_version = 9")

    with pytest.raises(SchemaTooNewError, match=r"reservations\.db"):
        SQLiteReservationSystem(path)
