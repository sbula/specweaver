# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An existing database learns that a call's cost can be unknown, and keeps its history.

Proves: C-FLOW-13 FR-12, FR-15

Alembic never runs at start-up, so the start-up itself rebuilds the one table (AD in the SF-03 plan).

| Bucket | Case |
|---|---|
| Happy | an old table with a NOT NULL cost column → rebuilt; an unknown cost can be stored |
| Boundary | the rebuild runs again on the next start and changes nothing |
| Degradation | not applicable — a missing table is created fresh by `create_all` |
| Hostile | the old rows and their indexes survive the rebuild |
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database

if TYPE_CHECKING:
    from pathlib import Path

_OLD_TABLE = """
CREATE TABLE llm_usage_log (
    id INTEGER NOT NULL PRIMARY KEY,
    timestamp VARCHAR NOT NULL,
    project_name VARCHAR NOT NULL,
    task_type VARCHAR NOT NULL,
    model VARCHAR NOT NULL,
    provider VARCHAR NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    estimated_cost FLOAT NOT NULL,
    duration_ms INTEGER NOT NULL,
    run_id VARCHAR
);
CREATE INDEX ix_llm_usage_log_project_name ON llm_usage_log (project_name);
CREATE INDEX ix_llm_usage_log_task_type ON llm_usage_log (task_type);
INSERT INTO llm_usage_log VALUES
    (1, '2026-09-01T10:00:00+00:00', 'demo', 'review', 'gemini-2.5-pro', 'gemini',
     10, 5, 15, 0.25, 900, 'run-1');
"""

_UNKNOWN_COST = (
    "INSERT INTO llm_usage_log (timestamp, project_name, task_type, model, provider, prompt_tokens,"
    " completion_tokens, total_tokens, estimated_cost, duration_ms, run_id) VALUES"
    " ('2026-09-27T10:00:00+00:00', 'demo', 'draft', 'qwen3-coder-next', 'openai-compatible',"
    " 1, 1, 2, NULL, 10, 'run-2')"
)


def _cost_is_required(db: Path) -> bool:
    with sqlite3.connect(db) as conn:
        columns = conn.execute("PRAGMA table_info(llm_usage_log)").fetchall()
    return next(col[3] for col in columns if col[1] == "estimated_cost") == 1


def test_an_old_database_can_store_an_unknown_cost_and_keeps_its_rows(tmp_path: Path) -> None:
    db = tmp_path / "specweaver.db"
    with sqlite3.connect(db) as conn:
        conn.executescript(_OLD_TABLE)

    bootstrap_database(str(db))
    bootstrap_database(str(db))  # the next start: nothing left to do

    assert not _cost_is_required(db)
    with sqlite3.connect(db) as conn:
        conn.execute(_UNKNOWN_COST)
        rows = conn.execute(
            "SELECT model, estimated_cost FROM llm_usage_log ORDER BY id"
        ).fetchall()
        indexes = {row[1] for row in conn.execute("PRAGMA index_list(llm_usage_log)")}
    assert rows == [("gemini-2.5-pro", 0.25), ("qwen3-coder-next", None)]
    assert {"ix_llm_usage_log_project_name", "ix_llm_usage_log_task_type"} <= indexes


def test_the_retired_llm_settings_tables_are_dropped(tmp_path: Path) -> None:
    """LLM settings live in the settings files only (C-FLOW-13 FR-15): the old tables go."""
    db = tmp_path / "specweaver.db"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            "CREATE TABLE llm_profiles (id INTEGER PRIMARY KEY, name VARCHAR);"
            "INSERT INTO llm_profiles VALUES (1, 'system-default');"
            "CREATE TABLE llm_project_links (project_name VARCHAR, role VARCHAR, profile_id INT);"
            "CREATE TABLE llm_cost_overrides (model_pattern VARCHAR PRIMARY KEY);"
        )

    bootstrap_database(str(db))
    bootstrap_database(str(db))

    with sqlite3.connect(db) as conn:
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert not {"llm_profiles", "llm_project_links", "llm_cost_overrides"} & tables
    assert "llm_usage_log" in tables
