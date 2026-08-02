# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest import mock

import pytest

from specweaver.core.flow.engine.reservation import SQLiteReservationSystem


def test_sqlite_reservation_acquire_and_release(tmp_path: Path) -> None:
    db_path = tmp_path / "reservations.db"

    # Needs to create tables automatically upon init
    system = SQLiteReservationSystem(db_path)

    # Acquire a mock resource
    success = system.acquire("port:8000", "run-123")
    assert success is True

    # Second acquisition by different run should catch IntegrityError
    # and safely return False (verdict=Park emulation)
    success2 = system.acquire("port:8000", "run-456")
    assert success2 is False

    # Release it
    system.release("run-123")

    # Now it can be snagged
    success3 = system.acquire("port:8000", "run-456")
    assert success3 is True


def test_sqlite_reservation_idempotent_creation(tmp_path: Path) -> None:
    db_path = tmp_path / "reservations.db"
    system1 = SQLiteReservationSystem(db_path)
    assert system1.acquire("test", "test") is True

    # Re-initialization should not fail (IF NOT EXISTS)
    system2 = SQLiteReservationSystem(db_path)
    assert system2.acquire("test-resource", "run-999") is True


def test_sqlite_reservation_ensure_schema_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    db_path = tmp_path / "reservations.db"
    system = SQLiteReservationSystem(db_path)

    with (
        mock.patch("sqlite3.connect", side_effect=sqlite3.Error("Mocked schema error")),
        pytest.raises(sqlite3.Error, match="Mocked schema error"),
    ):
        system._ensure_schema()

    assert "Failed to initialize SQLiteReservationSystem schema: Mocked schema error" in caplog.text


def test_sqlite_reservation_acquire_operational_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    db_path = tmp_path / "reservations.db"
    system = SQLiteReservationSystem(db_path)

    mock_conn = mock.MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.execute.side_effect = sqlite3.OperationalError("Database is locked")

    with mock.patch.object(system, "_get_connection", return_value=mock_conn):
        assert system.acquire("port:8000", "run-222") is False

    assert (
        "SQLiteReservationSystem Operational timeout on 'port:8000': Database is locked"
        in caplog.text
    )


