# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Sessions commit on success, roll back on error, and are limited per event loop; product
sessions enforce foreign keys.

Proves: B-INTL-09 FR-6, NFR-7

Moved from `tests/unit/core/config/test_database.py` and `test_db_semaphore_per_loop.py` when
`TECH-090` moved `session_scope` into `infrastructure/database/`.

| Bucket | Case |
|---|---|
| Happy | a session runs a query; a product session has foreign keys on |
| Boundary | at most `max_connections` sessions are open at once; one loop reuses its semaphore |
| Degradation | an error inside the scope rolls the transaction back |
| Hostile | a second event loop gets its own semaphore instead of crashing on the first one's |
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from specweaver.infrastructure.database import Database, session_scope
from specweaver.infrastructure.database import handle as opener
from tests.fixtures.db_utils import create_async_engine

if TYPE_CHECKING:
    from pathlib import Path

_MEMORY = "sqlite+aiosqlite:///:memory:"


@pytest.mark.asyncio
async def test_a_session_runs_a_query() -> None:
    async with session_scope(create_async_engine(_MEMORY)) as session:  # type: ignore[arg-type]
        assert isinstance(session, AsyncSession)
        assert (await session.execute(sa.text("SELECT 1"))).scalar() == 1


@pytest.mark.asyncio
async def test_an_error_inside_the_scope_rolls_back(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'a.db'}")

    async with session_scope(engine) as session:  # type: ignore[arg-type]
        await session.execute(sa.text("CREATE TABLE test (id int)"))

    with pytest.raises(RuntimeError, match="Simulated crash"):
        async with session_scope(engine) as session:  # type: ignore[arg-type]
            await session.execute(sa.text("INSERT INTO test VALUES (1)"))
            raise RuntimeError("Simulated crash")

    async with session_scope(engine) as session:  # type: ignore[arg-type]
        rows = (await session.execute(sa.text("SELECT count(*) FROM test"))).scalar_one()
    assert rows == 0


@pytest.mark.asyncio
async def test_at_most_max_connections_sessions_are_open() -> None:
    engine = create_async_engine(_MEMORY)
    active = observed = 0

    async def worker() -> None:
        nonlocal active, observed
        async with session_scope(engine, max_connections=2):  # type: ignore[arg-type]
            active += 1
            observed = max(observed, active)
            await asyncio.sleep(0.01)
            active -= 1

    await asyncio.gather(*(worker() for _ in range(10)))

    assert observed == 2


@pytest.mark.asyncio
async def test_a_product_session_has_foreign_keys_on(tmp_path: Path) -> None:
    async with Database(tmp_path / "x.db").async_session_scope() as session:
        assert (await session.execute(sa.text("PRAGMA foreign_keys"))).scalar() == 1


async def _contend() -> None:
    semaphore = opener._semaphore(1)

    async def hold() -> None:
        async with semaphore:
            await asyncio.sleep(0.01)

    await asyncio.gather(hold(), hold())


def test_a_second_event_loop_can_wait_on_its_own_semaphore() -> None:
    asyncio.run(_contend())
    asyncio.run(_contend())


def test_one_loop_reuses_its_semaphore() -> None:
    async def twice() -> bool:
        return opener._semaphore(500) is opener._semaphore(500)

    assert asyncio.run(twice())
