# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.core.config.settings import LLMSettings
from specweaver.infrastructure.llm.factory import create_llm_adapter
from specweaver.infrastructure.llm.models import Message, Role


@pytest.fixture
def mock_telemetry() -> None:
    with patch("specweaver.infrastructure.llm.factory.TelemetryCollector") as mock_col:
        instance = mock_col.return_value
        instance.record_usage = AsyncMock()

        # We need the patched class to behave like an adapter, so it needs a generate method
        # But wait, if we mock TelemetryCollector, we mock the whole wrapper! We won't actually call generate on the real adapter.
        # Instead, let's not mock TelemetryCollector, but mock `record_usage` on the collector module or the store.
        # Actually, let's patch the underlying _store.record_usage if we can.
        pass

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider, env_var",
    [
        ("gemini", "GEMINI_API_KEY"),
        ("openai", "OPENAI_API_KEY"),
        ("anthropic", "ANTHROPIC_API_KEY"),
        ("mistral", "MISTRAL_API_KEY"),
        ("qwen", "QWEN_API_KEY"),
    ],
)
async def test_provider_e2e_flow(
    provider: str,
    env_var: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 1. Setup Environment
    monkeypatch.setenv(env_var, "fake-api-key")

    class MockSettings:
        llm = LLMSettings(provider=provider, model="fake-model", max_output_tokens=100)

    # 3. Create adapter via factory with telemetry enabled
    mock_settings = cast("Any", MockSettings())
    _settings, adapter, config = create_llm_adapter(mock_settings, telemetry_project="test-proj")

    # Unwind the wrappers: TelemetryCollector -> AsyncRateLimiterAdapter -> ActualAdapter
    actual_adapter = adapter._adapter._wrapped
    assert actual_adapter.provider_name == provider

    # 2. Setup mocks for provider SDKs
    client_mock = MagicMock()

    if provider in ("openai", "qwen"):
        mock_choice = MagicMock()
        mock_choice.message.content = f"Response from {provider}"
        mock_choice.finish_reason = "stop"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30
        client_mock.chat.completions.create = AsyncMock(return_value=mock_response)
    elif provider == "anthropic":
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(type="text", text=f"Response from {provider}")]
        mock_msg.stop_reason = "end_turn"
        mock_msg.usage.input_tokens = 10
        mock_msg.usage.output_tokens = 20
        client_mock.messages.create = AsyncMock(return_value=mock_msg)
    elif provider == "mistral":
        mock_choice = MagicMock()
        mock_choice.message.content = f"Response from {provider}"
        mock_choice.finish_reason = "stop"
        mock_msg = MagicMock()
        mock_msg.choices = [mock_choice]
        mock_msg.usage.prompt_tokens = 10
        mock_msg.usage.completion_tokens = 20
        mock_msg.usage.total_tokens = 30
        client_mock.chat.complete_async = AsyncMock(return_value=mock_msg)
    elif provider == "gemini":
        mock_resp = MagicMock()
        mock_resp.text = f"Response from {provider}"
        mock_resp.usage_metadata.prompt_token_count = 10
        mock_resp.usage_metadata.candidates_token_count = 20
        mock_resp.usage_metadata.total_token_count = 30
        mock_resp.candidates = [MagicMock(finish_reason=1)]
        client_mock.aio.models.generate_content = AsyncMock(return_value=mock_resp)

    # Force adapter to use our mock client
    actual_adapter._client = client_mock

    # 4. Generate response
    messages = [Message(role=Role.USER, content="Hello")]

    # Telemetry should be captured by the wrapper
    result = await adapter.generate(messages, config)

    # 5. Assertions
    assert result.text == f"Response from {provider}"

    # Verify Telemetry was recorded
    assert len(adapter.records) == 1
    record = adapter.records[0]
    assert record.provider == provider
    assert record.model == "fake-model"
    assert record.prompt_tokens == 10
    assert record.completion_tokens == 20
    assert record.total_tokens == 30
