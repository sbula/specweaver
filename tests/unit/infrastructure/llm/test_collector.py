# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for llm/collector.py — TelemetryCollector decorator."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from specweaver.infrastructure.llm.collector import TelemetryCollector
from specweaver.infrastructure.llm.models import (
    GenerationConfig,
    LLMResponse,
    TaskType,
    TokenUsage,
)
from tests.ledger import Ledger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path


@pytest.fixture
def ledger(tmp_path: Path) -> Ledger:
    """A real ledger: the collector writes every call there itself (C-FLOW-01 FR-4)."""
    return Ledger(tmp_path)


# ---------------------------------------------------------------------------
# Fake adapter for testing
# ---------------------------------------------------------------------------


class FakeAdapter:
    """Minimal LLMAdapter-like object for testing the collector."""

    provider_name = "fake"

    def __init__(self, response: LLMResponse | None = None, stream_chunks: list[str] | None = None):
        self._response = response or LLMResponse(
            text="hello",
            model="fake-model",
            usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        )
        self._stream_chunks = stream_chunks if stream_chunks is not None else ["hello", " world"]
        self._call_count = 0

    def available(self) -> bool:
        return True

    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    async def count_tokens(self, text: str, model: str) -> int:
        return len(text) // 4

    async def generate(self, messages, config) -> LLMResponse:
        self._call_count += 1
        return self._response

    async def generate_with_tools(
        self, messages, config, tool_executor, on_tool_round=None, before_request=None
    ) -> LLMResponse:
        self._call_count += 1
        return self._response

    async def generate_stream(self, messages, config) -> AsyncIterator[str]:
        self._call_count += 1
        for chunk in self._stream_chunks:
            yield chunk


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCollectorGenerate:
    """Test telemetry capture for generate()."""

    @pytest.mark.asyncio
    async def test_captures_one_record(self, ledger):
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="test-proj", ledger=ledger.db)
        config = GenerationConfig(
            model="fake-model", task_type=TaskType.DRAFT, max_output_tokens=1000
        )

        response = await collector.generate([], config)

        assert response.text == "hello"
        assert len(ledger.rows) == 1
        record = ledger.rows[0]
        assert record.project_name == "test-proj"
        assert record.task_type == "draft"
        assert record.model == "fake-model"
        assert record.provider == "fake"
        assert record.prompt_tokens == 100
        assert record.completion_tokens == 50

    @pytest.mark.asyncio
    async def test_timing_is_positive(self, ledger):
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="test-proj", ledger=ledger.db)
        config = GenerationConfig(model="fake-model", max_output_tokens=1000)

        await collector.generate([], config)

        assert ledger.rows[0].duration_ms >= 0

    @pytest.mark.asyncio
    async def test_task_type_from_config_not_constructor(self, ledger):
        """task_type comes from config.task_type, not the collector constructor."""
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="proj", ledger=ledger.db)

        config1 = GenerationConfig(
            model="fake-model", task_type=TaskType.REVIEW, max_output_tokens=1000
        )
        config2 = GenerationConfig(
            model="fake-model", task_type=TaskType.IMPLEMENT, max_output_tokens=1000
        )

        await collector.generate([], config1)
        await collector.generate([], config2)

        assert ledger.rows[0].task_type == "review"
        assert ledger.rows[1].task_type == "implement"


class TestCollectorGenerateWithTools:
    """Test telemetry capture for generate_with_tools()."""

    @pytest.mark.asyncio
    async def test_captures_one_record(self, ledger):
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="proj", ledger=ledger.db)
        config = GenerationConfig(
            model="fake-model", task_type=TaskType.REVIEW, max_output_tokens=1000
        )

        response = await collector.generate_with_tools([], config, MagicMock())

        assert response.text == "hello"
        assert len(ledger.rows) == 1
        assert ledger.rows[0].task_type == "review"


