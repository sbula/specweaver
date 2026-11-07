# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The one way a SpecWeaver SQLite file is opened: WAL, foreign keys, and the process's lock wait."""

from __future__ import annotations

import os
import sqlite3
import time
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from pathlib import Path

_DEFAULT_LOCK_WAIT = 30.0
_lock_wait = _DEFAULT_LOCK_WAIT


def set_lock_wait(seconds: float) -> None:
    """How long every connection of this process waits for a locked file; the door sets it once."""
    global _lock_wait
    if not seconds > 0:
        raise ValueError(f"the lock wait must be more than 0 seconds, not {seconds}")
    _lock_wait = float(seconds)


def lock_wait_seconds() -> float:
    """The lock wait every new connection of this process gets."""
    return _lock_wait


def _switch_to_wal(conn: Any) -> None:
    """Put the file into WAL, which the file keeps; retried, because the busy wait does not cover it.

    Switching needs the file to itself, and when two processes open a new file together SQLite
    answers `database is locked` at once instead of waiting.
    """
    deadline = time.monotonic() + _lock_wait
    while True:
        try:
            # An `aiosqlite` cursor's `execute` returns None; the row is then read from the cursor.
            result = conn.execute("PRAGMA journal_mode")
            if (result or conn).fetchone()[0] != "wal":
                conn.execute("PRAGMA journal_mode=WAL")
            return
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc) or time.monotonic() >= deadline:
                raise
            time.sleep(0.05)


def apply_pragmas(conn: Any) -> None:
    """The three settings: the wait, then WAL, then foreign keys (a no-op inside a transaction)."""
    conn.execute(f"PRAGMA busy_timeout = {int(_lock_wait * 1000)}")
    _switch_to_wal(conn)
    conn.execute("PRAGMA foreign_keys=ON")


def open_sqlite(
    path: Path | str,
    *,
    row_factory: Any = None,
    isolation_level: Literal["DEFERRED", "EXCLUSIVE", "IMMEDIATE"] | None = "DEFERRED",
) -> sqlite3.Connection:
    """A connection to `path` with WAL, foreign keys on and the process's lock wait."""
    # `os.fspath`, not `str`: anything that is not a path is refused instead of becoming a file name.
    conn = sqlite3.connect(os.fspath(path), timeout=_lock_wait, isolation_level=isolation_level)
    try:
        apply_pragmas(conn)
    except sqlite3.Error:
        conn.close()
        raise
    if row_factory is not None:
        conn.row_factory = row_factory
    return conn
