# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import sqlite3
from unittest import mock

import pytest

from specweaver.graph.core.store.repository import SqliteGraphRepository


def test_sqlite_repository_initialization_creates_schema(tmp_path):
    """Test that initializing the repository creates the SQLite database and schema."""
    db_path = tmp_path / "graph.db"

    # Initialize repository
    SqliteGraphRepository(str(db_path), validated_service_name="test_service")

    # Verify the database file was created
    assert db_path.exists()

    # Verify the schema was applied by querying sqlite_master
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}

        assert "graph_nodes" in tables
        assert "graph_edges" in tables

        # Verify PRAGMA journal_mode=WAL
        cursor.execute("PRAGMA journal_mode;")
        journal_mode = cursor.fetchone()[0]
        assert journal_mode.upper() == "WAL"


def test_sqlite_repository_nodes_schema(tmp_path):
    """Test that the graph_nodes table has the correct columns."""
    db_path = tmp_path / "graph.db"
    SqliteGraphRepository(str(db_path), validated_service_name="test_service")

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(graph_nodes);")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected_columns = {
            "id": "INTEGER",
            "semantic_hash": "TEXT",
            "clone_hash": "TEXT",
            "file_id": "TEXT",
            "service_name": "TEXT",
            "package_name": "TEXT",
            "is_active": "INTEGER",
            "metadata": "JSON",
        }

        for col_name, col_type in expected_columns.items():
            assert col_name in columns
            assert columns[col_name] == col_type


def test_sqlite_repository_edges_schema(tmp_path):
    """Test that the graph_edges table has the correct columns and no strict FK on target_id."""
    db_path = tmp_path / "graph.db"
    SqliteGraphRepository(str(db_path), validated_service_name="test_service")

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(graph_edges);")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected_columns = {
            "source_id": "INTEGER",
            "target_id": "INTEGER",
            "type": "TEXT",
            "metadata": "JSON",
        }

        for col_name, col_type in expected_columns.items():
            assert col_name in columns
            assert columns[col_name] == col_type

        # Verify Foreign Keys (there should be NO FK on target_id due to LAZY edges)
        cursor.execute("PRAGMA foreign_key_list(graph_edges);")
        fk_list = cursor.fetchall()

        # It's okay if source_id has an FK, but target_id MUST NOT have one.
        for fk in fk_list:
            from_col = fk[3]
            assert from_col != "target_id", "target_id must not have a strict Foreign Key!"


def test_sqlite_repository_migrates_legacy_table_names_preserving_data(tmp_path):
    """TECH-005 FR-8: an installation with the pre-SF-3 unprefixed `nodes`/`edges` tables already
    on disk must be migrated to `graph_nodes`/`graph_edges` in place, with every row preserved and
    the `edges.source_id -> nodes(id)` foreign key still enforcing correctly afterward — a blind
    `CREATE TABLE IF NOT EXISTS graph_nodes` would instead create an empty new table alongside the
    untouched old one, silently orphaning every previously persisted graph.
    """
    db_path = tmp_path / "graph.db"

    # Build a raw pre-SF-3 database by hand, bypassing the repository entirely.
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                semantic_hash TEXT UNIQUE,
                clone_hash TEXT,
                file_id TEXT,
                service_name TEXT,
                package_name TEXT,
                is_active INTEGER DEFAULT 1,
                metadata JSON
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE edges (
                source_id INTEGER,
                target_id INTEGER,
                type TEXT,
                metadata JSON,
                PRIMARY KEY (source_id, target_id, type),
                FOREIGN KEY (source_id) REFERENCES nodes(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "INSERT INTO nodes (semantic_hash, clone_hash, file_id, service_name, package_name, "
            "is_active, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("svc:ast:1", "c1", "file1", "svc", "pkg1", 1, "{}"),
        )
        conn.execute(
            "INSERT INTO edges (source_id, target_id, type, metadata) VALUES (1, 1, 'CALLS', '{}')"
        )
        conn.commit()

    # Instantiating the repository against the SAME file must migrate, not orphan.
    repo = SqliteGraphRepository(str(db_path), validated_service_name="svc")

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        assert "nodes" not in tables and "edges" not in tables, "old-named tables must not remain"
        assert {"graph_nodes", "graph_edges"} <= tables

        cursor.execute("SELECT semantic_hash, clone_hash FROM graph_nodes")
        assert cursor.fetchall() == [("svc:ast:1", "c1")]

        cursor.execute("SELECT source_id, target_id, type FROM graph_edges")
        assert cursor.fetchall() == [(1, 1, "CALLS")]

        # FK integrity must still enforce post-rename: inserting an edge whose source_id has no
        # matching graph_nodes row must fail, not silently succeed.
        conn.execute("PRAGMA foreign_keys=ON;")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO graph_edges (source_id, target_id, type, metadata) "
                "VALUES (999, 1, 'CALLS', '{}')"
            )

    # And the repository's own public API must work normally against the migrated tables.
    assert repo.get_all_file_hashes() == {"file1": "c1"}


