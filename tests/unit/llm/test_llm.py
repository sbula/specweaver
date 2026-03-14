# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for LLM layer — models, errors, adapter, and Gemini adapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from specweaver.llm.errors import (
    AuthenticationError,
    ContentFilterError,
    GenerationError,
    LLMError,
    ModelNotFoundError,
    RateLimitError,
)
from specweaver.llm.gemini_adapter import GeminiAdapter, _messages_to_gemini
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
# Message conversion tests
# ---------------------------------------------------------------------------


class TestMessageConversion:
    """Test message conversion to Gemini format."""

    def test_extracts_system_instruction(self) -> None:
        messages = [
            Message(role=Role.SYSTEM, content="You are helpful"),
            Message(role=Role.USER, content="Hello"),
        ]
        system, contents = _messages_to_gemini(messages)
        assert system == "You are helpful"
        assert len(contents) == 1

    def test_no_system_message(self) -> None:
        messages = [
            Message(role=Role.USER, content="Hello"),
        ]
        system, contents = _messages_to_gemini(messages)
        assert system is None
        assert len(contents) == 1

    def test_multi_turn_conversation(self) -> None:
        messages = [
            Message(role=Role.USER, content="Q1"),
            Message(role=Role.ASSISTANT, content="A1"),
            Message(role=Role.USER, content="Q2"),
        ]
        system, contents = _messages_to_gemini(messages)
        assert system is None
        assert len(contents) == 3


# ---------------------------------------------------------------------------
# Gemini Adapter tests
# ---------------------------------------------------------------------------


class TestGeminiAdapter:
    """Test the Gemini adapter."""

    def test_provider_name(self) -> None:
        adapter = GeminiAdapter(api_key="test-key")
        assert adapter.provider_name == "gemini"

    def test_available_with_key(self) -> None:
        adapter = GeminiAdapter(api_key="test-key")
        assert adapter.available() is True

    def test_available_without_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        adapter = GeminiAdapter(api_key="")
        assert adapter.available() is False

    def test_available_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "env-key")
        adapter = GeminiAdapter()
        assert adapter.available() is True

    def test_no_key_raises_auth_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        adapter = GeminiAdapter(api_key="")
        with pytest.raises(AuthenticationError, match="GEMINI_API_KEY"):
            adapter._get_client()

    @pytest.mark.asyncio
    async def test_generate_with_mock(self) -> None:
        """Test generate with a mocked Gemini client."""
        adapter = GeminiAdapter(api_key="fake-key")

        # Create mock response
        mock_usage = MagicMock()
        mock_usage.prompt_token_count = 10
        mock_usage.candidates_token_count = 20
        mock_usage.total_token_count = 30

        mock_candidate = MagicMock()
        mock_candidate.finish_reason = "STOP"

        mock_response = MagicMock()
        mock_response.text = "Hello from Gemini!"
        mock_response.usage_metadata = mock_usage
        mock_response.candidates = [mock_candidate]

        # Mock the client
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        config = GenerationConfig(model="gemini-2.5-flash")
        messages = [Message(role=Role.USER, content="Hello")]

        result = await adapter.generate(messages, config)

        assert result.text == "Hello from Gemini!"
        assert result.usage.prompt_tokens == 10
        assert result.usage.completion_tokens == 20
        assert result.usage.total_tokens == 30
        assert result.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_generate_auth_error(self) -> None:
        """Test that 401 errors are converted to AuthenticationError."""
        adapter = GeminiAdapter(api_key="bad-key")

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("401 Unauthorized: invalid API key")
        )
        adapter._client = mock_client

        config = GenerationConfig(model="gemini-2.5-flash")
        messages = [Message(role=Role.USER, content="Hello")]

        with pytest.raises(AuthenticationError):
            await adapter.generate(messages, config)

    @pytest.mark.asyncio
    async def test_generate_rate_limit_error(self) -> None:
        """Test that 429 errors are converted to RateLimitError."""
        adapter = GeminiAdapter(api_key="test-key")

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("429 Resource exhausted: rate limit exceeded")
        )
        adapter._client = mock_client

        config = GenerationConfig(model="gemini-2.5-flash")
        messages = [Message(role=Role.USER, content="Hello")]

        with pytest.raises(RateLimitError):
            await adapter.generate(messages, config)

    @pytest.mark.asyncio
    async def test_generate_model_not_found(self) -> None:
        """Test that 404 errors are converted to ModelNotFoundError."""
        adapter = GeminiAdapter(api_key="test-key")

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("404 Not found: model xyz does not exist")
        )
        adapter._client = mock_client

        config = GenerationConfig(model="nonexistent-model")
        messages = [Message(role=Role.USER, content="Hello")]

        with pytest.raises(ModelNotFoundError):
            await adapter.generate(messages, config)

    @pytest.mark.asyncio
    async def test_generate_generic_error(self) -> None:
        """Test that unknown errors are converted to GenerationError."""
        adapter = GeminiAdapter(api_key="test-key")

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("Something unexpected happened")
        )
        adapter._client = mock_client

        config = GenerationConfig(model="gemini-2.5-flash")
        messages = [Message(role=Role.USER, content="Hello")]

        with pytest.raises(GenerationError):
            await adapter.generate(messages, config)

    @pytest.mark.asyncio
    async def test_generate_with_system_instruction(self) -> None:
        """Test that system messages are passed as system_instruction."""
        adapter = GeminiAdapter(api_key="fake-key")

        mock_response = MagicMock()
        mock_response.text = "I am helpful"
        mock_response.usage_metadata = None
        mock_response.candidates = []

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        config = GenerationConfig(model="gemini-2.5-flash")
        messages = [
            Message(role=Role.SYSTEM, content="You are a helpful assistant"),
            Message(role=Role.USER, content="Hello"),
        ]

        result = await adapter.generate(messages, config)
        assert result.text == "I am helpful"

        # Verify system_instruction was passed
        call_kwargs = mock_client.aio.models.generate_content.call_args
        gen_config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
        assert gen_config.system_instruction == "You are a helpful assistant"

    @pytest.mark.asyncio
    async def test_generate_json_format(self) -> None:
        """Test that JSON response format sets the correct MIME type."""
        adapter = GeminiAdapter(api_key="fake-key")

        mock_response = MagicMock()
        mock_response.text = '{"key": "value"}'
        mock_response.usage_metadata = None
        mock_response.candidates = []

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        config = GenerationConfig(model="gemini-2.5-flash", response_format="json")
        messages = [Message(role=Role.USER, content="Give me JSON")]

        result = await adapter.generate(messages, config)
        assert result.text == '{"key": "value"}'

        call_kwargs = mock_client.aio.models.generate_content.call_args
        gen_config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
        assert gen_config.response_mime_type == "application/json"

    def test_parse_response_content_filter(self) -> None:
        """Test that safety-blocked responses set finish_reason."""
        adapter = GeminiAdapter(api_key="fake-key")

        mock_candidate = MagicMock()
        mock_candidate.finish_reason = "SAFETY"

        mock_response = MagicMock()
        mock_response.text = ""
        mock_response.usage_metadata = None
        mock_response.candidates = [mock_candidate]

        result = adapter._parse_response(mock_response, "test-model")
        assert result.finish_reason == "content_filter"

    def test_parse_response_max_tokens(self) -> None:
        """Test that max_tokens finish reason is detected."""
        adapter = GeminiAdapter(api_key="fake-key")

        mock_candidate = MagicMock()
        mock_candidate.finish_reason = "MAX_TOKENS"

        mock_response = MagicMock()
        mock_response.text = "Truncated..."
        mock_response.usage_metadata = None
        mock_response.candidates = [mock_candidate]

        result = adapter._parse_response(mock_response, "test-model")
        assert result.finish_reason == "max_tokens"


