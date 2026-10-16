# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from specweaver.core.config.llm_settings import LlmSettingsFiles
from specweaver.infrastructure.llm.budget import SpendBudget
from specweaver.infrastructure.llm.models import Message, Role
from specweaver.infrastructure.llm.resolve import RoleResolver
from tests.ledger import Ledger

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider, env_var",
    [
        ("gemini", "GEMINI_API_KEY"),
        ("openai", "OPENAI_API_KEY"),
        ("anthropic", "ANTHROPIC_API_KEY"),
        ("mistral", "MISTRAL_API_KEY"),
    ],
)
async def test_provider_e2e_flow(
    provider: str,
    env_var: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    machine = (
        f'[servers.{provider}]\nkind = "{provider}"\napi_key_env = "{env_var}"\n'
        "private = false\nmax_parallel = 1\n\n"
        f'[roles]\ndefault = {{ model = "fake-model@{provider}", max_output_tokens = 100 }}\n'
        '\n[models."fake-model"]\n'
        "usd_per_million_input = 1.0\nusd_per_million_output = 1.0\nthinking_in_output_cap = true\n"
    )
    files = LlmSettingsFiles.from_texts(
        machine_text=machine,
        machine_source="-",
        project_text="",
        project_source="-",
        keys={env_var: "fake-api-key"},
    )

    # 3. Resolve the role's adapter: the resolver always records telemetry
    ledger = Ledger(tmp_path)
    resolver = RoleResolver(
        files, telemetry_project="test-proj", budget=SpendBudget(), history=ledger.db
    )
    adapter, config = resolver.for_role("draft")

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
    [record] = ledger.rows
    assert record.call_status == "ok"
    assert record.provider == provider
    assert record.model == "fake-model"
    assert record.prompt_tokens == 10
    assert record.completion_tokens == 20
    assert record.total_tokens == 30
