# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""E2E tests for telemetry pipeline (stories 29-30).

Full vertical slice: factory → TelemetryCollector → generate → flush → DB query.
Uses mock adapter but real DB and real factory logic.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from specweaver.llm.models import (
    GenerationConfig,
    LLMResponse,
    TaskType,
    TokenUsage,
)

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path):
    """Fresh database with a registered + active project."""
    from specweaver.config.database import Database

    database = Database(tmp_path / ".specweaver" / "specweaver.db")
    database.register_project("e2e-proj", str(tmp_path / "project"))
    database.set_active_project("e2e-proj")
    return database


class FakeGeminiAdapter:
    """Fake that quacks like GeminiAdapter but never calls the real API."""

    provider_name = "gemini"

    def __init__(self, **_kwargs) -> None:
        pass

    def available(self) -> bool:
        return True

    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    async def count_tokens(self, text: str, model: str) -> int:
        return len(text) // 4

    async def generate(self, messages, config) -> LLMResponse:
        return LLMResponse(
            text="E2E result",
            model=config.model,
            usage=TokenUsage(prompt_tokens=500, completion_tokens=200, total_tokens=700),
        )

    async def generate_with_tools(
        self, messages, config, tool_executor, on_tool_round=None,
    ) -> LLMResponse:
        return LLMResponse(
            text="E2E tools result",
            model=config.model,
            usage=TokenUsage(prompt_tokens=600, completion_tokens=300, total_tokens=900),
        )


# ---------------------------------------------------------------------------
# Story 29: Full pipeline E2E
# ---------------------------------------------------------------------------


class TestFullPipelineE2E:
    """Factory → wrapped adapter → generate → flush → query."""

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"GEMINI_API_KEY": "e2e-key"})
    async def test_full_telemetry_pipeline(self, db):
        """Story 29: full vertical slice — factory, collector, generate, flush, query."""
        from specweaver.llm.collector import TelemetryCollector
        from specweaver.llm.factory import create_llm_adapter

        with patch(
            "specweaver.llm.adapters.gemini.GeminiAdapter", FakeGeminiAdapter,
        ):
            _settings, adapter, gen_config = create_llm_adapter(
                db, telemetry_project="e2e-proj",
            )

        assert isinstance(adapter, TelemetryCollector)

        # Generate two calls
        config1 = GenerationConfig(
            model=gen_config.model, task_type=TaskType.DRAFT,
        )
        config2 = GenerationConfig(
            model=gen_config.model, task_type=TaskType.REVIEW,
        )
        await adapter.generate([], config1)
        await adapter.generate([], config2)

        # Flush to real DB
        flushed = adapter.flush(db)
        assert flushed == 2

        # Query and verify
        summary = db.get_usage_summary(project="e2e-proj")
        assert len(summary) == 2  # 2 groups: draft + review
        total_calls = sum(s["call_count"] for s in summary)
        assert total_calls == 2

        by_type = db.get_usage_by_task_type("e2e-proj")
        types = {r["task_type"] for r in by_type}
        assert types == {"draft", "review"}


# ---------------------------------------------------------------------------
# Story 30: Cost override lifecycle E2E
# ---------------------------------------------------------------------------


class TestCostOverrideLifecycleE2E:
    """Set override → factory loads → generate → flush → verify cost."""

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"GEMINI_API_KEY": "e2e-key"})
    async def test_cost_override_affects_persisted_cost(self, db):
        """Story 30: override pricing flows through entire pipeline to DB."""
        from specweaver.llm.collector import TelemetryCollector
        from specweaver.llm.factory import create_llm_adapter

        # Set a very high cost override so we can verify it's used
        db.set_cost_override("gemini-3-flash-preview", 100.0, 200.0)

        with patch(
            "specweaver.llm.adapters.gemini.GeminiAdapter", FakeGeminiAdapter,
        ):
            _settings, adapter, gen_config = create_llm_adapter(
                db, telemetry_project="e2e-proj",
            )

        assert isinstance(adapter, TelemetryCollector)

        # Generate — adapter returns 500 prompt + 200 completion tokens
        config = GenerationConfig(
            model=gen_config.model, task_type=TaskType.IMPLEMENT,
        )
        await adapter.generate([], config)

        # Flush → DB
        adapter.flush(db)

        # Verify cost: (500/1000)*100 + (200/1000)*200 = 50 + 40 = 90
        with db.connect() as conn:
            row = conn.execute(
                "SELECT estimated_cost FROM llm_usage_log WHERE project_name='e2e-proj'",
            ).fetchone()
        assert row["estimated_cost"] == pytest.approx(90.0)
