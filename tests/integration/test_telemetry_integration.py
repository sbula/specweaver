# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests for telemetry pipeline (stories 22-28).

These tests verify cross-module contracts: TelemetryCollector ↔ Database,
Factory ↔ TelemetryCollector, and Config helpers ↔ TelemetryCollector.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from specweaver.core.config.llm_settings import ModelFacts
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext
from specweaver.infrastructure.llm.collector import TelemetryCollector
from specweaver.infrastructure.llm.models import (
    GenerationConfig,
    LLMResponse,
    TaskType,
    TokenUsage,
)
from specweaver.infrastructure.llm.store import LlmRepository
from tests.scripted_llm import FixedRouter

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


class FakeAdapter:
    """Minimal adapter for integration tests."""

    provider_name = "fake"

    def __init__(self, response: LLMResponse | None = None) -> None:
        self._response = response or LLMResponse(
            text="hello",
            model="fake-model",
            usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        )

    def available(self) -> bool:
        return True

    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    async def count_tokens(self, text: str, model: str) -> int:
        return len(text) // 4

    async def generate(self, messages, config) -> LLMResponse:
        return self._response

    async def generate_with_tools(
        self,
        messages,
        config,
        tool_executor,
        on_tool_round=None,
    ) -> LLMResponse:
        return self._response


def _make_context(*, with_config: bool = True) -> RunContext:
    """Build a RunContext with proper required fields."""
    if with_config:
        config = MagicMock()
        config.llm.model = "fake-model"
        config.llm.max_output_tokens = 4096
    else:
        config = None
    return RunContext(
        model=ModelAccess(config=config, llm_router=FixedRouter(MagicMock())),
        project_path=Path("/tmp/fake"),
        spec_path=Path("/tmp/fake/spec.md"),
    )


@pytest.fixture()
def db(tmp_path: Path):
    """Fresh database with schema v9."""
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database

    bootstrap_database(str(tmp_path / ".specweaver" / "specweaver.db"))
    return Database(tmp_path / ".specweaver" / "specweaver.db")


# ---------------------------------------------------------------------------
# Stories 22-24: Collector → ledger → read-back
# ---------------------------------------------------------------------------


class TestCollectorToDatabase:
    """The collector writes real ledger rows, queryable through the repository."""

    @pytest.mark.asyncio
    async def test_a_call_writes_a_real_ledger_row(self, db):
        """Story 22: a call becomes one llm_usage_log row."""
        collector = TelemetryCollector(FakeAdapter(), project="proj", ledger=db)
        config = GenerationConfig(
            model="fake-model", task_type=TaskType.DRAFT, max_output_tokens=1000
        )
        await collector.generate([], config)

        with db.connect() as conn:
            rows = conn.execute("SELECT * FROM llm_usage_log").fetchall()
        assert len(rows) == 1
        assert rows[0]["model"] == "fake-model"
        assert rows[0]["project_name"] == "proj"
        assert rows[0]["task_type"] == "draft"

    @pytest.mark.asyncio
    async def test_ledger_rows_are_summed_by_get_usage_summary(self, db):
        """Story 23: ledger rows → get_usage_summary returns data."""
        collector = TelemetryCollector(FakeAdapter(), project="proj", ledger=db)
        await collector.generate(
            [], GenerationConfig(model="m", task_type=TaskType.DRAFT, max_output_tokens=1000)
        )
        await collector.generate(
            [], GenerationConfig(model="m", task_type=TaskType.DRAFT, max_output_tokens=1000)
        )

        async with db.async_session_scope() as session:
            summary = await LlmRepository(session).get_usage_summary(project="proj")
        assert len(summary) == 1
        assert summary[0]["call_count"] == 2
        assert summary[0]["total_tokens"] == 300  # 150 * 2

    @pytest.mark.asyncio
    async def test_ledger_rows_group_by_task_type(self, db):
        """Story 24: ledger rows → get_usage_by_task_type groups correctly."""
        collector = TelemetryCollector(FakeAdapter(), project="proj", ledger=db)
        await collector.generate(
            [], GenerationConfig(model="m", task_type=TaskType.DRAFT, max_output_tokens=1000)
        )
        await collector.generate(
            [], GenerationConfig(model="m", task_type=TaskType.REVIEW, max_output_tokens=1000)
        )
        await collector.generate(
            [], GenerationConfig(model="m", task_type=TaskType.IMPLEMENT, max_output_tokens=1000)
        )

        async with db.async_session_scope() as session:
            result = await LlmRepository(session).get_usage_by_task_type("proj")
        assert len(result) == 3
        types = {r["task_type"] for r in result}
        assert types == {"draft", "review", "implement"}


