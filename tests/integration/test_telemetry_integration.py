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

from specweaver.core.flow.handlers.base import RunContext
from specweaver.infrastructure.llm.collector import TelemetryCollector
from specweaver.infrastructure.llm.models import (
    GenerationConfig,
    LLMResponse,
    TaskType,
    TokenUsage,
)
from specweaver.infrastructure.llm.telemetry import CostEntry

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
        project_path=Path("/tmp/fake"),
        spec_path=Path("/tmp/fake/spec.md"),
        config=config,
        llm=MagicMock(),
    )


@pytest.fixture()
def db(tmp_path: Path):
    """Fresh database with schema v9."""
    from specweaver.core.config.database import Database

    return Database(tmp_path / ".specweaver" / "specweaver.db")


# ---------------------------------------------------------------------------
# Stories 22-24: Collector → flush → DB read-back
# ---------------------------------------------------------------------------


class TestCollectorToDatabase:
    """TelemetryCollector.flush writes real DB rows queryable via mixin."""

    @pytest.mark.asyncio
    async def test_flush_writes_real_db_rows(self, db):
        """Story 22: flush persists records to llm_usage_log via log_usage."""
        collector = TelemetryCollector(FakeAdapter(), project="proj")
        config = GenerationConfig(model="fake-model", task_type=TaskType.DRAFT)
        await collector.generate([], config)

        count = collector.flush(db)
        assert count == 1

        with db.connect() as conn:
            rows = conn.execute("SELECT * FROM llm_usage_log").fetchall()
        assert len(rows) == 1
        assert rows[0]["model"] == "fake-model"
        assert rows[0]["project_name"] == "proj"
        assert rows[0]["task_type"] == "draft"

    @pytest.mark.asyncio
    async def test_flush_data_queryable_via_get_usage_summary(self, db):
        """Story 23: flush → log_usage → get_usage_summary returns data."""
        collector = TelemetryCollector(FakeAdapter(), project="proj")
        await collector.generate([], GenerationConfig(model="m", task_type=TaskType.DRAFT))
        await collector.generate([], GenerationConfig(model="m", task_type=TaskType.DRAFT))
        collector.flush(db)

        summary = db.get_usage_summary(project="proj")
        assert len(summary) == 1
        assert summary[0]["call_count"] == 2
        assert summary[0]["total_tokens"] == 300  # 150 * 2

    @pytest.mark.asyncio
    async def test_flush_data_groups_by_task_type(self, db):
        """Story 24: flush → get_usage_by_task_type groups correctly."""
        collector = TelemetryCollector(FakeAdapter(), project="proj")
        await collector.generate([], GenerationConfig(model="m", task_type=TaskType.DRAFT))
        await collector.generate([], GenerationConfig(model="m", task_type=TaskType.REVIEW))
        await collector.generate([], GenerationConfig(model="m", task_type=TaskType.IMPLEMENT))
        collector.flush(db)

        result = db.get_usage_by_task_type("proj")
        assert len(result) == 3
        types = {r["task_type"] for r in result}
        assert types == {"draft", "review", "implement"}


# ---------------------------------------------------------------------------
# Story 25: DB cost overrides → collector via factory
# ---------------------------------------------------------------------------


class TestCostOverrideFlow:
    """DB cost overrides flow through to collector and affect pricing."""

    @pytest.mark.asyncio
    async def test_db_overrides_affect_collector_cost(self, db):
        """Story 25: set_cost_override → get_cost_overrides → collector uses them."""
        db.set_cost_override("fake-model", 50.0, 100.0)

        raw = db.get_cost_overrides()
        overrides = {k: CostEntry(*v) for k, v in raw.items()}

        collector = TelemetryCollector(
            FakeAdapter(),
            project="proj",
            cost_overrides=overrides,
        )
        await collector.generate(
            [],
            GenerationConfig(model="fake-model", task_type=TaskType.DRAFT),
        )

        record = collector.records[0]
        # (100/1000)*50 + (50/1000)*100 = 5.0 + 5.0 = 10.0
        assert record.estimated_cost_usd == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# Stories 26-27: task_type from config helpers → collector capture
# ---------------------------------------------------------------------------


class TestTaskTypeFlowThrough:
    """task_type from config helpers survives through collector capture."""

    @pytest.mark.asyncio
    async def test_review_task_type_survives_capture(self, db):
        """Story 26: task_type=REVIEW from config helper → collector record."""
        config = GenerationConfig(model="fake-model", task_type=TaskType.REVIEW)
        collector = TelemetryCollector(FakeAdapter(), project="proj")
        await collector.generate([], config)

        assert collector.records[0].task_type == "review"

    @pytest.mark.asyncio
    async def test_implement_task_type_survives_capture(self, db):
        """Story 27: task_type=IMPLEMENT from config helper → collector record."""
        config = GenerationConfig(model="fake-model", task_type=TaskType.IMPLEMENT)
        collector = TelemetryCollector(FakeAdapter(), project="proj")
        await collector.generate([], config)

        assert collector.records[0].task_type == "implement"


# ---------------------------------------------------------------------------
# Story 28: Multi-project isolation
# ---------------------------------------------------------------------------


class TestMultiProjectIsolation:
    """Two collectors for different projects, same DB — data isolated."""

    @pytest.mark.asyncio
    async def test_two_projects_isolated(self, db):
        """Story 28: two collectors flush to same DB, queries isolate by project."""
        adapter = FakeAdapter()
        c1 = TelemetryCollector(adapter, project="alpha")
        c2 = TelemetryCollector(adapter, project="beta")

        await c1.generate([], GenerationConfig(model="m", task_type=TaskType.DRAFT))
        await c1.generate([], GenerationConfig(model="m", task_type=TaskType.DRAFT))
        await c2.generate([], GenerationConfig(model="m", task_type=TaskType.REVIEW))

        c1.flush(db)
        c2.flush(db)

        alpha = db.get_usage_summary(project="alpha")
        beta = db.get_usage_summary(project="beta")

        assert alpha[0]["call_count"] == 2
        assert beta[0]["call_count"] == 1
        assert alpha[0]["task_type"] == "draft"
        assert beta[0]["task_type"] == "review"
