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
from specweaver.infrastructure.llm.telemetry import CostEntry

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

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
        self, messages, config, tool_executor, on_tool_round=None
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
    async def test_captures_one_record(self):
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="test-proj")
        config = GenerationConfig(model="fake-model", task_type=TaskType.DRAFT)

        response = await collector.generate([], config)

        assert response.text == "hello"
        assert len(collector.records) == 1
        record = collector.records[0]
        assert record.project_name == "test-proj"
        assert record.task_type == "draft"
        assert record.model == "fake-model"
        assert record.provider == "fake"
        assert record.prompt_tokens == 100
        assert record.completion_tokens == 50

    @pytest.mark.asyncio
    async def test_timing_is_positive(self):
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="test-proj")
        config = GenerationConfig(model="fake-model")

        await collector.generate([], config)

        assert collector.records[0].duration_ms >= 0

    @pytest.mark.asyncio
    async def test_task_type_from_config_not_constructor(self):
        """task_type comes from config.task_type, not the collector constructor."""
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="proj")

        config1 = GenerationConfig(model="fake-model", task_type=TaskType.REVIEW)
        config2 = GenerationConfig(model="fake-model", task_type=TaskType.IMPLEMENT)

        await collector.generate([], config1)
        await collector.generate([], config2)

        assert collector.records[0].task_type == "review"
        assert collector.records[1].task_type == "implement"


class TestCollectorGenerateWithTools:
    """Test telemetry capture for generate_with_tools()."""

    @pytest.mark.asyncio
    async def test_captures_one_record(self):
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="proj")
        config = GenerationConfig(model="fake-model", task_type=TaskType.REVIEW)

        response = await collector.generate_with_tools([], config, MagicMock())

        assert response.text == "hello"
        assert len(collector.records) == 1
        assert collector.records[0].task_type == "review"


class TestCollectorGenerateStream:
    """Test telemetry capture for generate_stream()."""

    @pytest.mark.asyncio
    async def test_captures_record_after_stream(self):
        adapter = FakeAdapter(stream_chunks=["hello", " world", "!"])
        collector = TelemetryCollector(adapter, project="proj")
        config = GenerationConfig(model="fake-model", task_type=TaskType.DRAFT)

        chunks = []
        async for chunk in collector.generate_stream([], config):
            chunks.append(chunk)

        assert chunks == ["hello", " world", "!"]
        assert len(collector.records) == 1
        record = collector.records[0]
        assert record.task_type == "draft"
        assert record.completion_tokens > 0  # Estimated from text
        assert record.prompt_tokens == 0  # Known gap for streaming


class TestCollectorMultipleCalls:
    """Test that each call produces a separate record."""

    @pytest.mark.asyncio
    async def test_three_calls_three_records(self):
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="proj")

        await collector.generate([], GenerationConfig(model="m", task_type=TaskType.DRAFT))
        await collector.generate([], GenerationConfig(model="m", task_type=TaskType.REVIEW))
        await collector.generate([], GenerationConfig(model="m", task_type=TaskType.IMPLEMENT))

        assert len(collector.records) == 3
        types = [r.task_type for r in collector.records]
        assert types == ["draft", "review", "implement"]


class TestCollectorFlush:
    """Test flush() persistence."""

    @pytest.mark.asyncio
    async def test_flush_calls_log_usage(self):
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="proj")
        config = GenerationConfig(model="fake-model")
        await collector.generate([], config)
        await collector.generate([], config)

        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_db.async_session_scope.return_value.__aenter__.return_value = mock_session

        from unittest.mock import AsyncMock, patch
        with patch("specweaver.infrastructure.llm.collector.LlmRepository") as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.log_usage = AsyncMock()
            count = collector.flush(mock_db)

            assert count == 2
            assert mock_repo.log_usage.call_count == 2
            assert len(collector.records) == 0  # Cleared

    @pytest.mark.asyncio
    async def test_flush_empty_returns_zero(self):
        collector = TelemetryCollector(FakeAdapter(), project="proj")
        mock_db = MagicMock()

        from unittest.mock import AsyncMock, patch
        with patch("specweaver.infrastructure.llm.collector.LlmRepository") as mock_repo_cls:
            mock_repo_cls.return_value.log_usage = AsyncMock()
            count = collector.flush(mock_db)
            assert count == 0
            assert mock_repo_cls.return_value.log_usage.call_count == 0

    @pytest.mark.asyncio
    async def test_flush_error_does_not_raise(self):
        """Telemetry failures are logged, not propagated."""
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="proj")
        await collector.generate([], GenerationConfig(model="m"))

        mock_db = MagicMock()
        mock_db.async_session_scope.return_value.__aenter__.return_value = MagicMock()

        from unittest.mock import AsyncMock, patch
        with patch("specweaver.infrastructure.llm.collector.LlmRepository") as mock_repo_cls:
            mock_repo_cls.return_value.log_usage = AsyncMock(side_effect=Exception("DB locked"))

            # Should NOT raise
            count = collector.flush(mock_db)
            assert count == 1


class TestCollectorDelegation:
    """Test that non-generation methods delegate correctly."""

    def test_provider_name(self):
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="proj")
        assert collector.provider_name == "fake"

    def test_available(self):
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="proj")
        assert collector.available() is True

    @pytest.mark.asyncio
    async def test_count_tokens(self):
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="proj")
        count = await collector.count_tokens("hello world", "model")
        assert isinstance(count, int)

    def test_estimate_tokens(self):
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="proj")
        est = collector.estimate_tokens("hello world test data")
        assert isinstance(est, int)
        assert est > 0