# ---------------------------------------------------------------------------
# Story 25: DB cost overrides → collector via factory
# ---------------------------------------------------------------------------


class TestUnknownPriceFlow:
    """A call without a known price reaches the database as unknown and is counted as such.

    Proves: C-FLOW-13 FR-12
    """

    @pytest.mark.asyncio
    async def test_an_unpriced_call_is_stored_and_summed_as_unknown(self, db):
        priced = ModelFacts(usd_per_million_input=1000.0, usd_per_million_output=1000.0)
        collector = TelemetryCollector(
            FakeAdapter(), project="proj", prices={"priced-model": priced}.get, ledger=db
        )
        for model in ("priced-model", "fake-model"):
            await collector.generate(
                [], GenerationConfig(model=model, task_type=TaskType.DRAFT, max_output_tokens=1000)
            )

        async with db.async_session_scope() as session:
            rows = await LlmRepository(session).get_usage_summary(project="proj")
        # The fake server answers "fake-model" to both, so both rows share that name: the known
        # cost is summed, the unpriced call is counted — never folded in as 0.
        [row] = rows
        assert row["total_cost"] == pytest.approx((100 + 50) * 1000.0 / 1_000_000)
        assert row["unpriced_calls"] == 1


# ---------------------------------------------------------------------------
# Stories 26-27: task_type from config helpers → collector capture
# ---------------------------------------------------------------------------


class TestTaskTypeFlowThrough:
    """task_type from config helpers survives through collector capture."""

    @pytest.mark.asyncio
    async def test_review_task_type_survives_capture(self, db):
        """Story 26: task_type=REVIEW from config helper → collector record."""
        config = GenerationConfig(
            model="fake-model", task_type=TaskType.REVIEW, max_output_tokens=1000
        )
        collector = TelemetryCollector(FakeAdapter(), project="proj", ledger=db)
        await collector.generate([], config)

        with db.connect() as conn:
            assert conn.execute("SELECT task_type FROM llm_usage_log").fetchone()[0] == "review"

    @pytest.mark.asyncio
    async def test_implement_task_type_survives_capture(self, db):
        """Story 27: task_type=IMPLEMENT from config helper → collector record."""
        config = GenerationConfig(
            model="fake-model", task_type=TaskType.IMPLEMENT, max_output_tokens=1000
        )
        collector = TelemetryCollector(FakeAdapter(), project="proj", ledger=db)
        await collector.generate([], config)

        with db.connect() as conn:
            assert conn.execute("SELECT task_type FROM llm_usage_log").fetchone()[0] == "implement"


# ---------------------------------------------------------------------------
# Story 28: Multi-project isolation
# ---------------------------------------------------------------------------


class TestMultiProjectIsolation:
    """Two collectors for different projects, same DB — data isolated."""

    @pytest.mark.asyncio
    async def test_two_projects_isolated(self, db):
        """Story 28: two collectors write to one ledger; queries isolate by project."""
        adapter = FakeAdapter()
        c1 = TelemetryCollector(adapter, project="alpha", ledger=db)
        c2 = TelemetryCollector(adapter, project="beta", ledger=db)

        await c1.generate(
            [], GenerationConfig(model="m", task_type=TaskType.DRAFT, max_output_tokens=1000)
        )
        await c1.generate(
            [], GenerationConfig(model="m", task_type=TaskType.DRAFT, max_output_tokens=1000)
        )
        await c2.generate(
            [], GenerationConfig(model="m", task_type=TaskType.REVIEW, max_output_tokens=1000)
        )

        async with db.async_session_scope() as session:
            alpha = await LlmRepository(session).get_usage_summary(project="alpha")
            beta = await LlmRepository(session).get_usage_summary(project="beta")

        assert alpha[0]["call_count"] == 2
        assert beta[0]["call_count"] == 1
        assert alpha[0]["task_type"] == "draft"
        assert beta[0]["task_type"] == "review"
