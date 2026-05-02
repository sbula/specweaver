import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from specweaver.core.config.database import (
    CQRSQueueManager,
    StrictISODateTime,
    create_async_engine,
    session_scope,
)


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
        import specweaver.core.config.database

        specweaver.core.config.database._db_semaphore = None  # Reset global semaphore

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
    async def test_story_5_dlx_survival_integration(
        self, engine: sa.ext.asyncio.AsyncEngine, tmp_path: Path
    ) -> None:
        """Integration Story 5: DLX traps invalid SQL and continues processing queue."""
        dlx_file = tmp_path / ".dlx.log"
        queue = CQRSQueueManager(maxsize=10, dlx_path=dlx_file)
        await queue.start()

        async def valid_write() -> None:
            async with session_scope(engine) as session:
                session.add(DummyLog(message="valid", created_at=datetime.now(tz=UTC)))

        async def poison_write() -> None:
            async with session_scope(engine) as session:
                # Force a physical SQLite syntax error to trigger operational rollback
                await session.execute(sa.text("INSERT INTO non_existent_table VALUES (1)"))

        # Enqueue: valid -> poison -> valid
        await queue.enqueue(valid_write)
        await queue.enqueue(poison_write)
        await queue.enqueue(valid_write)

        # Flush the queue
        await queue.flush()
        await queue.stop()

        # Verify DB physically contains only the 2 valid writes
        async with session_scope(engine) as session:
            result = await session.execute(sa.select(sa.func.count(DummyLog.id)))
            count = result.scalar()
            assert count == 2

        # Verify the poison pill was trapped and logged
        assert dlx_file.exists()
        log_content = dlx_file.read_text()
        assert "no such table: non_existent_table" in log_content

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

    @pytest.mark.asyncio
    async def test_story_7_max_queue_size_spikes(self, tmp_path: Path) -> None:
        """Integration Story 7: Spike of 1000 items is throttled and flushed cleanly."""
        queue = CQRSQueueManager(maxsize=100)  # Use 100 to speed up test and prove throttle

        success_count = 0

        async def fast_write() -> None:
            nonlocal success_count
            success_count += 1
            await asyncio.sleep(0.001)

        # We haven't started the worker yet, so the queue will block after 100
        for _ in range(100):
            queue.enqueue_nowait(fast_write)

        with pytest.raises(asyncio.QueueFull):
            queue.enqueue_nowait(fast_write)

        # Start the worker, let it drain, and flush
        await queue.start()
        await queue.flush()
        await queue.stop()

        assert success_count == 100
