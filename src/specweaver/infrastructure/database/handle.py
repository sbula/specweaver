# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A handle on one SpecWeaver SQLite file: plain connections, async sessions and a sync engine,
all from the one opener."""

from __future__ import annotations

import asyncio
import sqlite3
import weakref
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.pool import NullPool

from specweaver.infrastructure.database.engine import create_sqlite_engine
from specweaver.infrastructure.database.sqlite import open_sqlite

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.engine import Engine

# One semaphore per event loop, so a burst of sessions runs out of nothing before the OS runs out
# of file handles. Per loop: a semaphore binds to the first loop that waits on it, and the CLI
# starts a fresh loop for every command.
_semaphores: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = (
    weakref.WeakKeyDictionary()
)


def _semaphore(max_connections: int) -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    semaphore = _semaphores.get(loop)
    if semaphore is None:
        semaphore = asyncio.Semaphore(max_connections)
        _semaphores[loop] = semaphore
    return semaphore


@asynccontextmanager
async def session_scope(
    engine: AsyncEngine, max_connections: int = 500
) -> AsyncGenerator[AsyncSession, None]:
    """A session that commits on success and rolls back on error, at most `max_connections` open."""
    async with _semaphore(max_connections), AsyncSession(engine, expire_on_commit=False) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


class Database:
    """One SpecWeaver SQLite file."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        """A plain connection returning `sqlite3.Row` rows."""
        return open_sqlite(self._db_path, row_factory=sqlite3.Row)

    @asynccontextmanager
    async def async_session_scope(self) -> AsyncGenerator[AsyncSession, None]:
        """An async session on its own engine, disposed when the session ends."""
        engine = create_sqlite_engine(self._db_path.absolute())
        try:
            async with session_scope(engine) as session:
                yield session
        finally:
            await engine.dispose()

    def sync_engine(self) -> Engine:
        """A sync SQLAlchemy engine whose connections come from `open_sqlite`; dispose it after use."""
        return create_engine(
            "sqlite://", creator=lambda: open_sqlite(self._db_path), poolclass=NullPool
        )
