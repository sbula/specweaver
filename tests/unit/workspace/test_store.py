from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from specweaver.core.config.database import create_async_engine, session_scope
from specweaver.workspace.store import (
    Base,
    Project,
    ProjectStandard,
)


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
    """Create all tables for the Workspace domain store."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_workspace_store_happy_path_crud(engine):
    async with session_scope(engine) as session:
        now = datetime(2026, 5, 2, 10, 0, 0, tzinfo=UTC)

        project = Project(
            name="test-project",
            root_path="/tmp/test",
            created_at=now,
            last_used_at=now
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)

        assert project.log_level == "DEBUG"
        assert project.default_dal == "DAL_A"
        assert project.stitch_mode == "off"

@pytest.mark.asyncio
async def test_workspace_store_boundary_composite_pk(engine):
    async with session_scope(engine) as session:
        now = datetime(2026, 5, 2, 10, 0, 0, tzinfo=UTC)
        project = Project(
            name="proj1", root_path="/tmp/1", created_at=now, last_used_at=now
        )
        session.add(project)

        # Valid: Differing scopes
        std1 = ProjectStandard(project_name="proj1", scope="global", language="python", category="lint", data="{}", confidence=1.0, scanned_at=now)
        std2 = ProjectStandard(project_name="proj1", scope="local", language="python", category="lint", data="{}", confidence=1.0, scanned_at=now)
        session.add_all([std1, std2])
        await session.commit()

    # Invalid: Identical 4-part PK
    with pytest.raises(IntegrityError):
        async with session_scope(engine) as session:
            std3 = ProjectStandard(project_name="proj1", scope="global", language="python", category="lint", data="other", confidence=0.5, scanned_at=now)
            session.add(std3)

@pytest.mark.asyncio
async def test_workspace_store_degradation_unique_constraint(engine):
    with pytest.raises(IntegrityError):
        async with session_scope(engine) as session:
            now = datetime(2026, 5, 2, 10, 0, 0, tzinfo=UTC)
            p1 = Project(name="p1", root_path="/shared", created_at=now, last_used_at=now)
            p2 = Project(name="p2", root_path="/shared", created_at=now, last_used_at=now)
            session.add_all([p1, p2])

@pytest.mark.asyncio
async def test_workspace_store_hostile_invalid_schema(engine):
    async with session_scope(engine) as session:
        now = datetime(2026, 5, 2, 10, 0, 0, tzinfo=UTC)
        project = Project(name="proj2", root_path="/tmp/2", created_at=now, last_used_at=now)

        massive_data = "x" * 2_000_000  # 2 MB string
        std = ProjectStandard(
            project_name="proj2", scope="global", language="cpp", category="ast",
            data=massive_data, confidence=1.0, scanned_at=now
        )
        session.add_all([project, std])
        await session.commit()
        await session.refresh(std)

        assert len(std.data) == 2_000_000
