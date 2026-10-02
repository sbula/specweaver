# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import logging

from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import specweaver.workspace.memory.store  # noqa: F401
from specweaver.commons.async_bridge import run_sync
from specweaver.core.config.database import Database
from specweaver.core.config.paths import config_db_path
from specweaver.core.flow.store import Base as FlowBase
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
            await conn.run_sync(_drop_retired_llm_tables)

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
