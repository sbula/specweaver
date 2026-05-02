import sqlite3
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa

from specweaver.core.config.database import StrictISODateTime


class TestStrictISODateTime:

    def setup_method(self) -> None:
        # We instantiate a dummy dialect to test the process methods
        self.type_decorator = StrictISODateTime()
        self.dialect = sa.Dialect()

    def test_happy_path_bind_and_result(self) -> None:
        """Happy Path: Timezone-aware datetime binds to strict ISO format and reads back."""
        dt = datetime(2026, 5, 2, 12, 30, 45, 123456, tzinfo=UTC)

        # Bind
        bound_val = self.type_decorator.process_bind_param(dt, self.dialect)
        assert bound_val == "2026-05-02T12:30:45.123456+00:00"

        # Result
        result_val = self.type_decorator.process_result_value(bound_val, self.dialect)
        assert result_val == dt

    def test_happy_path_different_timezone(self) -> None:
        """Happy Path: Handles non-UTC timezones gracefully."""
        tz_plus_two = timezone(timedelta(hours=2))
        dt = datetime(2026, 5, 2, 14, 30, 45, tzinfo=tz_plus_two)

        bound_val = self.type_decorator.process_bind_param(dt, self.dialect)
        assert bound_val == "2026-05-02T14:30:45+02:00"

    def test_graceful_degradation_none_values(self) -> None:
        """Graceful Degradation: Handles None values safely for nullable columns."""
        assert self.type_decorator.process_bind_param(None, self.dialect) is None
        assert self.type_decorator.process_result_value(None, self.dialect) is None

    def test_boundary_naive_datetime_raises_error(self) -> None:
        """Boundary/Edge Case: Naive datetime objects are rejected."""
        dt = datetime(2026, 5, 2, 12, 30, 45) # No tzinfo

        with pytest.raises(ValueError, match="must be timezone-aware"):
            self.type_decorator.process_bind_param(dt, self.dialect)

    def test_hostile_input_wrong_type(self) -> None:
        """Hostile Input: Binding non-datetime objects raises TypeError."""
        with pytest.raises(TypeError, match="must be a datetime object"):
            self.type_decorator.process_bind_param("2026-05-02T12:00:00", self.dialect) # type: ignore

    def test_hostile_input_corrupted_database_string(self) -> None:
        """Hostile Input: Reading invalid strings from the DB raises ValueError."""
        with pytest.raises(ValueError):
            self.type_decorator.process_result_value("not-a-valid-date-string", self.dialect)


class TestCQRSQueueManager:
    @pytest.mark.asyncio
    async def test_happy_path_worker_processes_item(self) -> None:
        """Happy Path: Queue processes a callback exactly once."""
        from specweaver.core.config.database import CQRSQueueManager
        manager = CQRSQueueManager(maxsize=10)
        await manager.start()

        executed = False
        async def dummy_callback() -> None:
            nonlocal executed
            executed = True

        await manager.enqueue(dummy_callback)
        await manager.flush()
        await manager.stop()

        assert executed is True

    @pytest.mark.asyncio
    async def test_boundary_maxsize_enforced(self) -> None:
        """Boundary: Queue enforces maxsize."""
        from specweaver.core.config.database import CQRSQueueManager
        manager = CQRSQueueManager(maxsize=1)

        # We don't start the worker, so the queue just fills up
        async def dummy() -> None: pass

        await manager.enqueue(dummy) # Fills the queue

        # The second enqueue should raise or return False immediately if we use put_nowait
        # Let's enforce that enqueue raises asyncio.QueueFull if we use a non-blocking put for fast failing
        import asyncio
        with pytest.raises(asyncio.QueueFull):
            manager.enqueue_nowait(dummy)

    @pytest.mark.asyncio
    async def test_hostile_input_dead_letter_exchange(self, tmp_path: Path) -> None:
        """Hostile Input: Exception in callback does not kill worker, writes to DLX."""
        from specweaver.core.config.database import CQRSQueueManager

        dlx_file = tmp_path / ".dead_letter.log"
        manager = CQRSQueueManager(maxsize=10, dlx_path=dlx_file)
        await manager.start()

        async def poison_callback() -> None:
            raise sqlite3.OperationalError("Database is locked!")

        executed_next = False
        async def safe_callback() -> None:
            nonlocal executed_next
            executed_next = True

        # Enqueue poison, then a safe one
        await manager.enqueue(poison_callback)
        await manager.enqueue(safe_callback)

        await manager.flush()
        await manager.stop()

        # Worker should have survived and executed the safe one
        assert executed_next is True

        # Dead letter log should exist and contain the error
        assert dlx_file.exists()
        content = dlx_file.read_text()
        assert "Database is locked!" in content


class TestSessionScope:
    @pytest.mark.asyncio
    async def test_happy_path_yields_session(self) -> None:
        """Happy Path: session_scope yields an AsyncSession."""
        import sqlalchemy as sa
        from sqlalchemy.ext.asyncio import AsyncSession

        from specweaver.core.config.database import create_async_engine, session_scope

        # In-memory async SQLite
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        async with session_scope(engine) as session:
            assert isinstance(session, AsyncSession)
            # Simple query to prove it's connected
            result = await session.execute(sa.text("SELECT 1"))
            assert result.scalar() == 1

    @pytest.mark.asyncio
    async def test_graceful_degradation_rollback_on_exception(self) -> None:
        """Graceful Degradation: Exception inside scope rolls back transaction."""
        from specweaver.core.config.database import create_async_engine, session_scope
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        # We simulate a rollback by throwing an exception
        with pytest.raises(RuntimeError, match="Simulated crash"):
            async with session_scope(engine) as session:
                await session.execute(sa.text("CREATE TABLE test (id int)"))
                raise RuntimeError("Simulated crash")

        # Verify rollback (table shouldn't exist because the transaction rolled back)
        async with session_scope(engine) as session:
            with pytest.raises(sa.exc.OperationalError):
                await session.execute(sa.text("SELECT * FROM test"))

    @pytest.mark.asyncio
    async def test_boundary_semaphore_limits_concurrency(self) -> None:
        """Boundary: Semaphore limits concurrent connections."""
        import asyncio

        import specweaver.core.config.database as db_module
        from specweaver.core.config.database import create_async_engine, session_scope
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        # Reset the global semaphore to guarantee it initializes with max_connections=2
        db_module._db_semaphore = None

        # Test that we can't acquire more than max_connections simultaneously
        # We will mock the semaphore inside session_scope to a small number
        active_sessions = 0
        max_observed = 0

        async def worker() -> None:
            nonlocal active_sessions, max_observed
            # We override the default 500 limit to 2 for this test
            async with session_scope(engine, max_connections=2):
                active_sessions += 1
                max_observed = max(max_observed, active_sessions)
                await asyncio.sleep(0.01) # Hold the lock
                active_sessions -= 1

        # Spawn 10 concurrent workers
        tasks = [asyncio.create_task(worker()) for _ in range(10)]
        await asyncio.gather(*tasks)

        # At most 2 sessions should have been active at the same time
        assert max_observed == 2