class TestCollectorGenerateStream:
    """Test telemetry capture for generate_stream()."""

    @pytest.mark.asyncio
    async def test_captures_record_after_stream(self, ledger):
        adapter = FakeAdapter(stream_chunks=["hello", " world", "!"])
        collector = TelemetryCollector(adapter, project="proj", ledger=ledger.db)
        config = GenerationConfig(
            model="fake-model", task_type=TaskType.DRAFT, max_output_tokens=1000
        )

        chunks = []
        async for chunk in collector.generate_stream([], config):
            chunks.append(chunk)

        assert chunks == ["hello", " world", "!"]
        assert len(ledger.rows) == 1
        record = ledger.rows[0]
        assert record.task_type == "draft"
        assert record.completion_tokens > 0  # Estimated from text
        assert record.prompt_tokens == 0  # Known gap for streaming


class TestCollectorMultipleCalls:
    """Test that each call produces a separate record."""

    @pytest.mark.asyncio
    async def test_three_calls_three_records(self, ledger):
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="proj", ledger=ledger.db)

        await collector.generate(
            [], GenerationConfig(model="m", task_type=TaskType.DRAFT, max_output_tokens=1000)
        )
        await collector.generate(
            [], GenerationConfig(model="m", task_type=TaskType.REVIEW, max_output_tokens=1000)
        )
        await collector.generate(
            [], GenerationConfig(model="m", task_type=TaskType.IMPLEMENT, max_output_tokens=1000)
        )

        assert len(ledger.rows) == 3
        types = [r.task_type for r in ledger.rows]
        assert types == ["draft", "review", "implement"]


class TestCollectorDelegation:
    """Test that non-generation methods delegate correctly."""

    def test_provider_name(self, ledger):
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="proj", ledger=ledger.db)
        assert collector.provider_name == "fake"

    def test_available(self, ledger):
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="proj", ledger=ledger.db)
        assert collector.available() is True

    @pytest.mark.asyncio
    async def test_count_tokens(self, ledger):
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="proj", ledger=ledger.db)
        count = await collector.count_tokens("hello world", "model")
        assert isinstance(count, int)

    def test_estimate_tokens(self, ledger):
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="proj", ledger=ledger.db)
        est = collector.estimate_tokens("hello world test data")
        assert isinstance(est, int)
        assert est > 0


# ---------------------------------------------------------------------------
# Corner-case tests (stories 14-19)
# ---------------------------------------------------------------------------


class TestCollectorAdapterExceptions:
    """Adapter exceptions propagate without capturing telemetry."""

    @pytest.mark.asyncio
    async def test_generate_exception_propagates_and_is_recorded_failed(self, ledger):
        """adapter.generate() raises → the error goes on, and the call is `failed` with tokens
        unknown (C-FLOW-01 FR-3: a billed failure is spend)."""
        adapter = FakeAdapter()
        adapter.generate = _raise_adapter_error
        collector = TelemetryCollector(adapter, project="proj", ledger=ledger.db)
        config = GenerationConfig(model="fake-model", max_output_tokens=1000)

        with pytest.raises(RuntimeError, match="adapter exploded"):
            await collector.generate([], config)

        assert [(r.call_status, r.total_tokens, r.estimated_cost) for r in ledger.rows] == [
            ("failed", 0, None)
        ]

    @pytest.mark.asyncio
    async def test_generate_with_tools_exception_is_recorded_failed(self, ledger):
        """adapter.generate_with_tools() raises → the call is `failed`."""
        adapter = FakeAdapter()
        adapter.generate_with_tools = _raise_adapter_error_tools
        collector = TelemetryCollector(adapter, project="proj", ledger=ledger.db)
        config = GenerationConfig(model="fake-model", max_output_tokens=1000)

        with pytest.raises(RuntimeError, match="adapter exploded"):
            await collector.generate_with_tools([], config, MagicMock())

        assert [r.call_status for r in ledger.rows] == ["failed"]