# ---------------------------------------------------------------------------
# GeminiAdapter — behavioral tests (exceptions, boundaries)
# ---------------------------------------------------------------------------


class TestGeminiAdapterBehavioral:
    """Behavioral tests: exception wrapping, boundaries."""

    def test_handle_error_preserves_traceback(self) -> None:
        """Exception: wrapped errors preserve original via 'from exc'."""
        adapter = GeminiAdapter(api_key="test")
        original = ValueError("original cause")

        with pytest.raises(GenerationError) as exc_info:
            adapter._handle_error(original)

        assert exc_info.value.__cause__ is original

    def test_handle_error_safety_maps_to_content_filter(self) -> None:
        """Failure: 'safety' keyword maps to ContentFilterError."""
        adapter = GeminiAdapter(api_key="test")
        with pytest.raises(ContentFilterError):
            adapter._handle_error(Exception("safety blocked"))

    def test_parse_response_none_text(self) -> None:
        """Boundary: response.text is None → returns empty string."""
        adapter = GeminiAdapter(api_key="test")

        mock_response = MagicMock()
        mock_response.text = None
        mock_response.usage_metadata = None
        mock_response.candidates = []

        result = adapter._parse_response(mock_response, "test-model")
        assert result.text == ""

    def test_lazy_client_initialization(self) -> None:
        """Startup: client is NOT created at init, only on first use."""
        adapter = GeminiAdapter(api_key="test-key")
        assert adapter._client is None

    def test_empty_messages_conversion(self) -> None:
        """Boundary: empty messages list → empty contents."""
        system, contents = _messages_to_gemini([])
        assert system is None
        assert contents == []


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


# ---------------------------------------------------------------------------
# estimate_tokens / count_tokens tests
# ---------------------------------------------------------------------------


class TestTokenCounting:
    """Test LLMAdapter.estimate_tokens and GeminiAdapter.count_tokens."""

    def test_estimate_tokens_heuristic(self) -> None:
        """Default estimate_tokens uses len // 4."""
        adapter = GeminiAdapter(api_key="test-key")
        # 100 characters → ~25 tokens
        text = "a" * 100
        assert adapter.estimate_tokens(text) == 25

    def test_estimate_tokens_empty(self) -> None:
        adapter = GeminiAdapter(api_key="test-key")
        assert adapter.estimate_tokens("") == 0

    def test_estimate_tokens_short(self) -> None:
        adapter = GeminiAdapter(api_key="test-key")
        assert adapter.estimate_tokens("hi") == 0  # 2 // 4 = 0

    @pytest.mark.asyncio
    async def test_count_tokens_with_mock(self) -> None:
        """count_tokens uses Gemini's native API."""
        adapter = GeminiAdapter(api_key="fake-key")

        mock_response = MagicMock()
        mock_response.total_tokens = 42

        mock_client = MagicMock()
        mock_client.aio.models.count_tokens = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        result = await adapter.count_tokens("Hello, world!", "gemini-2.5-flash")
        assert result == 42

        # Verify correct API call
        mock_client.aio.models.count_tokens.assert_called_once_with(
            model="gemini-2.5-flash",
            contents="Hello, world!",
        )

    @pytest.mark.asyncio
    async def test_count_tokens_auth_error(self) -> None:
        """count_tokens with 401 error raises AuthenticationError."""
        adapter = GeminiAdapter(api_key="bad-key")

        mock_client = MagicMock()
        mock_client.aio.models.count_tokens = AsyncMock(
            side_effect=Exception("401 Unauthorized: invalid API key"),
        )
        adapter._client = mock_client

        with pytest.raises(AuthenticationError):
            await adapter.count_tokens("test", "gemini-2.5-flash")


