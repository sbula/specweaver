# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

import specweaver.workspace.memory.store  # noqa: F401
from specweaver.commons.async_bridge import run_sync
from specweaver.core.config.database import Database, session_scope
from specweaver.core.config.paths import config_db_path
from specweaver.core.flow.store import Base as FlowBase
from specweaver.infrastructure.llm.store import Base as LlmBase
from specweaver.infrastructure.llm.store import LlmProfile
from specweaver.workspace.store import Base as WorkspaceBase

logger = logging.getLogger(__name__)


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

        # Seed default LLM profiles if empty
        async with session_scope(engine) as session:
            result = await session.execute(select(LlmProfile).limit(1))
            if result.first() is None:
                defaults = [
                    LlmProfile(
                        name="system-default",
                        is_global=1,
                        provider="gemini",
                        model="gemini-2.5-pro",
                        temperature=0.7,
                        max_output_tokens=8192,
                        response_format="text",
                    ),
                    LlmProfile(
                        name="implement",
                        is_global=1,
                        provider="gemini",
                        model="gemini-2.5-flash",
                        temperature=0.2,
                        max_output_tokens=8192,
                        response_format="text",
                    ),
                    LlmProfile(
                        name="review",
                        is_global=1,
                        provider="gemini",
                        model="gemini-2.5-flash",
                        temperature=0.0,
                        max_output_tokens=8192,
                        response_format="text",
                    ),
                ]
                session.add_all(defaults)

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
