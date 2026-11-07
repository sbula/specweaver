# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import logging
import sqlite3
from pathlib import Path

from sqlalchemy import MetaData, Table
from sqlalchemy.dialects import sqlite as sqlite_dialect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.schema import CreateIndex, CreateTable

import specweaver.workspace.memory.store  # noqa: F401
from specweaver.core.config.paths import config_db_path
from specweaver.core.config.settings_file import SettingsFileError
from specweaver.core.flow.store import Base as FlowBase
from specweaver.infrastructure.database import Database, Step, upgrade
from specweaver.infrastructure.llm.catalogue import shipped_catalogue
from specweaver.infrastructure.llm.price_store import seed_prices
from specweaver.infrastructure.llm.store import Base as LlmBase
from specweaver.workspace.store import Base as WorkspaceBase

logger = logging.getLogger(__name__)


#: LLM settings tables the database no longer holds: every LLM setting lives in the settings files.
#: `project_llm_links` is the same table under the name an old migration gave it.
_RETIRED_LLM_TABLES = (
    "llm_project_links",
    "project_llm_links",
    "llm_cost_overrides",
    "llm_profiles",
)


def _drop_retired_llm_tables(conn: sqlite3.Connection) -> None:
    """Drop the old LLM settings tables from an existing database. Idempotent."""
    for table in _RETIRED_LLM_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table}")


def _allow_unknown_cost(conn: sqlite3.Connection) -> None:
    """Rebuild `llm_usage_log` if its cost column still refuses NULL. Keeps every row. Idempotent.

    A call to a model without a known price records its cost as unknown. Tables made before that
    declared the column NOT NULL, and SQLite cannot change a column, so the table is rebuilt.
    """
    columns = conn.execute("PRAGMA table_info(llm_usage_log)").fetchall()
    if not any(col[1] == "estimated_cost" and col[3] == 1 for col in columns):
        return
    names = ", ".join(col[1] for col in columns)
    old = "_llm_usage_log_before_unknown_cost"
    conn.execute(f"ALTER TABLE llm_usage_log RENAME TO {old}")
    for index in conn.execute(f"PRAGMA index_list({old})").fetchall():
        if not index[1].startswith("sqlite_autoindex"):
            conn.execute(f"DROP INDEX {index[1]}")
    _create_table(conn, LlmBase.metadata.tables["llm_usage_log"])
    conn.execute(f"INSERT INTO llm_usage_log ({names}) SELECT {names} FROM {old}")
    conn.execute(f"DROP TABLE {old}")


#: The history columns of `llm_usage_log`.
_HISTORY_COLUMNS = ("server", "dal_level", "step_name")


def _add_history_columns(conn: sqlite3.Connection) -> None:
    """Add the history columns to an older `llm_usage_log`. Keeps every row. Idempotent."""
    present = {col[1] for col in conn.execute("PRAGMA table_info(llm_usage_log)")}
    missing = [name for name in _HISTORY_COLUMNS if name not in present]
    if not missing:
        return
    for name in missing:
        conn.execute(f"ALTER TABLE llm_usage_log ADD COLUMN {name} VARCHAR")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_llm_usage_history "
        "ON llm_usage_log (task_type, model, dal_level)"
    )


def _add_call_status(conn: sqlite3.Connection) -> None:
    """Add `call_status` to an older `llm_usage_log`; its rows were all finished calls. Idempotent."""
    present = {col[1] for col in conn.execute("PRAGMA table_info(llm_usage_log)")}
    if "call_status" not in present:
        conn.execute(
            "ALTER TABLE llm_usage_log ADD COLUMN call_status VARCHAR NOT NULL DEFAULT 'ok'"
        )


#: The cached-token columns of `llm_usage_log`; NULL is unknown on every older row.
_CACHED_COLUMNS = (
    ("cached_read_tokens", "INTEGER"),
    ("cache_write_tokens", "INTEGER"),
    ("local", "BOOLEAN"),
)


def _add_cached_columns(conn: sqlite3.Connection) -> None:
    """Add the cached-token columns to an older `llm_usage_log`. Keeps every row. Idempotent."""
    present = {col[1] for col in conn.execute("PRAGMA table_info(llm_usage_log)")}
    for name, kind in _CACHED_COLUMNS:
        if name not in present:
            conn.execute(f"ALTER TABLE llm_usage_log ADD COLUMN {name} {kind}")


def _add_refresh_reached(conn: sqlite3.Connection) -> None:
    """Add `reached_at` to an older `llm_price_refresh`: unknown until models.dev next answers.
    Idempotent."""
    present = {col[1] for col in conn.execute("PRAGMA table_info(llm_price_refresh)")}
    if "reached_at" not in present:
        conn.execute("ALTER TABLE llm_price_refresh ADD COLUMN reached_at VARCHAR")


