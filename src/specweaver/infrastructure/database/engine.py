# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The async engine for a SpecWeaver SQLite file, with the same settings as `open_sqlite`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from specweaver.infrastructure.database.sqlite import apply_pragmas, lock_wait_seconds


def create_sqlite_engine(path: Path | str) -> AsyncEngine:
    """An `aiosqlite` engine whose every connection gets WAL, foreign keys and the lock wait.

    `NullPool`, so each checkout is a new connection that runs the `connect` event: a pooled
    connection must not cross event loops, which the CLI's `anyio.run` per call would make it do.
    """
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{Path(path).as_posix()}",
        poolclass=NullPool,
        connect_args={"timeout": lock_wait_seconds()},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _settings(dbapi_conn: Any, _record: Any) -> None:
        cursor = dbapi_conn.cursor()
        try:
            apply_pragmas(cursor)
        finally:
            cursor.close()

    return engine
