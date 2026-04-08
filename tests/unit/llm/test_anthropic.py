# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from specweaver.llm.adapters.anthropic import AnthropicAdapter
from specweaver.llm.models import GenerationConfig, Message, Role


class TestAnthropicAdapter:
    def test_provider_metadata(self) -> None:
        adapter = AnthropicAdapter(api_key="test")
        assert adapter.provider_name == "anthropic"
        assert adapter.api_key_env_var == "ANTHROPIC_API_KEY"
        assert "claude-4-6-sonnet" in AnthropicAdapter.default_costs

    def test_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
        assert AnthropicAdapter().available() is True
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert AnthropicAdapter(api_key="").available() is False

    @pytest.mark.asyncio
    async def test_generate_delegates(self) -> None:
        adapter = AnthropicAdapter(api_key="test-key")

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(type="text", text="Hello from Claude")]
        mock_msg.stop_reason = "end_turn"
        mock_msg.usage.input_tokens = 10
        mock_msg.usage.output_tokens = 20

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_msg)
        adapter._client = mock_client

        config = GenerationConfig(model="claude-3-7-sonnet-20250219")
        messages = [Message(role=Role.USER, content="Hello")]

        result = await adapter.generate(messages, config)

        assert result.text == "Hello from Claude"
        assert result.usage.prompt_tokens == 10
        assert result.usage.completion_tokens == 20
        assert result.usage.total_tokens == 30
        assert result.finish_reason == "stop"

        mock_client.messages.create.assert_called_once()
        kwargs = mock_client.messages.create.call_args.kwargs
        assert kwargs["model"] == "claude-3-7-sonnet-20250219"
        assert kwargs["messages"] == [{"role": "user", "content": "Hello"}]

    @pytest.mark.asyncio
    async def test_generate_with_tools_no_calls(self) -> None:
        adapter = AnthropicAdapter(api_key="key")

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(type="text", text="No tools used here")]
        mock_msg.stop_reason = "end_turn"
        mock_msg.usage.input_tokens = 10
        mock_msg.usage.output_tokens = 20

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_msg)
        adapter._client = mock_client

        from specweaver.llm.models import ToolDefinition

        config = GenerationConfig(
            model="claude-3-7-sonnet-20250219",
            tools=[ToolDefinition(name="test", description="desc")],
        )

        mock_exec = AsyncMock()
        result = await adapter.generate_with_tools([], config, mock_exec)

        assert result.text == "No tools used here"
        mock_exec.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_with_tools_max_rounds(self) -> None:
        adapter = AnthropicAdapter(api_key="key")

        mock_tool_use = MagicMock(type="tool_use", id="t1")
        mock_tool_use.name = "my_tool"
        mock_tool_use.input = {}

        mock_msg = MagicMock()
        mock_msg.content = [mock_tool_use]
        mock_msg.stop_reason = "tool_use"
        mock_msg.usage.input_tokens = 10
        mock_msg.usage.output_tokens = 20

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_msg)
        adapter._client = mock_client

        from specweaver.llm.models import ToolDefinition

        config = GenerationConfig(
            model="claude-4-6-sonnet",
            tools=[ToolDefinition(name="my_tool", description="desc")],
            max_tool_rounds=2,
        )

        mock_exec = AsyncMock()
        mock_exec.execute.return_value = "fixed"

        result = await adapter.generate_with_tools([], config, mock_exec)

        assert result.text == "Max tool rounds exceeded."
        assert result.finish_reason == "max_tokens"
        assert mock_exec.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_with_tools_json_error(self) -> None:
        adapter = AnthropicAdapter(api_key="key")

        class BadBlock:
            type = "tool_use"
            id = "t1"
            name = "my_tool"

            @property
            def input(self) -> dict:  # type: ignore
                raise ValueError("Bad json")

        mock_msg_1 = MagicMock()
        mock_msg_1.content = [BadBlock()]
        mock_msg_1.stop_reason = "tool_use"
        mock_msg_1.usage.input_tokens = 10
        mock_msg_1.usage.output_tokens = 20

        mock_msg_2 = MagicMock()
        mock_msg_2.content = [MagicMock(type="text", text="Success")]
        mock_msg_2.stop_reason = "end_turn"
        mock_msg_2.usage.input_tokens = 10
        mock_msg_2.usage.output_tokens = 20

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=[mock_msg_1, mock_msg_2])
        adapter._client = mock_client

        from specweaver.llm.models import ToolDefinition

        config = GenerationConfig(
            model="claude-4-6-sonnet", tools=[ToolDefinition(name="my_tool", description="desc")]
        )

        mock_exec = AsyncMock()
        mock_exec.execute.return_value = "fixed"

        result = await adapter.generate_with_tools([], config, mock_exec)

        mock_exec.execute.assert_called_once_with("my_tool", {})
        assert result.text == "Success"
