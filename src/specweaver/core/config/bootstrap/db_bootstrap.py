# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import logging

from sqlalchemy import Connection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

import specweaver.workspace.memory.store  # noqa: F401
from specweaver.commons.async_bridge import run_sync
from specweaver.core.config.database import Database
from specweaver.core.config.llm_settings import SettingsFileError
from specweaver.core.config.paths import config_db_path
from specweaver.core.flow.store import Base as FlowBase
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


def _drop_retired_llm_tables(conn: Connection) -> None:
    """Drop the old LLM settings tables from an existing database. Idempotent."""
    for table in _RETIRED_LLM_TABLES:
        conn.exec_driver_sql(f"DROP TABLE IF EXISTS {table}")


def _allow_unknown_cost(conn: Connection) -> None:
    """Rebuild `llm_usage_log` if its cost column still refuses NULL. Keeps every row. Idempotent.

    A call to a model without a known price records its cost as unknown. Tables made before that
    declared the column NOT NULL, and SQLite cannot change a column, so the table is rebuilt. Alembic
    does not run at start-up, so this is where an existing database is brought up to date.
    """
    columns = conn.exec_driver_sql("PRAGMA table_info(llm_usage_log)").fetchall()
    if not any(col[1] == "estimated_cost" and col[3] == 1 for col in columns):
        return
    names = ", ".join(col[1] for col in columns)
    old = "_llm_usage_log_before_unknown_cost"
    conn.exec_driver_sql(f"ALTER TABLE llm_usage_log RENAME TO {old}")
    for index in conn.exec_driver_sql(f"PRAGMA index_list({old})").fetchall():
        if not index[1].startswith("sqlite_autoindex"):
            conn.exec_driver_sql(f"DROP INDEX {index[1]}")
    LlmBase.metadata.tables["llm_usage_log"].create(conn)
    conn.exec_driver_sql(f"INSERT INTO llm_usage_log ({names}) SELECT {names} FROM {old}")
    conn.exec_driver_sql(f"DROP TABLE {old}")


#: The history columns of `llm_usage_log`.
_HISTORY_COLUMNS = ("server", "dal_level", "step_name")


def _add_history_columns(conn: Connection) -> None:
    """Add the history columns to an older `llm_usage_log`. Keeps every row. Idempotent."""
    present = {col[1] for col in conn.exec_driver_sql("PRAGMA table_info(llm_usage_log)")}
    missing = [name for name in _HISTORY_COLUMNS if name not in present]
    if not missing:
        return
    for name in missing:
        conn.exec_driver_sql(f"ALTER TABLE llm_usage_log ADD COLUMN {name} VARCHAR")
    conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_llm_usage_history "
        "ON llm_usage_log (task_type, model, dal_level)"
    )


def _add_call_status(conn: Connection) -> None:
    """Add `call_status` to an older `llm_usage_log`; its rows were all finished calls. Idempotent."""
    present = {col[1] for col in conn.exec_driver_sql("PRAGMA table_info(llm_usage_log)")}
    if "call_status" not in present:
        conn.exec_driver_sql(
            "ALTER TABLE llm_usage_log ADD COLUMN call_status VARCHAR NOT NULL DEFAULT 'ok'"
        )


#: The cached-token columns of `llm_usage_log`; NULL is unknown on every older row.
_CACHED_COLUMNS = (
    ("cached_read_tokens", "INTEGER"),
    ("cache_write_tokens", "INTEGER"),
    ("local", "BOOLEAN"),
)


def _add_cached_columns(conn: Connection) -> None:
    """Add the cached-token columns to an older `llm_usage_log`. Keeps every row. Idempotent."""
    present = {col[1] for col in conn.exec_driver_sql("PRAGMA table_info(llm_usage_log)")}
    for name, kind in _CACHED_COLUMNS:
        if name not in present:
            conn.exec_driver_sql(f"ALTER TABLE llm_usage_log ADD COLUMN {name} {kind}")


def _add_console_log_level(conn: Connection) -> None:
    """Add `console_log_level` to an older `workspace_projects`; every project shows warnings. Idempotent."""
    present = {col[1] for col in conn.exec_driver_sql("PRAGMA table_info(workspace_projects)")}
    if "console_log_level" not in present:
        conn.exec_driver_sql(
            "ALTER TABLE workspace_projects ADD COLUMN console_log_level VARCHAR NOT NULL "
            "DEFAULT 'WARNING'"
        )


def _move_default_dal_once(conn: Connection) -> None:
    """Move projects from the old default DAL_A to DAL_C, once per database.

    No command sets a project's DAL, so every DAL_A at this point is the old default, not a choice.
    A marker keeps a later start from undoing a DAL_A set on purpose.
    """
    conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS specweaver_migrations (name TEXT PRIMARY KEY)")
    done = conn.exec_driver_sql(
        "SELECT 1 FROM specweaver_migrations WHERE name = 'default_dal_c'"
    ).fetchone()
    if done:
        return
    conn.exec_driver_sql(
        "UPDATE workspace_projects SET default_dal = 'DAL_C' WHERE default_dal = 'DAL_A'"
    )
    conn.exec_driver_sql(
        "INSERT OR IGNORE INTO specweaver_migrations (name) VALUES ('default_dal_c')"
    )


def _seed_prices(conn: Connection) -> None:
    """Store the shipped list's prices. A list that cannot be read changes nothing, and warns."""
    try:
        with conn.begin_nested():
            seed_prices(conn, shipped_catalogue())
    except (SettingsFileError, SQLAlchemyError) as exc:
        logger.warning("Shipped prices not stored, the stored ones stay: %s", exc)


def bootstrap_database(db_path: str) -> None:
    """Create tables and apply defaults natively. Idempotent."""
    import pathlib

    pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async def _create_all() -> None:
        db_posix = pathlib.Path(db_path).absolute().as_posix()
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_posix}")
        async with engine.begin() as conn:
            # `logger.debug`, never `print`: a bootstrap that writes its schema to stdout puts it
            # ahead of the first event of `sw run --json`, whose output is a machine-readable NDJSON
            # stream.
            logger.debug("LlmBase tables: %s", LlmBase.metadata.tables.keys())
            logger.debug("WorkspaceBase tables: %s", WorkspaceBase.metadata.tables.keys())
            logger.debug("FlowBase tables: %s", FlowBase.metadata.tables.keys())
            await conn.run_sync(WorkspaceBase.metadata.create_all)
            await conn.run_sync(LlmBase.metadata.create_all)
            await conn.run_sync(FlowBase.metadata.create_all)
            await conn.run_sync(_allow_unknown_cost)
            await conn.run_sync(_add_history_columns)
            await conn.run_sync(_add_call_status)
            await conn.run_sync(_add_cached_columns)
            await conn.run_sync(_add_console_log_level)
            await conn.run_sync(_move_default_dal_once)
            await conn.run_sync(_drop_retired_llm_tables)
            await conn.run_sync(_seed_prices)

        await engine.dispose()

    # Never re-enters a running loop — see `commons.async_bridge`. Called from async tests and
    # from `get_db()`, so both paths matter.
    run_sync(_create_all)


def get_db() -> Database:
    """Get the global SpecWeaver database (creates if needed)."""
    db_path = config_db_path()
    try:
        bootstrap_database(str(db_path))
    except Exception as exc:
        logger.warning("Failed to bootstrap database at %s: %s", db_path, exc)
    return Database(db_path)
