# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The LLM telemetry store stands on its own models, constraints and session scope.

Drives the store directly rather than through a caller, so a regression that folded these tables
back into the shared config database would fail here rather than somewhere downstream.

Proves: TECH-001 FR-1.
Proves: C-FLOW-13 FR-12.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import Column, String, Table
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from specweaver.core.config.database import create_async_engine, session_scope
from specweaver.infrastructure.llm.store import Base, LlmUsageLog


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
    Table(
        "workspace_projects",
        Base.metadata,
        Column("name", String, primary_key=True),
        extend_existing=True,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def _usage(**overrides) -> LlmUsageLog:
    values = {
        "timestamp": datetime(2026, 5, 2, 10, 0, 0, tzinfo=UTC),
        "project_name": "test-project",
        "task_type": "review",
        "model": "claude-opus-5-5",
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "estimated_cost": 0.25,
    }
    return LlmUsageLog(**(values | overrides))


@pytest.mark.asyncio
async def test_llm_store_happy_path_crud(engine):
    async with session_scope(engine) as session:
        log = _usage()
        session.add(log)
        await session.commit()
        await session.refresh(log)

        assert log.id is not None
        assert (log.model, log.estimated_cost) == ("claude-opus-5-5", 0.25)


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
async def test_llm_store_degradation_unknown_cost_is_stored_as_unknown(engine):
    """A model without a known price records no cost, never 0 (C-FLOW-13 FR-12)."""
    async with session_scope(engine) as session:
        log = _usage(model="qwen3-coder-next", estimated_cost=None)
        session.add(log)
        await session.commit()
        await session.refresh(log)

        assert log.estimated_cost is None


@pytest.mark.asyncio
async def test_llm_store_hostile_null_injection(engine):
    with pytest.raises(IntegrityError):
        async with session_scope(engine) as session:
            # None injection into a NOT NULL field
            session.add(_usage(model=None))
