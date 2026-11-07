# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from specweaver.infrastructure.database import StrictISODateTime, session_scope
from specweaver.infrastructure.database import handle as opener
from tests.fixtures.db_utils import create_async_engine


# A minimal DeclarativeBase and model for integration testing
class Base(DeclarativeBase):
    pass


class DummyLog(Base):
    __tablename__ = "dummy_logs"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message: Mapped[str] = mapped_column(sa.String)
    created_at: Mapped[datetime] = mapped_column(StrictISODateTime)


@pytest.fixture
async def engine(tmp_path: Path) -> sa.ext.asyncio.AsyncEngine:
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


class TestDatabaseIntegration:
    @pytest.mark.asyncio
    async def test_story_3_concurrent_reads_happy_path(
        self, engine: sa.ext.asyncio.AsyncEngine
    ) -> None:
        """Integration Story 3: 500 concurrent queries don't lock database due to WAL + Semaphore."""
        # Insert a dummy record
        async with session_scope(engine) as session:
            session.add(DummyLog(message="test", created_at=datetime.now(tz=UTC)))

        async def read_worker(worker_id: int) -> int:
            async with session_scope(engine) as session:
                result = await session.execute(sa.select(sa.func.count(DummyLog.id)))
                return result.scalar() or 0

        # Fire 500 concurrent reads
        tasks = [read_worker(i) for i in range(500)]
        results = await asyncio.gather(*tasks)

        # Verify all 500 succeeded
        assert len(results) == 500
        assert all(r == 1 for r in results)

    @pytest.mark.asyncio
    async def test_story_4_file_descriptor_throttling(
        self, engine: sa.ext.asyncio.AsyncEngine
    ) -> None:
        """Integration Story 4: Semaphore throttles connections without OS failure."""
        opener._semaphores.clear()  # this test sets its own limit

        active_connections = 0
        max_connections = 0

        async def throttled_worker() -> None:
            nonlocal active_connections, max_connections
            # Use max_connections=5 to simulate tight file descriptor limits
            async with session_scope(engine, max_connections=5):
                active_connections += 1
                if active_connections > max_connections:
                    max_connections = active_connections
                await asyncio.sleep(0.01)  # Hold connection briefly
                active_connections -= 1

        # Fire 50 concurrent requests against a limit of 5
        tasks = [throttled_worker() for _ in range(50)]
        await asyncio.gather(*tasks)

        assert max_connections == 5

    @pytest.mark.asyncio
    async def test_story_6_legacy_db_string_parsing(
        self, engine: sa.ext.asyncio.AsyncEngine
    ) -> None:
        """Integration Story 6: legacy/corrupted SQLite dates throw clean errors via StrictISODateTime."""
        # Force a corrupt legacy string into the DB directly using raw SQL
        async with engine.begin() as conn:
            await conn.execute(
                sa.text(
                    "INSERT INTO dummy_logs (message, created_at) VALUES ('legacy', 'not-a-date-format')"
                )
            )

        async with session_scope(engine) as session:
            with pytest.raises(ValueError, match="Invalid isoformat string"):
                # Attempt to map it back via the ORM
                result = await session.execute(
                    sa.select(DummyLog).where(DummyLog.message == "legacy")
                )
                result.scalars().first()
