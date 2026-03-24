# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for Gemini LLM adapter — message conversion, generation, errors."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from specweaver.llm.adapters.gemini import GeminiAdapter, _messages_to_gemini
from specweaver.llm.errors import (
    AuthenticationError,
    ContentFilterError,
    GenerationError,
    ModelNotFoundError,
    RateLimitError,
)
from specweaver.llm.models import (
    GenerationConfig,
    Message,
    Role,
)

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
# Token counting tests
# ---------------------------------------------------------------------------


class TestTokenCounting:
    """Test LLMAdapter.estimate_tokens and GeminiAdapter.count_tokens."""

    def test_estimate_tokens_heuristic(self) -> None:
        """Default estimate_tokens uses len // 4."""
        adapter = GeminiAdapter(api_key="test-key")
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


# ---------------------------------------------------------------------------
# generate_with_tools() tests
# ---------------------------------------------------------------------------


class TestGenerateWithTools:
    """Tests for the agentic tool-use loop."""

    @pytest.mark.asyncio
    async def test_no_tool_calls_returns_text(self) -> None:
        """When LLM returns text without tool calls, return directly."""
        adapter = GeminiAdapter(api_key="fake-key")

        mock_response = MagicMock()
        mock_response.text = "Final answer"
        mock_response.usage_metadata = None
        mock_response.candidates = [MagicMock(finish_reason="STOP")]
        mock_response.function_calls = None

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        from specweaver.llm.models import ToolDefinition

        config = GenerationConfig(
            model="gemini-2.5-flash",
            tools=[ToolDefinition(name="grep", description="search")],
        )
        messages = [Message(role=Role.USER, content="Hello")]
        mock_executor = AsyncMock()

        result = await adapter.generate_with_tools(messages, config, mock_executor)
        assert result.text == "Final answer"
        mock_executor.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_single_tool_call_round(self) -> None:
        """LLM calls a tool, gets result, then returns text."""
        adapter = GeminiAdapter(api_key="fake-key")

        # Round 1: tool call
        mock_fc = MagicMock()
        mock_fc.name = "grep"
        mock_fc.args = {"pattern": "hello"}

        mock_response_1 = MagicMock()
        mock_response_1.text = ""
        mock_response_1.usage_metadata = None
        mock_response_1.candidates = [MagicMock(content=MagicMock())]
        mock_response_1.function_calls = [mock_fc]

        # Round 2: final text
        mock_response_2 = MagicMock()
        mock_response_2.text = "Found 3 matches"
        mock_response_2.usage_metadata = None
        mock_response_2.candidates = [MagicMock(finish_reason="STOP")]
        mock_response_2.function_calls = None

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=[mock_response_1, mock_response_2],
        )
        adapter._client = mock_client

        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {"results": [{"file": "main.py", "line_number": 1}]}

        from specweaver.llm.models import ToolDefinition

        config = GenerationConfig(
            model="gemini-2.5-flash",
            tools=[ToolDefinition(name="grep", description="search")],
        )
        messages = [Message(role=Role.USER, content="Search for hello")]

        result = await adapter.generate_with_tools(messages, config, mock_executor)
        assert result.text == "Found 3 matches"
        mock_executor.execute.assert_called_once_with("grep", {"pattern": "hello"})

    @pytest.mark.asyncio
    async def test_no_tools_config_falls_back_to_generate(self) -> None:
        """When config.tools is None, fall back to regular generate()."""
        adapter = GeminiAdapter(api_key="fake-key")

        mock_response = MagicMock()
        mock_response.text = "Direct response"
        mock_response.usage_metadata = None
        mock_response.candidates = [MagicMock(finish_reason="STOP")]

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        config = GenerationConfig(model="gemini-2.5-flash")  # No tools
        messages = [Message(role=Role.USER, content="Hello")]

        result = await adapter.generate_with_tools(messages, config, AsyncMock())
        assert result.text == "Direct response"

    @pytest.mark.asyncio
    async def test_base_adapter_fallback(self) -> None:
        """Base adapter's generate_with_tools falls back to generate()."""
        adapter = GeminiAdapter(api_key="fake-key")

        mock_response = MagicMock()
        mock_response.text = "Fallback"
        mock_response.usage_metadata = None
        mock_response.candidates = [MagicMock(finish_reason="STOP")]

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        # Call the base class method explicitly (no tools)
        from specweaver.llm.adapters.base import LLMAdapter

        config = GenerationConfig(model="gemini-2.5-flash")
        messages = [Message(role=Role.USER, content="Hello")]

        result = await LLMAdapter.generate_with_tools(
            adapter, messages, config, AsyncMock(),
        )
        assert result.text == "Fallback"

