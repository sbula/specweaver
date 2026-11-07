# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A new `specweaver.db` and one upgraded from the release before have the same schema.

Proves: TECH-090 FR-6

Compared table by table: columns (name, type, NOT NULL, default, key) and indexes (name, unique,
columns). The one allowed difference is the SQL default of four columns in files Alembic made
`[agreed 2026-11-07]`; any other difference fails.

| Bucket | Case |
|---|---|
| Happy | the two schemas are equal |
| Boundary | the allowed difference covers exactly the four named columns |
| Degradation | a missing index in the upgraded file is a difference |
| Hostile | a column with another type is a difference |
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import TYPE_CHECKING

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database

from .test_config_db_steps import old_file

if TYPE_CHECKING:
    from pathlib import Path

#: Files Alembic made carry SQL defaults the code no longer declares; the code sets the values
#: itself (`register_project`), so the difference is cosmetic.
ALLOWED_DEFAULTS = {
    ("workspace_projects", "log_level"),
    ("workspace_projects", "auto_bootstrap_constitution"),
    ("workspace_projects", "stitch_mode"),
    ("workspace_projects", "default_dal"),
}


def schema(path: Path) -> dict[str, object]:
    """Every table's columns and indexes, as SQLite reports them."""
    with closing(sqlite3.connect(path)) as conn:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        out: dict[str, object] = {}
        for table in sorted(tables):
            columns = {
                r[1]: (r[2], r[3], None if (table, r[1]) in ALLOWED_DEFAULTS else r[4], r[5])
                for r in conn.execute(f"PRAGMA table_info({table})")
            }
            indexes = {
                r[1]: (r[2], tuple(c[2] for c in conn.execute(f"PRAGMA index_info({r[1]})")))
                for r in conn.execute(f"PRAGMA index_list({table})")
            }
            out[table] = (columns, indexes)
        return out


def test_a_new_file_and_an_upgraded_one_have_the_same_schema(tmp_path: Path) -> None:
    new, old = tmp_path / "new.db", old_file(tmp_path / "old.db")

    bootstrap_database(str(new))
    bootstrap_database(str(old))

    assert schema(old) == schema(new)


def test_a_missing_index_is_a_difference(tmp_path: Path) -> None:
    new, old = tmp_path / "new.db", old_file(tmp_path / "old.db")
    bootstrap_database(str(new))
    bootstrap_database(str(old))
    with closing(sqlite3.connect(old)) as conn:
        conn.execute("DROP INDEX ux_llm_price_once")
        conn.commit()

    assert schema(old) != schema(new)


def test_a_column_with_another_type_is_a_difference(tmp_path: Path) -> None:
    a, b = tmp_path / "a.db", tmp_path / "b.db"
    for path, kind in ((a, "VARCHAR"), (b, "TEXT")):
        with closing(sqlite3.connect(path)) as conn:
            conn.execute(f"CREATE TABLE t (x {kind})")

    assert schema(a) != schema(b)


def test_the_allowed_difference_is_the_four_defaults_and_no_other(tmp_path: Path) -> None:
    a, b = tmp_path / "a.db", tmp_path / "b.db"
    with closing(sqlite3.connect(a)) as conn:
        conn.execute("CREATE TABLE workspace_projects (log_level VARCHAR DEFAULT 'DEBUG', x TEXT)")
    with closing(sqlite3.connect(b)) as conn:
        conn.execute("CREATE TABLE workspace_projects (log_level VARCHAR, x TEXT DEFAULT 'y')")

    left, right = schema(a)["workspace_projects"], schema(b)["workspace_projects"]

    assert left[0]["log_level"] == right[0]["log_level"]  # type: ignore[index]
    assert left[0]["x"] != right[0]["x"]  # type: ignore[index]
