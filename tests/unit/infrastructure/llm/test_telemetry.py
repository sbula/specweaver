# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for llm/telemetry.py — UsageRecord, cost estimation, record creation."""

from __future__ import annotations

import pytest

from specweaver.core.config.llm_settings import ModelFacts
from specweaver.infrastructure.llm.models import GenerationConfig, LLMResponse, TaskType, TokenUsage
from specweaver.infrastructure.llm.telemetry import create_usage_record, estimate_cost


class TestTaskTypeEnum:
    """TaskType StrEnum tests."""

    def test_all_members_are_strings(self):
        for member in TaskType:
            assert isinstance(member.value, str)

    def test_expected_members(self):
        expected = {"draft", "review", "plan", "implement", "validate", "check", "unknown"}
        actual = {m.value for m in TaskType}
        assert actual == expected

    def test_string_comparison(self):
        assert TaskType.DRAFT == "draft"
        assert TaskType.REVIEW == "review"


class TestEstimateCost:
    """Prices are USD per 1M tokens, from the catalogue; an unknown price is unknown, never 0."""

    def test_a_known_price_is_per_million_tokens(self):
        facts = ModelFacts(usd_per_million_input=3.0, usd_per_million_output=15.0)
        usage = TokenUsage(prompt_tokens=1000, completion_tokens=500)

        assert estimate_cost(usage, facts) == pytest.approx(0.003 + 0.0075)

    def test_a_free_model_costs_zero(self):
        facts = ModelFacts(usd_per_million_input=0.0, usd_per_million_output=0.0)

        assert estimate_cost(TokenUsage(prompt_tokens=10, completion_tokens=10), facts) == 0.0

    def test_an_unknown_model_has_an_unknown_cost(self):
        assert estimate_cost(TokenUsage(prompt_tokens=10, completion_tokens=10), None) is None

    def test_half_a_price_is_an_unknown_cost(self):
        facts = ModelFacts(usd_per_million_input=3.0)

        assert estimate_cost(TokenUsage(prompt_tokens=10, completion_tokens=10), facts) is None


class TestCreateUsageRecord:
    """create_usage_record() factory tests."""

    def test_all_fields_populated(self):
        config = GenerationConfig(
            model="gemini-3-flash-preview",
            task_type=TaskType.REVIEW,
            run_id="test-run-123",
        )
        response = LLMResponse(
            text="result",
            model="gemini-3-flash-preview",
            usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        )
        facts = ModelFacts(usd_per_million_input=1.0, usd_per_million_output=2.0)
        record = create_usage_record(config, response, "gemini", "myproject", 1234, facts)
        assert record.timestamp  # Non-empty ISO string
        assert record.project_name == "myproject"
        assert record.task_type == "review"
        assert record.model == "gemini-3-flash-preview"
        assert record.provider == "gemini"
        assert record.prompt_tokens == 100
        assert record.completion_tokens == 50
        assert record.total_tokens == 150
        assert record.estimated_cost_usd == pytest.approx(100 / 1e6 * 1.0 + 50 / 1e6 * 2.0)
        assert record.duration_ms == 1234
        assert record.run_id == "test-run-123"

    def test_run_id_populated(self):
        config = GenerationConfig(model="gemini", run_id="my-uuid-1234")
        response = LLMResponse(text="", model="gemini")
        record = create_usage_record(config, response, "gemini", "proj", 0)
        assert record.run_id == "my-uuid-1234"

    def test_unknown_task_type_default(self):
        config = GenerationConfig(model="gemini-3-flash-preview")
        response = LLMResponse(
            text="",
            model="gemini-3-flash-preview",
            usage=TokenUsage(),
        )
        record = create_usage_record(config, response, "gemini", "proj", 0)
        assert record.task_type == "unknown"

    def test_model_dump_produces_dict(self):
        config = GenerationConfig(model="gemini-3-flash-preview", task_type=TaskType.DRAFT)
        response = LLMResponse(
            text="",
            model="gemini-3-flash-preview",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        )
        record = create_usage_record(config, response, "gemini", "proj", 500)
        d = record.model_dump()
        assert isinstance(d, dict)
        assert "timestamp" in d
        assert "estimated_cost_usd" in d
        assert d["task_type"] == "draft"

    def test_the_price_comes_from_the_facts_given(self):
        config = GenerationConfig(model="my-model", task_type=TaskType.CHECK)
        response = LLMResponse(
            text="",
            model="my-model",
            usage=TokenUsage(prompt_tokens=1000, completion_tokens=1000, total_tokens=2000),
        )
        facts = ModelFacts(usd_per_million_input=10.0, usd_per_million_output=20.0)

        record = create_usage_record(config, response, "custom", "proj", 100, facts)

        assert record.estimated_cost_usd == pytest.approx(0.03)

    def test_zero_token_response(self):
        """create_usage_record with zero tokens produces zero cost."""
        config = GenerationConfig(model="gemini-3-flash-preview", task_type=TaskType.DRAFT)
        response = LLMResponse(
            text="",
            model="gemini-3-flash-preview",
            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )
        facts = ModelFacts(usd_per_million_input=1.0, usd_per_million_output=2.0)
        record = create_usage_record(config, response, "gemini", "proj", 42, facts)
        assert record.prompt_tokens == 0
        assert record.completion_tokens == 0
        assert record.total_tokens == 0
        assert record.estimated_cost_usd == 0.0
        assert record.duration_ms == 42

    def test_without_a_price_the_record_says_unknown(self):
        config = GenerationConfig(model="qwen3-coder-next")
        response = LLMResponse(text="", model="qwen3-coder-next", usage=TokenUsage(total_tokens=9))

        record = create_usage_record(config, response, "openai-compatible", "proj", 0)

        assert record.estimated_cost_usd is None
