# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for llm/telemetry.py — UsageRecord, cost estimation, record creation."""

from __future__ import annotations

import pytest

from specweaver.llm.models import GenerationConfig, LLMResponse, TaskType, TokenUsage
from specweaver.llm.telemetry import (
    CostEntry,
    create_usage_record,
    estimate_cost,
    get_default_cost_table,
)


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
    """estimate_cost() tests."""

    def test_known_model_returns_nonzero(self):
        usage = TokenUsage(prompt_tokens=1000, completion_tokens=500)
        cost = estimate_cost("gemini-3-flash-preview", usage)
        assert cost > 0

    def test_known_model_correct_calculation(self):
        """Verify math: (1000/1000)*0.0001 + (500/1000)*0.0004 = 0.0003."""
        usage = TokenUsage(prompt_tokens=1000, completion_tokens=500)
        cost = estimate_cost("gemini-3-flash-preview", usage)
        assert cost == pytest.approx(0.0003, abs=1e-8)

    def test_unknown_model_returns_zero(self):
        usage = TokenUsage(prompt_tokens=1000, completion_tokens=500)
        cost = estimate_cost("some-unknown-model-xyz", usage)
        assert cost == 0.0

    def test_zero_tokens_returns_zero(self):
        usage = TokenUsage(prompt_tokens=0, completion_tokens=0)
        cost = estimate_cost("gemini-3-flash-preview", usage)
        assert cost == 0.0

    def test_override_takes_precedence(self):
        usage = TokenUsage(prompt_tokens=1000, completion_tokens=1000)
        overrides = {"gemini-3-flash-preview": CostEntry(1.0, 2.0)}
        cost = estimate_cost("gemini-3-flash-preview", usage, overrides=overrides)
        # (1000/1000)*1.0 + (1000/1000)*2.0 = 3.0
        assert cost == pytest.approx(3.0)

    def test_override_for_unknown_model(self):
        """Override can add pricing for models not in DEFAULT_COST_TABLE."""
        usage = TokenUsage(prompt_tokens=100, completion_tokens=100)
        overrides = {"my-custom-model": CostEntry(0.5, 1.0)}
        cost = estimate_cost("my-custom-model", usage, overrides=overrides)
        # (100/1000)*0.5 + (100/1000)*1.0 = 0.15
        assert cost == pytest.approx(0.15)

    def test_empty_overrides_falls_through(self):
        usage = TokenUsage(prompt_tokens=1000, completion_tokens=500)
        cost = estimate_cost("gemini-3-flash-preview", usage, overrides={})
        assert cost > 0  # Falls through to get_default_cost_table()


class TestCostTableStructure:
    """get_default_cost_table() integrity."""

    def test_all_entries_are_cost_entries(self):
        for model, entry in get_default_cost_table().items():
            assert isinstance(entry, CostEntry), f"{model} is not a CostEntry"

    def test_all_entries_have_positive_costs(self):
        for model, entry in get_default_cost_table().items():
            assert entry.input_cost_per_1k > 0, f"{model} input cost <= 0"
            assert entry.output_cost_per_1k > 0, f"{model} output cost <= 0"

    def test_table_not_empty(self):
        assert len(get_default_cost_table()) >= 5  # At least 5 models


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
        record = create_usage_record(config, response, "gemini", "myproject", 1234)
        assert record.timestamp  # Non-empty ISO string
        assert record.project_name == "myproject"
        assert record.task_type == "review"
        assert record.model == "gemini-3-flash-preview"
        assert record.provider == "gemini"
        assert record.prompt_tokens == 100
        assert record.completion_tokens == 50
        assert record.total_tokens == 150
        assert record.estimated_cost_usd > 0
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

    def test_cost_overrides_applied(self):
        config = GenerationConfig(model="my-model", task_type=TaskType.CHECK)
        response = LLMResponse(
            text="",
            model="my-model",
            usage=TokenUsage(prompt_tokens=1000, completion_tokens=1000, total_tokens=2000),
        )
        overrides = {"my-model": CostEntry(10.0, 20.0)}
        record = create_usage_record(
            config,
            response,
            "custom",
            "proj",
            100,
            cost_overrides=overrides,
        )
        # (1000/1000)*10 + (1000/1000)*20 = 30
        assert record.estimated_cost_usd == pytest.approx(30.0)

    def test_zero_token_response(self):
        """create_usage_record with zero tokens produces zero cost."""
        config = GenerationConfig(model="gemini-3-flash-preview", task_type=TaskType.DRAFT)
        response = LLMResponse(
            text="",
            model="gemini-3-flash-preview",
            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )
        record = create_usage_record(config, response, "gemini", "proj", 42)
        assert record.prompt_tokens == 0
        assert record.completion_tokens == 0
        assert record.total_tokens == 0
        assert record.estimated_cost_usd == 0.0
        assert record.duration_ms == 42
