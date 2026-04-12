# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from specweaver.infrastructure.llm.adapters.mistral import MistralAdapter
from specweaver.infrastructure.llm.models import GenerationConfig, Message, Role


class TestMistralAdapter:
    def test_provider_metadata(self) -> None:
        adapter = MistralAdapter(api_key="test")
        assert adapter.provider_name == "mistral"
        assert adapter.api_key_env_var == "MISTRAL_API_KEY"
        assert "mistral-small-4" in MistralAdapter.default_costs

    def test_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MISTRAL_API_KEY", "test")
        assert MistralAdapter().available() is True
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        assert MistralAdapter(api_key="").available() is False

    @pytest.mark.asyncio
    async def test_generate_delegates(self) -> None:
        adapter = MistralAdapter(api_key="test-key")

        mock_choice = MagicMock()
        mock_choice.message.content = "Bonjour from Mistral"
        mock_choice.finish_reason = "stop"

        mock_msg = MagicMock()
        mock_msg.choices = [mock_choice]
        mock_msg.usage.prompt_tokens = 10
        mock_msg.usage.completion_tokens = 20
        mock_msg.usage.total_tokens = 30

        mock_client = MagicMock()
        mock_client.chat.complete_async = AsyncMock(return_value=mock_msg)
        adapter._client = mock_client

        config = GenerationConfig(model="mistral-large-latest")
        messages = [Message(role=Role.USER, content="Bonjour")]

        result = await adapter.generate(messages, config)

        assert result.text == "Bonjour from Mistral"
        assert result.usage.prompt_tokens == 10
        assert result.usage.completion_tokens == 20
        assert result.usage.total_tokens == 30
        assert result.finish_reason == "stop"

        mock_client.chat.complete_async.assert_called_once()
        kwargs = mock_client.chat.complete_async.call_args.kwargs
        assert kwargs["model"] == "mistral-large-latest"
        assert kwargs["messages"] == [{"role": "user", "content": "Bonjour"}]

    @pytest.mark.asyncio
    async def test_generate_with_tools_no_calls(self) -> None:
        adapter = MistralAdapter(api_key="key")

        mock_choice = MagicMock()
        mock_choice.message.content = "No tools used here"
        mock_choice.message.tool_calls = None
        mock_choice.finish_reason = "stop"

        mock_msg = MagicMock()
        mock_msg.choices = [mock_choice]
        mock_msg.usage.prompt_tokens = 10
        mock_msg.usage.completion_tokens = 20
        mock_msg.usage.total_tokens = 30

        mock_client = MagicMock()
        mock_client.chat.complete_async = AsyncMock(return_value=mock_msg)
        adapter._client = mock_client

        from specweaver.infrastructure.llm.models import ToolDefinition

        config = GenerationConfig(
            model="mistral-large-latest", tools=[ToolDefinition(name="test", description="desc")]
        )

        mock_exec = AsyncMock()
        result = await adapter.generate_with_tools([], config, mock_exec)

        assert result.text == "No tools used here"
        mock_exec.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_with_tools_max_rounds(self) -> None:
        adapter = MistralAdapter(api_key="key")

        mock_tc = MagicMock()
        mock_tc.id = "call_123"
        mock_tc.function.name = "my_tool"
        mock_tc.function.arguments = "{}"

        mock_choice = MagicMock()
        mock_choice.message.content = ""
        mock_choice.message.tool_calls = [mock_tc]
        mock_choice.finish_reason = "tool_calls"

        mock_msg = MagicMock()
        mock_msg.choices = [mock_choice]
        mock_msg.usage.prompt_tokens = 10
        mock_msg.usage.completion_tokens = 20
        mock_msg.usage.total_tokens = 30

        mock_client = MagicMock()
        mock_client.chat.complete_async = AsyncMock(return_value=mock_msg)
        adapter._client = mock_client

        from specweaver.infrastructure.llm.models import ToolDefinition

        config = GenerationConfig(
            model="mistral-large-latest",
            tools=[ToolDefinition(name="my_tool", description="desc")],
            max_tool_rounds=2,
        )

        mock_exec = AsyncMock()
        mock_exec.execute.return_value = {"success": True}

        result = await adapter.generate_with_tools([], config, mock_exec)

        assert result.text == "Max tool rounds exceeded."
        assert result.finish_reason == "max_tokens"
        assert mock_exec.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_with_tools_json_error(self) -> None:
        adapter = MistralAdapter(api_key="key")

        mock_tc_bad = MagicMock()
        mock_tc_bad.id = "call_bad"
        mock_tc_bad.function.name = "my_tool"
        mock_tc_bad.function.arguments = "{ invalid json"

        mock_choice_1 = MagicMock()
        mock_choice_1.message.content = ""
        mock_choice_1.message.tool_calls = [mock_tc_bad]
        mock_choice_1.finish_reason = "tool_calls"
        mock_msg_1 = MagicMock()
        mock_msg_1.choices = [mock_choice_1]
        mock_msg_1.usage.prompt_tokens = 10

        mock_choice_2 = MagicMock()
        mock_choice_2.message.content = "Success"
        mock_choice_2.message.tool_calls = None
        mock_choice_2.finish_reason = "stop"
        mock_msg_2 = MagicMock()
        mock_msg_2.choices = [mock_choice_2]
        mock_msg_2.usage.prompt_tokens = 10

        mock_client = MagicMock()
        mock_client.chat.complete_async = AsyncMock(side_effect=[mock_msg_1, mock_msg_2])
        adapter._client = mock_client

        from specweaver.infrastructure.llm.models import ToolDefinition

        config = GenerationConfig(
            model="mistral-large-latest", tools=[ToolDefinition(name="my_tool", description="desc")]
        )

        mock_exec = AsyncMock()
        mock_exec.execute.return_value = "fixed"

        result = await adapter.generate_with_tools([], config, mock_exec)

        mock_exec.execute.assert_called_once_with("my_tool", {})
        assert result.text == "Success"
