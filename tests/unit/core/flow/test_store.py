from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.pool import StaticPool

from specweaver.core.config.database import create_async_engine, session_scope
from specweaver.core.flow.store import ArtifactEvent, Base


@pytest.fixture
async def engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={'check_same_thread': False}
    )
    yield engine
    await engine.dispose()

@pytest.fixture(autouse=True)
async def setup_test_db(engine):
    """Create all tables for the Flow domain store."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_flow_store_happy_path_crud(engine):
    async with session_scope(engine) as session:
        now = datetime(2026, 5, 2, 10, 0, 0, tzinfo=UTC)
        event = ArtifactEvent(
            artifact_id="art-1",
            run_id="run-1",
            event_type="created",
            timestamp=now
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)

        assert event.id is not None
        assert event.model_id == "unknown"
        assert event.parent_id is None

@pytest.mark.asyncio
async def test_flow_store_boundary_large_ids(engine):
    async with session_scope(engine) as session:
        now = datetime(2026, 5, 2, 10, 0, 0, tzinfo=UTC)
        large_id = "x" * 1000
        event = ArtifactEvent(
            artifact_id=large_id,
            run_id=large_id,
            event_type=large_id,
            timestamp=now
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)

        assert event.artifact_id == large_id

@pytest.mark.asyncio
async def test_flow_store_degradation_missing_fields(engine):
    with pytest.raises(IntegrityError):
        async with session_scope(engine) as session:
            now = datetime(2026, 5, 2, 10, 0, 0, tzinfo=UTC)
            event = ArtifactEvent(
                run_id="run-1",
                event_type="created",
                timestamp=now
                # missing artifact_id
            )
            session.add(event)

@pytest.mark.asyncio
async def test_flow_store_hostile_type_mismatch(engine):
    with pytest.raises(StatementError):
        async with session_scope(engine) as session:
            event = ArtifactEvent(
                artifact_id="art-1",
                run_id="run-1",
                event_type="created",
                timestamp="not-a-datetime"  # Should cause StatementError in StrictISODateTime
            )
            session.add(event)