def test_sqlite_reservation_release_error(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    db_path = tmp_path / "reservations.db"
    system = SQLiteReservationSystem(db_path)

    mock_conn = mock.MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.execute.side_effect = sqlite3.Error("Release failed")

    with mock.patch.object(system, "_get_connection", return_value=mock_conn):
        system.release("run-333")  # Does not raise, swallows gracefully via logger

    assert (
        "SQLiteReservationSystem failed to release lock for run_id=run-333: Release failed"
        in caplog.text
    )


def test_sqlite_reservation_migrates_legacy_table_name_preserving_data(tmp_path: Path) -> None:
    """TECH-005 FR-8: an installation with the pre-SF-3 unprefixed `sw_reservations` table already
    on disk must be migrated to `flow_reservations` in place, preserving every held lock — a blind
    `CREATE TABLE IF NOT EXISTS flow_reservations` would instead create an empty new table
    alongside the untouched old one, silently orphaning every active reservation."""
    db_path = tmp_path / "reservations.db"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE sw_reservations (resource_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, "
            "expires_at DATETIME)"
        )
        conn.execute(
            "INSERT INTO sw_reservations (resource_id, run_id, expires_at) "
            "VALUES ('port:8000', 'run-legacy', '2026-03-14T18:00:00Z')"
        )
        conn.commit()

    system = SQLiteReservationSystem(db_path)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        assert "sw_reservations" not in tables
        assert "flow_reservations" in tables

        cursor.execute("SELECT resource_id, run_id FROM flow_reservations")
        assert cursor.fetchall() == [("port:8000", "run-legacy")]

    # The system's own public API must work normally against the migrated table.
    assert system.acquire("port:8000", "run-new") is False  # still held by run-legacy
    system.release("run-legacy")
    assert system.acquire("port:8000", "run-new") is True


def test_sqlite_reservation_skips_rename_when_both_old_and_new_tables_exist(
    tmp_path: Path,
) -> None:
    """[Graceful degradation] A partially-migrated or corrupt DB with BOTH `sw_reservations` and
    `flow_reservations` present must not raise and must not drop either table."""
    db_path = tmp_path / "reservations.db"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE sw_reservations (resource_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, "
            "expires_at DATETIME)"
        )
        conn.execute(
            "CREATE TABLE flow_reservations (resource_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, "
            "expires_at DATETIME)"
        )
        conn.commit()

    SQLiteReservationSystem(db_path)  # must not raise

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        assert "sw_reservations" in tables
        assert "flow_reservations" in tables


def test_sqlite_reservation_rename_is_idempotent_across_repeated_construction(
    tmp_path: Path,
) -> None:
    """[Robustness] Two `SQLiteReservationSystem` instances constructed back-to-back against the
    same legacy-named DB (simulating a second process racing at startup) must not raise."""
    db_path = tmp_path / "reservations.db"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE sw_reservations (resource_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, "
            "expires_at DATETIME)"
        )
        conn.commit()

    SQLiteReservationSystem(db_path)
    SQLiteReservationSystem(db_path)  # must not raise

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        assert "flow_reservations" in tables
        assert "sw_reservations" not in tables


def test_sqlite_reservation_rename_swallows_concurrent_operational_error() -> None:
    """[Graceful degradation] `_rename_legacy_table` must swallow `sqlite3.OperationalError`
    raised by `ALTER TABLE` itself when a RE-CHECK proves another process already finished the
    rename (`flow_reservations` now exists) — not just reach the same outcome via the
    membership-check skip already covered by the idempotent-construction test above."""
    system = SQLiteReservationSystem.__new__(SQLiteReservationSystem)
    select_call_count = 0

    def fake_execute(sql, *_args, **_kwargs):
        nonlocal select_call_count
        stripped = sql.strip()
        if stripped.startswith("SELECT name FROM sqlite_master"):
            select_call_count += 1
            if select_call_count == 1:
                return [("sw_reservations",)]
            return [("sw_reservations",), ("flow_reservations",)]
        if stripped.startswith("ALTER TABLE sw_reservations"):
            raise sqlite3.OperationalError("no such table: sw_reservations")
        raise AssertionError(f"unexpected SQL: {sql}")

    mock_conn = mock.MagicMock()
    mock_conn.execute.side_effect = fake_execute

    system._rename_legacy_table(mock_conn)  # must not raise

    mock_conn.execute.assert_any_call("ALTER TABLE sw_reservations RENAME TO flow_reservations")


def test_sqlite_reservation_rename_reraises_genuine_operational_errors() -> None:
    """[Hostile] A genuine `OperationalError` during the `ALTER TABLE` (disk I/O failure, lock
    contention, corruption) that is NOT explained by "another process already finished the
    rename" must propagate, not be silently swallowed. Swallowing it unconditionally would let
    `_ensure_schema()` proceed straight to `CREATE TABLE IF NOT EXISTS flow_reservations`,
    creating an empty new table and silently orphaning every held lock in the untouched old
    table — `reservation.py`'s `_get_connection()` sets no `busy_timeout`, so lock contention
    under this system's own thundering-herd concurrency usage is a real, not theoretical, cause
    for `ALTER TABLE` to raise `OperationalError` for a reason OTHER than the benign race."""
    system = SQLiteReservationSystem.__new__(SQLiteReservationSystem)

    def fake_execute(sql, *_args, **_kwargs):
        stripped = sql.strip()
        if stripped.startswith("SELECT name FROM sqlite_master"):
            return [("sw_reservations",)]  # flow_reservations never appears
        if stripped.startswith("ALTER TABLE sw_reservations"):
            raise sqlite3.OperationalError("database is locked")
        raise AssertionError(f"unexpected SQL: {sql}")

    mock_conn = mock.MagicMock()
    mock_conn.execute.side_effect = fake_execute

    with pytest.raises(sqlite3.OperationalError, match="database is locked"):
        system._rename_legacy_table(mock_conn)


def test_sqlite_reservation_thundering_herd_concurrency(tmp_path: Path) -> None:
    """The Thundering Herd Concurrency Test: 50 threads firing exactly simultaneously.
    Proves SQLite's ACID integrity bound naturally prevents collisions natively.
    """
    db_path = tmp_path / "reservations.db"
    # Pre-init schema natively
    _system = SQLiteReservationSystem(db_path)

    results = []

    def hammer_lock(thread_id: int) -> bool:
        # Each thread instantiates a rapid connection natively bypassing GIL bottlenecks
        local_system = SQLiteReservationSystem(db_path)
        return local_system.acquire("port:9000", f"run-{thread_id}")

    # Hammer it with ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(hammer_lock, i) for i in range(50)]
        for future in as_completed(futures):
            results.append(future.result())

    # Strictly 1 acquisition should succeed, 49 should yield False via IntegrityError
    assert results.count(True) == 1
    assert results.count(False) == 49
