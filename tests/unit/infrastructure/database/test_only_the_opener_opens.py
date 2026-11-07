# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Only `infrastructure/database/` opens a SQLite file; a second opener is a failing test.

Proves: TECH-090 FR-1

The allowlist names the openers not moved yet, and shrinks: `core/flow/engine/store.py` leaves it
in SF-01 CB-3, the rest in SF-02. A name on it that no longer opens a file fails too.

| Bucket | Case |
|---|---|
| Happy | today's tree opens SQLite only in the opener and the listed files |
| Boundary | an allowlisted file that stopped opening one must leave the list |
| Hostile | a planted `sqlite3.connect`, `from sqlite3 import connect as c`, `create_async_engine` is caught |
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[4] / "src" / "specweaver"
_OPENER = _SRC / "infrastructure" / "database"
_NOT_MOVED_YET = {
    "core/config/database.py",
    "core/config/bootstrap/db_bootstrap.py",
}
_OPENERS = {("sqlite3", "connect"), ("sqlalchemy", "create_engine")}
_OPENERS |= {("sqlalchemy.ext.asyncio", "create_async_engine")}


def _imported_openers(tree: ast.Module) -> set[str]:
    """Local names bound to an opener by `from … import …`, aliases included."""
    return {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
        for alias in node.names
        if (node.module, alias.name) in _OPENERS
    }


def _is_opener(func: ast.expr, imported: set[str]) -> bool:
    if isinstance(func, ast.Name):
        return func.id in imported
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return (func.value.id, func.attr) == ("sqlite3", "connect") or func.attr in {
            "create_engine",
            "create_async_engine",
        }
    return False


def opens_sqlite(source: str) -> bool:
    """Whether the module calls `sqlite3.connect`, `create_engine` or `create_async_engine`."""
    tree = ast.parse(source)
    imported = _imported_openers(tree)
    return any(
        _is_opener(node.func, imported) for node in ast.walk(tree) if isinstance(node, ast.Call)
    )


def _openers() -> set[str]:
    return {
        path.relative_to(_SRC).as_posix()
        for path in _SRC.rglob("*.py")
        if _OPENER not in path.parents and opens_sqlite(path.read_text(encoding="utf-8"))
    }


def test_only_the_opener_and_the_files_not_moved_yet_open_sqlite() -> None:
    assert _openers() - _NOT_MOVED_YET == set()


def test_a_file_that_moved_leaves_the_allowlist() -> None:
    assert _NOT_MOVED_YET - _openers() == set()


@pytest.mark.parametrize(
    "planted",
    [
        "import sqlite3\nsqlite3.connect('x.db')\n",
        "from sqlite3 import connect as c\nc('x.db')\n",
        "from sqlalchemy.ext.asyncio import create_async_engine\ncreate_async_engine('sqlite://')\n",
        "import sqlalchemy\nsqlalchemy.create_engine('sqlite://')\n",
    ],
)
def test_a_planted_opener_is_caught(planted: str) -> None:
    assert opens_sqlite(planted)


def test_reading_a_connection_is_not_opening_one() -> None:
    assert not opens_sqlite("def f(conn):\n    return conn.execute('SELECT 1')\n")