def test_sqlite_repository_skips_rename_when_both_old_and_new_tables_exist(tmp_path):
    """[Graceful degradation] A partially-migrated or corrupt DB with BOTH `nodes` and
    `graph_nodes` present must not raise and must not drop either table — it logs and proceeds
    using the new-named table, which every current code path already expects."""
    db_path = tmp_path / "graph.db"

    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE nodes (id INTEGER PRIMARY KEY, semantic_hash TEXT)")
        conn.execute("INSERT INTO nodes (semantic_hash) VALUES ('orphaned')")
        # Pre-create the new-named table too, so a rename target already exists — otherwise
        # construction would just rename `nodes` -> `graph_nodes` normally and never exercise
        # the "both already exist" branch at all.
        conn.execute("CREATE TABLE graph_nodes (id INTEGER PRIMARY KEY, semantic_hash TEXT)")
        conn.commit()

    # Should not raise even though both `nodes` and `graph_nodes` already exist.
    SqliteGraphRepository(str(db_path), validated_service_name="svc")

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        assert "nodes" in tables, "the old table must be left alone, not dropped"
        assert "graph_nodes" in tables


def test_sqlite_repository_rename_is_idempotent_across_repeated_construction(tmp_path):
    """[Robustness] Two `SqliteGraphRepository` instances constructed back-to-back against the
    same legacy-named DB (simulating a second process racing at startup) must not raise on the
    second construction — the first already renamed the table out from under it."""
    db_path = tmp_path / "graph.db"

    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE nodes (id INTEGER PRIMARY KEY, semantic_hash TEXT)")
        conn.commit()

    SqliteGraphRepository(str(db_path), validated_service_name="svc")
    SqliteGraphRepository(str(db_path), validated_service_name="svc")  # must not raise

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        assert "graph_nodes" in tables
        assert "nodes" not in tables


