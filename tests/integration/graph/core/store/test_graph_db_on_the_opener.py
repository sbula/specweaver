# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`graph.db` is opened through the one opener and versioned like every other file.

Proves: TECH-090 FR-1
Proves: TECH-090 FR-2

| Bucket | Case |
|---|---|
| Happy | a new file reads back WAL, foreign keys and the 30 s wait (5 s before), at version 1 |
| Boundary | a file from before versioning keeps its nodes and edges |
| Degradation | a file from an old release (`nodes`, `edges`) keeps them under the new names |
| Hostile | a file from a newer SpecWeaver is refused, naming the file |
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import TYPE_CHECKING

import pytest

from specweaver.graph.core.store.repository import SqliteGraphRepository
from specweaver.infrastructure.database import SchemaTooNewError

if TYPE_CHECKING:
    from pathlib import Path

_NODES = (
    "CREATE TABLE {} (id INTEGER PRIMARY KEY AUTOINCREMENT, semantic_hash TEXT UNIQUE,"
    " clone_hash TEXT, file_id TEXT, service_name TEXT, package_name TEXT,"
    " is_active INTEGER DEFAULT 1, metadata JSON)"
)
_EDGES = (
    "CREATE TABLE {} (source_id INTEGER, target_id INTEGER, type TEXT, metadata JSON,"
    " PRIMARY KEY (source_id, target_id, type), FOREIGN KEY (source_id) REFERENCES {}(id)"
    " ON DELETE CASCADE)"
)


def _read(path: Path, sql: str) -> list[tuple[object, ...]]:
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute(sql).fetchall()


def _old_file(path: Path, nodes: str, edges: str) -> None:
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(_NODES.format(nodes))
        conn.execute(_EDGES.format(edges, nodes))
        conn.execute(f"INSERT INTO {nodes} (semantic_hash, service_name) VALUES ('h1', 'svc')")
        conn.execute(f"INSERT INTO {edges} VALUES (1, 2, 'CALLS', NULL)")
        conn.commit()


def test_a_new_file_gets_the_settings_and_version_1(tmp_path: Path) -> None:
    repo = SqliteGraphRepository(str(tmp_path / "graph.db"), "svc")

    with closing(repo._get_connection()) as conn:
        settings = [
            conn.execute(f"PRAGMA {name}").fetchone()[0]
            for name in ("journal_mode", "foreign_keys", "busy_timeout")
        ]
    assert settings == ["wal", 1, 30000]
    assert _read(tmp_path / "graph.db", "PRAGMA user_version") == [(1,)]


def test_a_file_from_before_versioning_keeps_its_graph(tmp_path: Path) -> None:
    path = tmp_path / "graph.db"
    _old_file(path, "graph_nodes", "graph_edges")

    SqliteGraphRepository(str(path), "svc")

    assert _read(path, "SELECT semantic_hash FROM graph_nodes") == [("h1",)]
    assert _read(path, "SELECT type FROM graph_edges") == [("CALLS",)]


def test_a_file_from_an_old_release_keeps_its_graph_under_the_new_names(tmp_path: Path) -> None:
    path = tmp_path / "graph.db"
    _old_file(path, "nodes", "edges")

    SqliteGraphRepository(str(path), "svc")

    assert _read(path, "SELECT semantic_hash FROM graph_nodes") == [("h1",)]
    assert _read(path, "SELECT type FROM graph_edges") == [("CALLS",)]


def test_a_file_from_a_newer_specweaver_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "graph.db"
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA user_version = 9")

    with pytest.raises(SchemaTooNewError, match=r"graph\.db"):
        SqliteGraphRepository(str(path), "svc")
