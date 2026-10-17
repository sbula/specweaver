# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The Memory Bank's hot queries use an index, never a full table scan.

Proves: B-INTL-09 NFR-9

The SQL each repository call sends is captured and handed to SQLite's `EXPLAIN QUERY PLAN`. The plan
shows whether an index is used without 50,000 rows: a `SCAN` of a Memory Bank table, or an automatic
index built from one on every query, is the full scan the requirement forbids. A recursive query's own working set (`SCAN ancestors`) is not a table.

| Bucket | Case |
|---|---|
| Happy | the dependency walk, task claiming and the zombie scan each search by an index |
| Boundary | a recursive query's scan of its own working set is allowed |
| Degradation | not applicable — the plan is computed, not run |
| Hostile | a planted query that filters on an unindexed column is caught, so the check can fail |
"""

import re
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from specweaver.core.config.database import register_fk_pragma_listener
from specweaver.workspace.memory.repository import MemoryRepository
from specweaver.workspace.store import Base, Project

pytestmark = pytest.mark.integration

_TABLES = ("memory_tasks", "memory_task_dependencies", "memory_state_transitions")


@pytest_asyncio.fixture
async def engine(tmp_path):
    eng = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'memory.db'}")
    register_fk_pragma_listener(eng.sync_engine)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


class _Captured:
    def __init__(self, engine) -> None:
        self.statements: list[tuple[str, object]] = []
        event.listen(engine.sync_engine, "before_cursor_execute", self._keep)

    def _keep(self, _conn, _cursor, statement, parameters, _context, _many) -> None:
        if statement.lstrip().upper().startswith(("SELECT", "WITH", "UPDATE")):
            self.statements.append((statement, parameters))


def _names(statement: str) -> set[str]:
    """Each Memory Bank table in `statement`, under its own name and every alias it is given."""
    names = set()
    for table in _TABLES:
        if table in statement:
            names.add(table)
            names |= set(re.findall(rf"\b{table}\s+(?:AS\s+)?(\w+)", statement, re.IGNORECASE))
    return names - {"ON", "WHERE", "JOIN", "SET", "AS"}


async def _table_scans(engine, statements) -> list[str]:
    scans = []
    async with engine.connect() as conn:
        for statement, parameters in statements:
            plan = await conn.exec_driver_sql("EXPLAIN QUERY PLAN " + statement, parameters)
            names = _names(statement)
            for row in plan.fetchall():
                step = row[-1].split()
                # An automatic index is built by reading the whole table, on every query.
                full = step[0] == "SCAN" or "AUTOMATIC" in step
                if full and len(step) > 1 and step[1] in names:
                    scans.append(row[-1])
    return scans


@pytest.mark.asyncio
async def test_the_hot_queries_search_by_an_index(engine) -> None:
    captured = _Captured(engine)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        now = datetime.now(UTC)
        session.add(Project(name="p", root_path="/tmp/p", created_at=now, last_used_at=now))
        await session.flush()
        repo = MemoryRepository(session)
        parent = uuid.UUID(str((await repo.create_task(project_name="p", title="A"))["id"]))
        child = uuid.UUID(str((await repo.create_task(project_name="p", title="B"))["id"]))
        captured.statements.clear()

        await repo.insert_dependency(parent, child)
        await repo.acquire_task(child, "worker")
        await repo.recycle_zombies(project_name="p")
        await session.commit()

    assert captured.statements
    assert await _table_scans(engine, captured.statements) == []


@pytest.mark.asyncio
async def test_a_query_on_an_unindexed_column_is_caught(engine) -> None:
    planted = [("SELECT id FROM memory_tasks WHERE title = ?", ("x",))]

    assert await _table_scans(engine, planted) != []
