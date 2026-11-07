# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`pipeline_state.db` moves from its own version table to `PRAGMA user_version`, keeping every run.

Proves: TECH-090 FR-1
Proves: TECH-090 FR-4
Proves: TECH-090 NFR-1

Test files are built as each old release left them: v1 with the old table names and neither
`parent_run_id` nor `spend_state`, v2 with `parent_run_id`, v3 with the validation table, v4 as today.

| Bucket | Case |
|---|---|
| Happy | each of v1..v4 ends at `user_version` 1 with today's columns, its runs and no old version table |
| Boundary | a second open in a new process changes nothing; a new file starts at 1 |
| Degradation | a failure after `user_version` is set and before the old table is dropped undoes both |
| Hostile | a version the map does not know stops, naming it |
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.engine import store as state_store
from specweaver.core.flow.engine.store import StateStore
from specweaver.infrastructure.database import SchemaStepError
from specweaver.infrastructure.database import steps as runner

if TYPE_CHECKING:
    from pathlib import Path

_RUNS = """CREATE TABLE {runs} (
    run_id TEXT PRIMARY KEY, {parent}pipeline_name TEXT NOT NULL, project_name TEXT NOT NULL,
    spec_path TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'not_started',
    current_step INTEGER NOT NULL DEFAULT 0, step_records TEXT NOT NULL DEFAULT '[]',
    started_at TEXT NOT NULL, updated_at TEXT NOT NULL{spend})"""
_AUDIT = """CREATE TABLE {audit} (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL REFERENCES {runs}(run_id),
    timestamp TEXT NOT NULL, event TEXT NOT NULL, step_name TEXT, details TEXT)"""
_VERSION = "CREATE TABLE {version} (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
_VALIDATION = """CREATE TABLE flow_validation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, step_name TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 1, rule_id TEXT NOT NULL, rule_status TEXT NOT NULL,
    rule_message TEXT, finding_index INTEGER, message TEXT, line INTEGER, severity TEXT,
    suggestion TEXT, recorded_at TEXT NOT NULL)"""


def _old_file(path: Path, version: int, *, recorded: int | None = None) -> None:
    old = version == 1
    names = {
        "runs": "pipeline_runs" if old else "flow_pipeline_runs",
        "audit": "audit_log" if old else "flow_audit_log",
        "version": "state_schema_version" if old else "flow_state_schema_version",
    }
    parent = "parent_run_id TEXT, " if version >= 2 else ""
    spend = ", spend_state TEXT NOT NULL DEFAULT '{}'" if version >= 4 else ""
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(_RUNS.format(parent=parent, spend=spend, **names))
        conn.execute(_AUDIT.format(**names))
        conn.execute(_VERSION.format(**names))
        if version >= 3:
            conn.execute(_VALIDATION)
        conn.execute(
            f"INSERT INTO {names['runs']} (run_id, pipeline_name, project_name, spec_path,"
            " started_at, updated_at) VALUES ('run-1', 'p', 'proj', 's.md', 't0', 't0')"
        )
        conn.execute(
            f"INSERT INTO {names['audit']} (run_id, timestamp, event) VALUES ('run-1', 't0', 'x')"
        )
        conn.execute(
            f"INSERT INTO {names['version']} VALUES (?, 't0')",
            (version if recorded is None else recorded,),
        )
        conn.commit()


def _read(path: Path, sql: str) -> list[tuple[object, ...]]:
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute(sql).fetchall()


def _tables(path: Path) -> set[str]:
    return {r[0] for r in _read(path, "SELECT name FROM sqlite_master WHERE type='table'")}


@pytest.mark.parametrize("version", [1, 2, 3, 4])
def test_each_old_version_ends_at_1_with_its_runs(tmp_path: Path, version: int) -> None:
    path = tmp_path / "pipeline_state.db"
    _old_file(path, version)

    StateStore(path)

    assert _read(path, "PRAGMA user_version") == [(1,)]
    assert _read(path, "SELECT run_id FROM flow_pipeline_runs") == [("run-1",)]
    assert _read(path, "SELECT event FROM flow_audit_log") == [("x",)]
    columns = {r[1] for r in _read(path, "PRAGMA table_info(flow_pipeline_runs)")}
    assert {"parent_run_id", "spend_state"} <= columns
    tables = _tables(path)
    assert "flow_validation_results" in tables
    assert not tables & {"flow_state_schema_version", "state_schema_version", "pipeline_runs"}


def test_a_new_file_starts_at_1(tmp_path: Path) -> None:
    StateStore(tmp_path / "pipeline_state.db")

    assert _read(tmp_path / "pipeline_state.db", "PRAGMA user_version") == [(1,)]
    assert "flow_state_schema_version" not in _tables(tmp_path / "pipeline_state.db")


def test_a_second_open_in_a_new_process_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "pipeline_state.db"
    _old_file(path, 2)
    StateStore(path)
    before = _read(path, "SELECT sql FROM sqlite_master ORDER BY name")
    monkeypatch.setattr(runner, "_UPGRADED", set())

    StateStore(path)

    assert _read(path, "SELECT sql FROM sqlite_master ORDER BY name") == before
    assert _read(path, "PRAGMA user_version") == [(1,)]


def test_a_failure_before_the_old_table_is_dropped_undoes_the_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "pipeline_state.db"
    _old_file(path, 4)

    def _fail(conn: sqlite3.Connection) -> None:
        raise RuntimeError("planted before the drop")

    monkeypatch.setattr(state_store, "_drop_old_version_table", _fail)

    with pytest.raises(SchemaStepError, match="planted before the drop"):
        StateStore(path)

    assert _read(path, "PRAGMA user_version") == [(0,)]
    assert _read(path, "SELECT version FROM flow_state_schema_version") == [(4,)]


def test_a_version_the_map_does_not_know_stops_naming_it(tmp_path: Path) -> None:
    path = tmp_path / "pipeline_state.db"
    _old_file(path, 4, recorded=7)

    with pytest.raises(SchemaStepError, match="old schema version 7 is not one"):
        StateStore(path)

    assert _read(path, "SELECT version FROM flow_state_schema_version") == [(7,)]


def test_an_empty_version_table_is_read_as_a_new_file(tmp_path: Path) -> None:
    """The old code read an empty table as "new file" and recorded v4 without checking columns."""
    path = tmp_path / "pipeline_state.db"
    _old_file(path, 2)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("DELETE FROM flow_state_schema_version")
        conn.commit()

    StateStore(path)

    assert _read(path, "PRAGMA user_version") == [(1,)]
    assert "spend_state" in {r[1] for r in _read(path, "PRAGMA table_info(flow_pipeline_runs)")}
