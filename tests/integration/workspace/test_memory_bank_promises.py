# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The Memory Bank's promises that no other test checked: the default timeout, the size limit
through the repository, and the log lines an operator reads.

Proves: B-INTL-09 NFR-4, NFR-6, NFR-8

A real SQLite database with foreign keys on, driven through `MemoryRepository`.

| Bucket | Case |
|---|---|
| Happy | a blocked child logs its upstream propagation; a heartbeat logs its pulse |
| Boundary | with no timeout given, 14 minutes of silence is alive and 16 is a zombie |
| Degradation | a lost race logs a warning before it raises |
| Hostile | a note over 8 KB never reaches the database |
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from specweaver.core.config.database import register_fk_pragma_listener
from specweaver.workspace.memory.errors import StaleTaskVersionError
from specweaver.workspace.memory.models import HandoverContext
from specweaver.workspace.memory.repository import MemoryRepository
from specweaver.workspace.memory.store import Task, TaskStatus
from specweaver.workspace.store import Base, Project

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, poolclass=StaticPool)
    register_fk_pragma_listener(eng.sync_engine)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        now = datetime.now(UTC)
        session.add(Project(name="p", root_path="/tmp/p", created_at=now, last_used_at=now))
        await session.flush()
        yield session


async def _running(session: AsyncSession, silent_for: timedelta) -> uuid.UUID:
    repo = MemoryRepository(session)
    task = await repo.create_task(project_name="p", title="T")
    task_id = uuid.UUID(str(task["id"]))
    await repo.acquire_task(task_id, worker_id="agent-1")
    row = await session.get(Task, task_id)
    row.last_heartbeat_at = datetime.now(UTC) - silent_for
    await session.flush()
    return task_id


@pytest.mark.asyncio
@pytest.mark.parametrize(("silent", "reaped"), [(14, 0), (16, 1)])
async def test_the_default_timeout_is_15_minutes(
    session: AsyncSession, silent: int, reaped: int
) -> None:
    await _running(session, timedelta(minutes=silent))

    recycled = await MemoryRepository(session).recycle_zombies(project_name="p")

    assert len(recycled) == reaped


@pytest.mark.asyncio
async def test_a_note_over_8_kb_never_reaches_the_database(session: AsyncSession) -> None:
    repo = MemoryRepository(session)
    task = await repo.create_task(project_name="p", title="T")
    task_id = uuid.UUID(str(task["id"]))
    big = HandoverContext(files_touched=[f"src/file_{i:05d}.py" for i in range(600)])

    with pytest.raises(ValueError, match="8192 byte limit"):
        await repo.update_handover_context(task_id, big)

    assert (await session.get(Task, task_id)).handover_context is None


@pytest.mark.asyncio
async def test_a_blocked_child_logs_its_upstream_propagation(
    session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    repo = MemoryRepository(session)
    parent = uuid.UUID(str((await repo.create_task(project_name="p", title="A"))["id"]))
    child = uuid.UUID(str((await repo.create_task(project_name="p", title="B"))["id"]))
    await repo.insert_dependency(parent, child)
    await repo.transition_state(task_id=child, to_status=TaskStatus.BLOCKED, reason="error")

    with caplog.at_level(logging.INFO, logger="specweaver.workspace.memory"):
        await repo.propagate_blocked(task_id=child)

    assert any(
        r.levelno == logging.INFO and "Upstream propagation" in r.getMessage()
        for r in caplog.records
    )


@pytest.mark.asyncio
async def test_a_heartbeat_logs_its_pulse(
    session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    task_id = await _running(session, timedelta(seconds=0))

    with caplog.at_level(logging.DEBUG, logger="specweaver.workspace.memory"):
        await MemoryRepository(session).pulse_heartbeat(task_id, worker_id="agent-1")

    assert any(
        r.levelno == logging.DEBUG and "Heartbeat pulse" in r.getMessage() for r in caplog.records
    )


@pytest.mark.asyncio
async def test_a_lost_race_logs_a_warning_before_it_raises(
    engine, session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    task = await MemoryRepository(session).create_task(project_name="p", title="Contested")
    task_id = uuid.UUID(str(task["id"]))
    await session.commit()

    async def _claim(worker: str):
        async with AsyncSession(engine, expire_on_commit=False) as other:
            return await MemoryRepository(other).acquire_task(task_id, worker)

    with caplog.at_level(logging.WARNING, logger="specweaver.workspace.memory"):
        results = await asyncio.gather(_claim("a"), _claim("b"), return_exceptions=True)

    assert sum(isinstance(r, StaleTaskVersionError) for r in results) == 1
    assert any(
        r.levelno == logging.WARNING and "OCC collision" in r.getMessage() for r in caplog.records
    )
