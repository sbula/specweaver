from datetime import UTC, datetime

import pytest
from sqlalchemy import Column, String, Table, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from specweaver.core.config.database import create_async_engine, session_scope
from specweaver.infrastructure.llm.store import (
    Base,
    LlmProfile,
    LlmUsageLog,
    ProjectLlmLink,
)


@pytest.fixture
async def engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
async def setup_test_db(engine):
    """Create all tables for the LLM domain store."""
    # Define dummy projects table to satisfy the cross-module ForeignKey during create_all
    Table("projects", Base.metadata, Column("name", String, primary_key=True), extend_existing=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_llm_store_happy_path_crud(engine):
    async with session_scope(engine) as session:
        # Create
        profile = LlmProfile(name="test-profile")
        session.add(profile)
        await session.commit()
        await session.refresh(profile)

        assert profile.id is not None
        assert profile.model == "gemini-3-flash-preview"
        assert profile.context_limit == 128000


@pytest.mark.asyncio
async def test_llm_store_boundary_max_tokens(engine):
    async with session_scope(engine) as session:
        # 2^63 - 1 (SQLite max integer)
        max_sqlite_int = 9223372036854775807
        log = LlmUsageLog(
            timestamp=datetime(2026, 5, 2, 10, 0, 0, tzinfo=UTC),
            project_name="test-project",
            task_type="test-task",
            model="gemini",
            prompt_tokens=0,
            completion_tokens=max_sqlite_int,
            total_tokens=max_sqlite_int,
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)

        assert log.completion_tokens == max_sqlite_int


@pytest.mark.asyncio
async def test_llm_store_degradation_fk_constraint(engine):
    # Enable FKs for SQLite in tests
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys=ON"))

    with pytest.raises(IntegrityError):
        async with session_scope(engine) as session:
            link = ProjectLlmLink(
                project_name="fake-project",
                role="draft",
                profile_id=9999,  # Does not exist
            )
            session.add(link)


@pytest.mark.asyncio
async def test_llm_store_hostile_null_injection(engine):
    with pytest.raises(IntegrityError):
        async with session_scope(engine) as session:
            # None injection into NOT NULL field
            profile = LlmProfile(name=None)
            session.add(profile)
