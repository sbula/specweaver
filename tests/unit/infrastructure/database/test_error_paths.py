# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The opener's and the rename helper's failures: what is raised, what is retried, what is closed.

Proves: TECH-090 FR-2

| Bucket | Case |
|---|---|
| Degradation | a rename another process finished is no error; a rename that fails for another reason is raised |
| Degradation | the WAL switch retries a lock and gives up at the lock wait; any other error is raised at once |
| Hostile | a connection whose settings fail is closed, not leaked |
"""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from specweaver.infrastructure.database import legacy, rename_legacy_tables, set_lock_wait
from specweaver.infrastructure.database import sqlite as opener


class _Rows:
    def __init__(self, rows: list[tuple[str]]) -> None:
        self._rows = rows

    def __iter__(self) -> Any:
        return iter(self._rows)

    def fetchone(self) -> tuple[str]:
        return self._rows[0]


class _RenameFails:
    """A connection whose ALTER fails; `finished_elsewhere` says whether the new table exists after."""

    def __init__(self, *, finished_elsewhere: bool) -> None:
        self.finished_elsewhere = finished_elsewhere
        self.altered = False

    def execute(self, sql: str) -> _Rows:
        if sql.startswith("ALTER"):
            self.altered = True
            raise sqlite3.OperationalError("disk I/O error")
        if self.altered and self.finished_elsewhere:
            return _Rows([("new_name",)])
        return _Rows([("old_name",)])


def test_a_rename_another_process_finished_is_no_error() -> None:
    conn = _RenameFails(finished_elsewhere=True)

    rename_legacy_tables(conn, (("old_name", "new_name"),))  # type: ignore[arg-type]

    assert conn.altered


def test_a_rename_that_failed_for_another_reason_is_raised() -> None:
    with pytest.raises(sqlite3.OperationalError, match="disk I/O"):
        rename_legacy_tables(_RenameFails(finished_elsewhere=False), (("old_name", "new_name"),))  # type: ignore[arg-type]


class _WalLocked:
    """`PRAGMA journal_mode` fails with `failures` errors, then reports `wal`."""

    def __init__(self, failures: int, message: str = "database is locked") -> None:
        self.failures, self.message, self.calls = failures, message, 0

    def execute(self, sql: str) -> _Rows:
        self.calls += 1
        if self.failures:
            self.failures -= 1
            raise sqlite3.OperationalError(self.message)
        return _Rows([("wal",)])


class _Clock:
    """Stands in for the opener's `time` only; the real one stays untouched for pytest."""

    def __init__(self, *ticks: float) -> None:
        self.ticks = list(ticks) or [0.0]

    def monotonic(self) -> float:
        return self.ticks.pop(0) if len(self.ticks) > 1 else self.ticks[0]

    def sleep(self, _seconds: float) -> None:
        return None


def test_the_wal_switch_retries_a_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(opener, "time", _Clock())
    conn = _WalLocked(failures=3)

    opener._switch_to_wal(conn)

    assert conn.calls == 4


def test_the_wal_switch_gives_up_at_the_lock_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    set_lock_wait(1)
    monkeypatch.setattr(opener, "time", _Clock(0.0, 0.5, 2.0))

    with pytest.raises(sqlite3.OperationalError, match="locked"):
        opener._switch_to_wal(_WalLocked(failures=99))


def test_any_other_error_is_raised_at_once() -> None:
    conn = _WalLocked(failures=1, message="disk I/O error")

    with pytest.raises(sqlite3.OperationalError, match="disk I/O"):
        opener._switch_to_wal(conn)
    assert conn.calls == 1


def test_a_connection_whose_settings_fail_is_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    closed: list[bool] = []

    class _Conn:
        def close(self) -> None:
            closed.append(True)

    monkeypatch.setattr(opener.sqlite3, "connect", lambda *a, **k: _Conn())

    def _fail(conn: Any) -> None:
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(opener, "apply_pragmas", _fail)

    with pytest.raises(sqlite3.OperationalError):
        opener.open_sqlite(tmp_path / "a.db")
    assert closed == [True]


def test_the_helper_module_is_the_one_copy() -> None:
    assert rename_legacy_tables is legacy.rename_legacy_tables
