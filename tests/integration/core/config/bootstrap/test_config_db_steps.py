# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`specweaver.db` carries its schema version in `PRAGMA user_version`; step 1 is today's schema.

Proves: TECH-090 FR-5

The old file is built from `tests/fixtures/specweaver_db_before_tech_090.sql`, the schema the
release before this ticket made, frozen before the code changed.

| Bucket | Case |
|---|---|
| Happy | a new file ends at version 1; a file from the release before ends at 1 with every row |
| Boundary | a second run in a new process changes nothing; a leftover `alembic_version` is dropped |
| Degradation | a failure inside step 1 leaves the file at 0 and raises, naming the step |
| Hostile | a file with the table names from before 2026-07-12 is refused and left as it was |
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from specweaver.core.config.bootstrap import db_bootstrap
from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.infrastructure.database import SchemaStepError
from specweaver.infrastructure.database import steps as runner

_BEFORE = Path(__file__).resolve().parents[4] / "fixtures" / "specweaver_db_before_tech_090.sql"


def _read(path: Path, sql: str) -> list[tuple[object, ...]]:
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute(sql).fetchall()


def _tables(path: Path) -> set[str]:
    return {r[0] for r in _read(path, "SELECT name FROM sqlite_master WHERE type='table'")}


def old_file(path: Path) -> Path:
    """A file as the release before this ticket left it, with a project and one model call."""
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript(_BEFORE.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO workspace_projects (name, root_path, created_at, last_used_at, log_level,"
            " console_log_level, constitution_max_size, auto_bootstrap_constitution, stitch_mode,"
            " default_dal) VALUES ('shop', '/w/shop', 't0', 't0', 'DEBUG', 'WARNING', 5000,"
            " 'prompt', 'off', 'DAL_C')"
        )
        conn.execute(
            "INSERT INTO llm_usage_log (timestamp, project_name, task_type, model, provider,"
            " prompt_tokens, completion_tokens, total_tokens, duration_ms, call_status)"
            " VALUES ('t0', 'shop', 'review', 'm', 'p', 1, 2, 3, 4, 'ok')"
        )
        conn.commit()
    return path


def test_a_new_file_ends_at_version_1(tmp_path: Path) -> None:
    bootstrap_database(str(tmp_path / "specweaver.db"))

    assert _read(tmp_path / "specweaver.db", "PRAGMA user_version") == [(1,)]
    assert "workspace_projects" in _tables(tmp_path / "specweaver.db")


def test_a_file_from_the_release_before_keeps_every_row(tmp_path: Path) -> None:
    path = old_file(tmp_path / "specweaver.db")

    bootstrap_database(str(path))

    assert _read(path, "PRAGMA user_version") == [(1,)]
    assert _read(path, "SELECT name, default_dal FROM workspace_projects") == [("shop", "DAL_C")]
    assert _read(path, "SELECT total_tokens FROM llm_usage_log") == [(3,)]


def test_a_second_run_in_a_new_process_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = old_file(tmp_path / "specweaver.db")
    bootstrap_database(str(path))
    before = _read(path, "SELECT type, name, sql FROM sqlite_master ORDER BY name")
    monkeypatch.setattr(runner, "_UPGRADED", set())

    bootstrap_database(str(path))

    assert _read(path, "SELECT type, name, sql FROM sqlite_master ORDER BY name") == before


def test_a_leftover_alembic_version_is_dropped(tmp_path: Path) -> None:
    path = old_file(tmp_path / "specweaver.db")
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
        conn.execute("INSERT INTO alembic_version VALUES ('af60fd3509a2')")
        conn.commit()

    bootstrap_database(str(path))

    assert "alembic_version" not in _tables(path)


def test_a_failure_inside_step_1_leaves_the_file_at_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = old_file(tmp_path / "specweaver.db")

    def _fail(conn: sqlite3.Connection) -> None:
        raise RuntimeError("planted inside step 1")

    monkeypatch.setattr(db_bootstrap, "_add_price_index", _fail)

    with pytest.raises(SchemaStepError, match="planted inside step 1"):
        bootstrap_database(str(path))

    assert _read(path, "PRAGMA user_version") == [(0,)]


def test_a_file_with_the_old_table_names_is_refused_and_left_alone(tmp_path: Path) -> None:
    path = tmp_path / "specweaver.db"
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE projects (name TEXT PRIMARY KEY, root_path TEXT)")
        conn.execute("INSERT INTO projects VALUES ('old', '/w/old')")
        conn.commit()

    with pytest.raises(SchemaStepError, match="2026-07-12"):
        bootstrap_database(str(path))

    assert _tables(path) == {"projects"}
    assert _read(path, "PRAGMA user_version") == [(0,)]


def test_a_new_file_prints_nothing_to_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`sw run --json` streams NDJSON on stdout; a first run on a new machine creates the file."""
    bootstrap_database(str(tmp_path / "specweaver.db"))

    assert capsys.readouterr().out == ""


def test_a_failed_price_seed_warns_and_keeps_the_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Seeding is data, not schema: a broken shipped list warns `[agreed 2026-11-07]`."""
    from specweaver.core.config.settings_file import SettingsFileError

    def _broken() -> None:
        raise SettingsFileError("catalogue.toml", "prices", 1, "unreadable")

    monkeypatch.setattr(db_bootstrap, "shipped_catalogue", _broken)

    bootstrap_database(str(tmp_path / "specweaver.db"))

    assert _read(tmp_path / "specweaver.db", "PRAGMA user_version") == [(1,)]
    assert "Shipped prices not stored" in caplog.text


def test_an_older_refresh_table_gains_reached_at(tmp_path: Path) -> None:
    path = old_file(tmp_path / "specweaver.db")
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("ALTER TABLE llm_price_refresh DROP COLUMN reached_at")
        conn.commit()

    bootstrap_database(str(path))

    assert "reached_at" in {r[1] for r in _read(path, "PRAGMA table_info(llm_price_refresh)")}