def test_sqlite_repository_resumes_a_half_migrated_state(tmp_path):
    """[Robustness] `ALTER TABLE`/`CREATE TABLE` are DDL — each auto-commits independently in
    Python's `sqlite3` module, NOT as one atomic unit protected by `with conn:` (empirically
    verified: a `with sqlite3.connect(...) as conn:` block does not roll back an already-executed
    `ALTER TABLE` when a later statement in the same block raises). A process killed between
    renaming `nodes` and renaming `edges` therefore leaves a genuinely half-migrated DB on disk —
    `graph_nodes` present, `edges` still old-named. The very next construction must complete the
    interrupted migration correctly (not error, not skip the still-pending table)."""
    db_path = tmp_path / "graph.db"

    with sqlite3.connect(db_path) as conn:
        # Simulate the exact half-migrated state: `nodes` already renamed, `edges` still old,
        # with real data in both — proving no data is lost by the resumed rename either.
        conn.execute(
            "CREATE TABLE graph_nodes (id INTEGER PRIMARY KEY AUTOINCREMENT, semantic_hash TEXT "
            "UNIQUE, clone_hash TEXT, file_id TEXT, service_name TEXT, package_name TEXT, "
            "is_active INTEGER DEFAULT 1, metadata JSON)"
        )
        conn.execute(
            "CREATE TABLE edges (source_id INTEGER, target_id INTEGER, type TEXT, metadata JSON, "
            "PRIMARY KEY (source_id, target_id, type), "
            "FOREIGN KEY (source_id) REFERENCES graph_nodes(id) ON DELETE CASCADE)"
        )
        conn.execute(
            "INSERT INTO graph_nodes (semantic_hash, service_name, is_active) VALUES "
            "('svc:ast:1', 'svc', 1)"
        )
        conn.execute("INSERT INTO edges (source_id, target_id, type) VALUES (1, 1, 'CALLS')")
        conn.commit()

    SqliteGraphRepository(str(db_path), validated_service_name="svc")

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        assert "edges" not in tables
        assert "graph_edges" in tables

        cursor.execute("SELECT semantic_hash FROM graph_nodes")
        assert cursor.fetchall() == [("svc:ast:1",)]
        cursor.execute("SELECT source_id, target_id, type FROM graph_edges")
        assert cursor.fetchall() == [(1, 1, "CALLS")]


def test_sqlite_repository_rename_swallows_concurrent_operational_error():
    """[Graceful degradation] `_rename_legacy_tables` must swallow `sqlite3.OperationalError`
    raised by the `ALTER TABLE` statement itself when a RE-CHECK proves another process already
    finished the rename (`graph_nodes` now exists) — not just reach the same outcome via the
    membership-check skip already covered by the idempotent-construction test above."""
    repo = SqliteGraphRepository.__new__(SqliteGraphRepository)
    select_call_count = 0

    def fake_execute(sql, *_args, **_kwargs):
        nonlocal select_call_count
        stripped = sql.strip()
        if stripped.startswith("SELECT name FROM sqlite_master"):
            select_call_count += 1
            # First check (before the rename attempt): only `nodes` present.
            # Re-check (after the ALTER raised): the concurrent process has now finished —
            # `graph_nodes` exists too, proving the error really was the benign race.
            if select_call_count == 1:
                return [("nodes",)]
            return [("nodes",), ("graph_nodes",)]
        if stripped.startswith("ALTER TABLE nodes"):
            raise sqlite3.OperationalError("no such table: nodes")
        raise AssertionError(f"unexpected SQL: {sql}")

    mock_conn = mock.MagicMock()
    mock_conn.execute.side_effect = fake_execute

    repo._rename_legacy_tables(mock_conn)  # must not raise

    mock_conn.execute.assert_any_call("ALTER TABLE nodes RENAME TO graph_nodes")


def test_sqlite_repository_rename_reraises_genuine_operational_errors():
    """[Hostile] A genuine `OperationalError` during the `ALTER TABLE` (disk I/O failure, lock
    contention, corruption) that is NOT explained by "another process already finished the
    rename" must propagate, not be silently swallowed. Swallowing it unconditionally would let
    `_init_db()` proceed straight to `CREATE TABLE IF NOT EXISTS graph_nodes`, creating an empty
    new table and silently orphaning the untouched old `nodes` table's data — exactly the failure
    mode this whole migration exists to prevent."""
    repo = SqliteGraphRepository.__new__(SqliteGraphRepository)

    def fake_execute(sql, *_args, **_kwargs):
        stripped = sql.strip()
        if stripped.startswith("SELECT name FROM sqlite_master"):
            return [("nodes",)]  # `graph_nodes` never appears -> not actually renamed elsewhere
        if stripped.startswith("ALTER TABLE nodes"):
            raise sqlite3.OperationalError("disk I/O error")
        raise AssertionError(f"unexpected SQL: {sql}")

    mock_conn = mock.MagicMock()
    mock_conn.execute.side_effect = fake_execute

    with pytest.raises(sqlite3.OperationalError, match="disk I/O error"):
        repo._rename_legacy_tables(mock_conn)
