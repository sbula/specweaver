# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""E2E tests for telemetry pipeline (stories 29-30).

Full vertical slice: settings file → RoleResolver → TelemetryCollector → generate → flush → DB query.
Only the provider adapter class is faked; the settings file, the resolver and the DB are real.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from specweaver.infrastructure.llm.models import (
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
    from specweaver.core.config.database import Database

    database = Database(tmp_path / ".specweaver" / "specweaver.db")
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from tests.fixtures.db_utils import register_test_project, set_test_active_project

    db_path = str(tmp_path / ".specweaver" / "specweaver.db")
    bootstrap_database(db_path)

    register_test_project(database, "e2e-proj", str(tmp_path / "project"))
    set_test_active_project(database, "e2e-proj")
    return database


class FakeGeminiAdapter:
    """Fake that quacks like GeminiAdapter but never calls the real API."""

    provider_name = "gemini"
    api_key_env_var = "GEMINI_API_KEY"

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
        self,
        messages,
        config,
        tool_executor,
        on_tool_round=None,
    ) -> LLMResponse:
        return LLMResponse(
            text="E2E tools result",
            model=config.model,
            usage=TokenUsage(prompt_tokens=600, completion_tokens=300, total_tokens=900),
        )


_SETTINGS = """\
[servers.gem]
kind = "gemini"
private = false
max_parallel = 2

[roles]
default = "gemini-2.5-pro@gem"
"""


def _router(extra: str = ""):
    """The router a command would build, from a real machine settings file."""
    from specweaver.core.config.bootstrap.llm_settings_loader import (
        load_llm_settings,
        machine_settings_path,
    )
    from specweaver.infrastructure.llm.router import build_router

    path = machine_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_SETTINGS + extra, encoding="utf-8")
    with patch(
        "specweaver.infrastructure.llm.servers.get_adapter_class",
        return_value=FakeGeminiAdapter,
    ):
        router = build_router(
            load_llm_settings(None),
            project="e2e-proj",
            roles=["default"],
            spend_limit_usd=None,
            token_limit=None,
        )
        result = router.get_for_task(TaskType.UNKNOWN)
    return result.adapter, result.config


# ---------------------------------------------------------------------------
# Story 29: Full pipeline E2E
# ---------------------------------------------------------------------------


def _get_usage_summary_sync(db, project: str):
    from specweaver.infrastructure.llm.store import LlmRepository
    from tests.fixtures.db_utils import _sync_or_async

    async def _do():
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            return await repo.get_usage_summary(project)

    return _sync_or_async(_do())


def _get_usage_by_task_type_sync(db, project: str):
    from specweaver.infrastructure.llm.store import LlmRepository
    from tests.fixtures.db_utils import _sync_or_async

    async def _do():
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            return await repo.get_usage_by_task_type(project)

    return _sync_or_async(_do())


def _get_estimated_cost_sync(db, project: str) -> float:
    from tests.fixtures.db_utils import _sync_or_async

    async def _do():
        async with db.async_session_scope() as session:
            from sqlalchemy import text

            result = await session.execute(
                text("SELECT estimated_cost FROM llm_usage_log WHERE project_name = :p"),
                {"p": project},
            )
            row = result.fetchone()
            return row[0] if row else 0.0

    return _sync_or_async(_do())


class TestFullPipelineE2E:
    """Settings file → wrapped adapter → generate → flush → query."""

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"GEMINI_API_KEY": "e2e-key"})
    async def test_full_telemetry_pipeline(self, db):
        """Story 29: full vertical slice — settings, resolver, collector, generate, flush, query."""
        from specweaver.infrastructure.llm.collector import TelemetryCollector

        adapter, gen_config = _router()

        assert isinstance(adapter, TelemetryCollector)

        # Generate two calls
        config1 = GenerationConfig(
            model=gen_config.model,
            task_type=TaskType.DRAFT,
        )
        config2 = GenerationConfig(
            model=gen_config.model,
            task_type=TaskType.REVIEW,
        )
        await adapter.generate([], config1)
        await adapter.generate([], config2)

        # Flush to real DB
        flushed = adapter.flush(db)
        assert flushed == 2

        # Query and verify
        summary = _get_usage_summary_sync(db, "e2e-proj")
        assert len(summary) == 2  # 2 groups: draft + review
        total_calls = sum(s["call_count"] for s in summary)
        assert total_calls == 2

        by_type = _get_usage_by_task_type_sync(db, "e2e-proj")
        types = {r["task_type"] for r in by_type}
        assert types == {"draft", "review"}


# ---------------------------------------------------------------------------
# Story 30: Cost override lifecycle E2E
# ---------------------------------------------------------------------------


_PRICE = """
[models."gemini-2.5-pro"]
usd_per_million_input = 100000.0
usd_per_million_output = 200000.0
"""


class TestCostOverrideLifecycleE2E:
    """A machine-file price → resolver → generate → flush → the stored cost uses it."""

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"GEMINI_API_KEY": "e2e-key"})
    async def test_cost_override_affects_persisted_cost(self, db):
        """Story 30: the machine file's price flows through the whole pipeline to the DB."""
        # A very high price in the machine file, so it is plainly the one used
        from specweaver.infrastructure.llm.collector import TelemetryCollector

        adapter, gen_config = _router(_PRICE)

        assert isinstance(adapter, TelemetryCollector)

        # Generate — adapter returns 500 prompt + 200 completion tokens
        config = GenerationConfig(
            model=gen_config.model,
            task_type=TaskType.IMPLEMENT,
        )
        await adapter.generate([], config)

        # Flush → DB
        adapter.flush(db)

        # Verify cost: 500 * 100_000/1M + 200 * 200_000/1M = 50 + 40 = 90
        assert _get_estimated_cost_sync(db, "e2e-proj") == pytest.approx(90.0)