class TestCollectorCostOverrides:
    """Test that cost overrides are passed through."""

    @pytest.mark.asyncio
    async def test_overrides_affect_cost(self):
        adapter = FakeAdapter()
        overrides = {"fake-model": CostEntry(100.0, 200.0)}
        collector = TelemetryCollector(adapter, project="proj", cost_overrides=overrides)

        config = GenerationConfig(model="fake-model")
        await collector.generate([], config)

        record = collector.records[0]
        # (100/1000)*100 + (50/1000)*200 = 10 + 10 = 20
        assert record.estimated_cost_usd == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# Corner-case tests (stories 14-19)
# ---------------------------------------------------------------------------


class TestCollectorAdapterExceptions:
    """Adapter exceptions propagate without capturing telemetry."""

    @pytest.mark.asyncio
    async def test_generate_exception_propagates_no_record(self):
        """adapter.generate() raises → exception propagated, no record."""
        adapter = FakeAdapter()
        adapter.generate = _raise_adapter_error
        collector = TelemetryCollector(adapter, project="proj")
        config = GenerationConfig(model="fake-model")

        with pytest.raises(RuntimeError, match="adapter exploded"):
            await collector.generate([], config)

        assert len(collector.records) == 0

    @pytest.mark.asyncio
    async def test_generate_with_tools_exception_propagates_no_record(self):
        """adapter.generate_with_tools() raises → no record."""
        adapter = FakeAdapter()
        adapter.generate_with_tools = _raise_adapter_error_tools
        collector = TelemetryCollector(adapter, project="proj")
        config = GenerationConfig(model="fake-model")

        with pytest.raises(RuntimeError, match="adapter exploded"):
            await collector.generate_with_tools([], config, MagicMock())

        assert len(collector.records) == 0


class TestCollectorStreamEdgeCases:
    """Edge cases for generate_stream()."""

    @pytest.mark.asyncio
    async def test_empty_stream_creates_zero_token_record(self):
        """Empty stream (0 chunks) → record with 0 completion tokens."""
        adapter = FakeAdapter(stream_chunks=[])
        collector = TelemetryCollector(adapter, project="proj")
        config = GenerationConfig(model="fake-model")

        chunks = []
        async for chunk in collector.generate_stream([], config):
            chunks.append(chunk)

        assert chunks == []
        assert len(collector.records) == 1
        assert collector.records[0].completion_tokens == 0

    @pytest.mark.asyncio
    async def test_stream_error_mid_stream_no_record(self):
        """Adapter raises mid-stream → no record captured."""
        adapter = FakeAdapter()
        adapter.generate_stream = _raise_stream_error
        collector = TelemetryCollector(adapter, project="proj")
        config = GenerationConfig(model="fake-model")

        with pytest.raises(RuntimeError, match="stream exploded"):
            async for _chunk in collector.generate_stream([], config):
                pass

        assert len(collector.records) == 0


class TestCollectorFlushEdgeCases:
    """Flush edge cases: double flush, partial failure."""

    @pytest.mark.asyncio
    async def test_double_flush_second_returns_zero(self):
        """Flushing twice: second flush returns 0 (records already cleared)."""
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="proj")
        await collector.generate([], GenerationConfig(model="m"))

        mock_db = MagicMock()
        mock_db.async_session_scope.return_value.__aenter__.return_value = MagicMock()

        from unittest.mock import AsyncMock, patch
        with patch("specweaver.infrastructure.llm.collector.LlmRepository") as mock_repo_cls:
            mock_repo_cls.return_value.log_usage = AsyncMock()
            first = collector.flush(mock_db)
            second = collector.flush(mock_db)

            assert first == 1
            assert second == 0
            assert mock_repo_cls.return_value.log_usage.call_count == 1

    @pytest.mark.asyncio
    async def test_partial_failure_records_not_cleared(self):
        """DB fails mid-flush → records are NOT cleared (preserved for retry)."""
        adapter = FakeAdapter()
        collector = TelemetryCollector(adapter, project="proj")
        await collector.generate([], GenerationConfig(model="m"))
        await collector.generate([], GenerationConfig(model="m"))

        mock_db = MagicMock()
        mock_db.async_session_scope.return_value.__aenter__.return_value = MagicMock()

        from unittest.mock import AsyncMock, patch
        with patch("specweaver.infrastructure.llm.collector.LlmRepository") as mock_repo_cls:
            # Fail on the second call
            mock_repo_cls.return_value.log_usage = AsyncMock(side_effect=[None, Exception("DB error")])

            collector.flush(mock_db)

            # Records NOT cleared because the loop raised before .clear()
            assert len(collector.records) == 2


# ---------------------------------------------------------------------------
# Helper functions for exception tests
# ---------------------------------------------------------------------------


async def _raise_adapter_error(messages, config):
    msg = "adapter exploded"
    raise RuntimeError(msg)


async def _raise_adapter_error_tools(messages, config, tool_executor, on_tool_round=None):
    msg = "adapter exploded"
    raise RuntimeError(msg)


async def _raise_stream_error(messages, config):
    yield "partial"
    msg = "stream exploded"
    raise RuntimeError(msg)
