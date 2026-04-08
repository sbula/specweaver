# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for LLM data models and error hierarchy."""

from __future__ import annotations

import pytest

from specweaver.llm.errors import (
    AuthenticationError,
    ContentFilterError,
    GenerationError,
    LLMError,
    ModelNotFoundError,
    RateLimitError,
)
from specweaver.llm.models import (
    GenerationConfig,
    LLMResponse,
    Message,
    Role,
    TokenUsage,
)

# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestLLMModels:
    """Test LLM data models."""

    def test_message_creation(self) -> None:
        msg = Message(role=Role.USER, content="Hello")
        assert msg.role == Role.USER
        assert msg.content == "Hello"

    def test_generation_config_defaults(self) -> None:
        config = GenerationConfig(model="gemini-2.5-flash")
        assert config.temperature == 0.7
        assert config.max_output_tokens == 4096
        assert config.response_format == "text"
        assert config.system_instruction is None

    def test_generation_config_validation(self) -> None:
        with pytest.raises(ValueError):
            GenerationConfig(model="test", temperature=-1.0)
        with pytest.raises(ValueError):
            GenerationConfig(model="test", max_output_tokens=0)

    def test_token_usage_defaults(self) -> None:
        usage = TokenUsage()
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_tokens == 0

    def test_llm_response_defaults(self) -> None:
        resp = LLMResponse(text="hello", model="gemini-2.5-flash")
        assert resp.finish_reason == "stop"
        assert resp.usage.total_tokens == 0

    def test_role_enum(self) -> None:
        assert Role.SYSTEM.value == "system"
        assert Role.USER.value == "user"
        assert Role.ASSISTANT.value == "assistant"

    def test_generation_config_json_format(self) -> None:
        config = GenerationConfig(model="test", response_format="json")
        assert config.response_format == "json"


# ---------------------------------------------------------------------------
# Error tests
# ---------------------------------------------------------------------------


class TestLLMErrors:
    """Test LLM error hierarchy."""

    def test_llm_error_is_exception(self) -> None:
        err = LLMError("test error", provider="gemini")
        assert isinstance(err, Exception)
        assert err.provider == "gemini"
        assert str(err) == "test error"

    def test_auth_error_hierarchy(self) -> None:
        err = AuthenticationError("bad key", provider="gemini")
        assert isinstance(err, LLMError)

    def test_rate_limit_with_retry(self) -> None:
        err = RateLimitError("slow down", provider="gemini", retry_after=30.0)
        assert isinstance(err, LLMError)
        assert err.retry_after == 30.0

    def test_rate_limit_without_retry(self) -> None:
        err = RateLimitError("slow down", provider="gemini")
        assert err.retry_after is None

    def test_all_errors_are_llm_error(self) -> None:
        for cls in [
            AuthenticationError,
            RateLimitError,
            ModelNotFoundError,
            GenerationError,
            ContentFilterError,
        ]:
            err = cls("test", provider="test")
            assert isinstance(err, LLMError)


# ---------------------------------------------------------------------------
# TokenBudget tests
# ---------------------------------------------------------------------------


class TestTokenBudget:
    """Test TokenBudget lifecycle tracking."""

    def test_defaults(self) -> None:
        from specweaver.llm.models import TokenBudget

        budget = TokenBudget()
        assert budget.limit == 128_000
        assert budget.used == 0
        assert budget.remaining == 128_000
        assert budget.exceeded is False
        assert budget.warning is False

    def test_add_tokens(self) -> None:
        from specweaver.llm.models import TokenBudget

        budget = TokenBudget(limit=1000)
        budget.add(300)
        assert budget.used == 300
        assert budget.remaining == 700

    def test_exceeded(self) -> None:
        from specweaver.llm.models import TokenBudget

        budget = TokenBudget(limit=100)
        budget.add(150)
        assert budget.exceeded is True
        assert budget.remaining == 0

    def test_warning_at_80_pct(self) -> None:
        from specweaver.llm.models import TokenBudget

        budget = TokenBudget(limit=1000)
        budget.add(800)
        assert budget.warning is False  # exactly 80% is not > 80%
        budget.add(1)
        assert budget.warning is True

    def test_usage_pct(self) -> None:
        from specweaver.llm.models import TokenBudget

        budget = TokenBudget(limit=200)
        budget.add(50)
        assert budget.usage_pct == pytest.approx(25.0)

    def test_summary_format(self) -> None:
        from specweaver.llm.models import TokenBudget

        budget = TokenBudget(limit=128_000)
        budget.add(12_400)
        summary = budget.summary()
        assert "12,400" in summary
        assert "128,000" in summary
        assert "9.7%" in summary

    def test_custom_limit(self) -> None:
        from specweaver.llm.models import TokenBudget

        budget = TokenBudget(limit=1_048_576)
        assert budget.limit == 1_048_576
        assert budget.remaining == 1_048_576