class TestCollectorStreamEdgeCases:
    """Edge cases for generate_stream()."""

    @pytest.mark.asyncio
    async def test_empty_stream_creates_zero_token_record(self, ledger):
        """Empty stream (0 chunks) → record with 0 completion tokens."""
        adapter = FakeAdapter(stream_chunks=[])
        collector = TelemetryCollector(adapter, project="proj", ledger=ledger.db)
        config = GenerationConfig(model="fake-model", max_output_tokens=1000)

        chunks = []
        async for chunk in collector.generate_stream([], config):
            chunks.append(chunk)

        assert chunks == []
        assert len(ledger.rows) == 1
        assert ledger.rows[0].completion_tokens == 0

    @pytest.mark.asyncio
    async def test_stream_error_mid_stream_is_recorded_failed(self, ledger):
        """Adapter raises mid-stream → the call is `failed`."""
        adapter = FakeAdapter()
        adapter.generate_stream = _raise_stream_error
        collector = TelemetryCollector(adapter, project="proj", ledger=ledger.db)
        config = GenerationConfig(model="fake-model", max_output_tokens=1000)

        with pytest.raises(RuntimeError, match="stream exploded"):
            async for _chunk in collector.generate_stream([], config):
                pass

        assert [r.call_status for r in ledger.rows] == ["failed"]


# ---------------------------------------------------------------------------
# Helper functions for exception tests
# ---------------------------------------------------------------------------


async def _raise_adapter_error(messages, config):
    msg = "adapter exploded"
    raise RuntimeError(msg)


async def _raise_adapter_error_tools(
    messages, config, tool_executor, on_tool_round=None, before_request=None
):
    msg = "adapter exploded"
    raise RuntimeError(msg)


async def _raise_stream_error(messages, config):
    yield "partial"
    msg = "stream exploded"
    raise RuntimeError(msg)


class TestTelemetryCollectorPrices:
    """Prices come from one lookup (the catalogue); an unknown price stays unknown."""

    @pytest.mark.asyncio
    async def test_a_known_price_is_recorded_and_spent(self, ledger) -> None:
        from specweaver.core.config.llm_settings import ModelFacts
        from specweaver.infrastructure.llm.budget import CallScope, Limit, SpendBudget
        from specweaver.infrastructure.llm.prices import PriceBook

        budget = SpendBudget()
        facts = PriceBook.of(ModelFacts(usd_per_million_input=2.0, usd_per_million_output=10.0))
        run = Limit("brake.hosted_spend_per_run", "usd", 100.0)
        collector = TelemetryCollector(
            FakeAdapter(),
            "p",
            prices={"m": facts}.get,
            budget=budget,
            scope_of=lambda _config: CallScope(limits=(run,), prices=facts),
            ledger=ledger.db,
        )

        await collector.generate([], GenerationConfig(model="m", max_output_tokens=1000))

        assert ledger.rows[0].estimated_cost_usd == pytest.approx(100 / 1e6 * 2 + 50 / 1e6 * 10)
        assert budget.spent(run.key) == pytest.approx(ledger.rows[0].estimated_cost_usd)

    @pytest.mark.asyncio
    async def test_an_unknown_price_counts_tokens_and_warns_once(
        self, ledger, caplog: pytest.LogCaptureFixture
    ) -> None:
        from specweaver.infrastructure.llm.budget import CallScope, Limit, SpendBudget

        budget = SpendBudget()
        tokens = Limit("brake.tokens_per_run", "tokens", 10_000)
        collector = TelemetryCollector(
            FakeAdapter(),
            "p",
            prices=lambda model: None,
            budget=budget,
            scope_of=lambda _config: CallScope(limits=(tokens,)),
            ledger=ledger.db,
        )

        with caplog.at_level("WARNING"):
            await collector.generate(
                [], GenerationConfig(model="qwen3-coder-next", max_output_tokens=1000)
            )
            await collector.generate(
                [], GenerationConfig(model="qwen3-coder-next", max_output_tokens=1000)
            )

        assert [r.estimated_cost_usd for r in ledger.rows] == [None, None]
        assert budget.spent(tokens.key) == 300
        warnings = [r for r in caplog.records if "qwen3-coder-next" in r.getMessage()]
        assert len(warnings) == 1


def test_the_collector_does_not_import_nest_asyncio() -> None:
    """Asserted at module level on purpose, not by observing one call.

    `nest_asyncio.apply` patches the loop CLASS and leaves it patched for the whole process,
    so a before/after comparison inside one test passes spuriously as soon as any earlier
    test has already triggered it. The only order-independent statement is that this module
    does not reach for the library at all.
    """
    from specweaver.infrastructure.llm import collector as collector_module

    assert not hasattr(collector_module, "nest_asyncio")
