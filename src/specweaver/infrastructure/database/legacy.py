# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Renaming a table an old release named differently, in place, keeping its rows."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def rename_legacy_tables(conn: sqlite3.Connection, renames: Iterable[tuple[str, str]]) -> None:
    """Rename each `(old, new)` table whose old name exists and new name does not.

    Both names present is left alone: a half-moved file must not lose either table. A rename that
    fails is ignored only when the new table exists afterwards, because another process finished
    it; any other failure is raised, so the caller does not create an empty table beside the data.
    """
    for old, new in renames:
        existing = _tables(conn)
        if old not in existing or new in existing:
            continue
        try:
            conn.execute(f"ALTER TABLE {old} RENAME TO {new}")
        except sqlite3.OperationalError:
            if new not in _tables(conn):
                raise