def _add_console_log_level(conn: sqlite3.Connection) -> None:
    """Add `console_log_level` to an older `workspace_projects`; every project shows warnings. Idempotent."""
    present = {col[1] for col in conn.execute("PRAGMA table_info(workspace_projects)")}
    if "console_log_level" not in present:
        conn.execute(
            "ALTER TABLE workspace_projects ADD COLUMN console_log_level VARCHAR NOT NULL "
            "DEFAULT 'WARNING'"
        )


def _move_default_dal_once(conn: sqlite3.Connection) -> None:
    """Move projects from the old default DAL_A to DAL_C, once per database.

    No command sets a project's DAL, so every DAL_A at this point is the old default, not a choice.
    A marker keeps a later start from undoing a DAL_A set on purpose.
    """
    conn.execute("CREATE TABLE IF NOT EXISTS specweaver_migrations (name TEXT PRIMARY KEY)")
    done = conn.execute(
        "SELECT 1 FROM specweaver_migrations WHERE name = 'default_dal_c'"
    ).fetchone()
    if done:
        return
    conn.execute("UPDATE workspace_projects SET default_dal = 'DAL_C' WHERE default_dal = 'DAL_A'")
    conn.execute("INSERT OR IGNORE INTO specweaver_migrations (name) VALUES ('default_dal_c')")


def _add_price_index(conn: sqlite3.Connection) -> None:
    """One price per offering, kind, rule and start date, held by the database itself, so two
    commands storing the same download at once cannot both succeed. Idempotent."""
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_llm_price_once ON llm_price "
        "(offering_id, token_kind, IFNULL(rule_id, 0), valid_from)"
    )


_DIALECT = sqlite_dialect.dialect()

#: Table names a file made before 2026-07-12 carries; nothing can bring such a file forward.
_PRE_PREFIX_TABLES = ("projects", "active_state", "project_standards", "artifact_events")


def _create_table(conn: sqlite3.Connection, table: Table) -> None:
    """The table and its indexes as SQLAlchemy would create them, run on this connection.

    Compiled to text because `metadata.create_all` commits its own transaction, which would end the
    schema step's transaction early.
    """
    conn.execute(str(CreateTable(table).compile(dialect=_DIALECT)))
    for index in sorted(table.indexes, key=lambda ix: str(ix.name)):
        conn.execute(str(CreateIndex(index).compile(dialect=_DIALECT)))


def _create_tables(conn: sqlite3.Connection, metadata: MetaData) -> None:
    """Each missing table with its indexes; an existing table is left to the helpers below, as
    `create_all` leaves it, since its indexes may name columns a helper adds later."""
    existing = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table in metadata.sorted_tables:
        if table.name not in existing:
            _create_table(conn, table)


def _drop_alembic_version(conn: sqlite3.Connection) -> None:
    """A file Alembic once touched says Alembic manages it; nothing does."""
    conn.execute("DROP TABLE IF EXISTS alembic_version")


def _create_config(conn: sqlite3.Connection) -> None:
    """Step 1: today's schema, created where missing, and every change an older file still needs."""
    for metadata in (WorkspaceBase.metadata, LlmBase.metadata, FlowBase.metadata):
        _create_tables(conn, metadata)
    _allow_unknown_cost(conn)
    _add_history_columns(conn)
    _add_call_status(conn)
    _add_cached_columns(conn)
    _add_refresh_reached(conn)
    _add_console_log_level(conn)
    _move_default_dal_once(conn)
    _drop_retired_llm_tables(conn)
    _add_price_index(conn)
    _drop_alembic_version(conn)


def _refuse_pre_prefix_file(conn: sqlite3.Connection) -> None:
    """Stop before step 1 creates anything, so the file is left as it was."""
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    old = sorted(tables.intersection(_PRE_PREFIX_TABLES))
    if old:
        raise ValueError(
            f"the file was made before 2026-07-12 (it has the table {old[0]!r}), and this "
            f"SpecWeaver cannot bring it forward; move it aside to start a new one"
        )


#: The file's schema, one step per version; never edit a step that has shipped.
_STEPS = (Step(1, "create the configuration tables", _create_config),)


def _seed_prices(db_path: str) -> None:
    """Store the shipped list's prices. A list that cannot be read changes nothing, and warns."""
    engine = Database(db_path).sync_engine()
    try:
        with engine.begin() as conn:
            seed_prices(conn, shipped_catalogue())
    except (SettingsFileError, SQLAlchemyError) as exc:
        logger.warning("Shipped prices not stored, the stored ones stay: %s", exc)
    finally:
        engine.dispose()


def bootstrap_database(db_path: str) -> None:
    """Bring `specweaver.db` to the current schema, then store the shipped prices."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    upgrade(db_path, _STEPS, adopt=_refuse_pre_prefix_file)
    _seed_prices(db_path)


def get_db() -> Database:
    """The global SpecWeaver database, brought up to date (created if missing).

    Raises:
        SchemaError: the file cannot be opened or a step failed; the message names the file.
    """
    db_path = config_db_path()
    bootstrap_database(str(db_path))
    return Database(db_path)
