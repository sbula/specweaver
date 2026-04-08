# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests for ToolDispatcher boundary with all adapters."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from specweaver.llm.adapters.anthropic import AnthropicAdapter
from specweaver.llm.adapters.mistral import MistralAdapter
from specweaver.llm.adapters.openai import OpenAIAdapter
from specweaver.llm.adapters.qwen import QwenAdapter
from specweaver.llm.models import GenerationConfig, ToolDefinition
from specweaver.loom.dispatcher import ToolDispatcher


class DummyInterface:
    """A dummy tool interface for integration testing."""

    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="my_test_tool",
                description="A test tool",
            )
        ]

    def my_test_tool(self) -> dict[str, str]:
        return {"result": "hello world"}


@pytest.mark.asyncio
async def test_openai_dispatcher_integration() -> None:
    dispatcher = ToolDispatcher([DummyInterface()])
    adapter = OpenAIAdapter(api_key="test")

    mock_tc = MagicMock()
    mock_tc.id = "call_1"
    mock_tc.function.name = "my_test_tool"
    mock_tc.function.arguments = "{}"

    mock_choice_1 = MagicMock()
    mock_choice_1.message.content = ""
    mock_choice_1.message.tool_calls = [mock_tc]
    mock_choice_1.finish_reason = "tool_calls"
    mock_response_1 = MagicMock()
    mock_response_1.choices = [mock_choice_1]
    mock_response_1.usage = None

    mock_choice_2 = MagicMock()
    mock_choice_2.message.content = "Integration success"
    mock_choice_2.message.tool_calls = None
    mock_choice_2.finish_reason = "stop"
    mock_response_2 = MagicMock()
    mock_response_2.choices = [mock_choice_2]
    mock_response_2.usage = None

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=[mock_response_1, mock_response_2])
    adapter._client = mock_client

    config = GenerationConfig(model="gpt-4o", tools=dispatcher.available_tools())

    result = await adapter.generate_with_tools([], config, dispatcher)

    assert result.text == "Integration success"


@pytest.mark.asyncio
async def test_anthropic_dispatcher_integration() -> None:
    dispatcher = ToolDispatcher([DummyInterface()])
    adapter = AnthropicAdapter(api_key="test")

    mock_tool_use = MagicMock(type="tool_use", id="t1")
    mock_tool_use.name = "my_test_tool"
    mock_tool_use.input = {}

    mock_msg_1 = MagicMock()
    mock_msg_1.content = [mock_tool_use]
    mock_msg_1.stop_reason = "tool_use"
    mock_msg_1.usage.input_tokens = 10
    mock_msg_1.usage.output_tokens = 20

    mock_msg_2 = MagicMock()
    mock_msg_2.content = [MagicMock(type="text", text="Integration success")]
    mock_msg_2.stop_reason = "end_turn"
    mock_msg_2.usage.input_tokens = 10
    mock_msg_2.usage.output_tokens = 20

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[mock_msg_1, mock_msg_2])
    adapter._client = mock_client

    config = GenerationConfig(model="claude-4-6-sonnet", tools=dispatcher.available_tools())

    result = await adapter.generate_with_tools([], config, dispatcher)

    assert result.text == "Integration success"


@pytest.mark.asyncio
async def test_mistral_dispatcher_integration() -> None:
    dispatcher = ToolDispatcher([DummyInterface()])
    adapter = MistralAdapter(api_key="test")

    mock_tc = MagicMock()
    mock_tc.id = "call_1"
    mock_tc.function.name = "my_test_tool"
    mock_tc.function.arguments = "{}"

    mock_choice_1 = MagicMock()
    mock_choice_1.message.content = ""
    mock_choice_1.message.tool_calls = [mock_tc]
    mock_choice_1.finish_reason = "tool_calls"
    mock_msg_1 = MagicMock()
    mock_msg_1.choices = [mock_choice_1]
    mock_msg_1.usage.prompt_tokens = 10

    mock_choice_2 = MagicMock()
    mock_choice_2.message.content = "Integration success"
    mock_choice_2.message.tool_calls = None
    mock_choice_2.finish_reason = "stop"
    mock_msg_2 = MagicMock()
    mock_msg_2.choices = [mock_choice_2]
    mock_msg_2.usage.prompt_tokens = 10

    mock_client = MagicMock()
    mock_client.chat.complete_async = AsyncMock(side_effect=[mock_msg_1, mock_msg_2])
    adapter._client = mock_client

    config = GenerationConfig(model="mistral-large-latest", tools=dispatcher.available_tools())

    result = await adapter.generate_with_tools([], config, dispatcher)

    assert result.text == "Integration success"


@pytest.mark.asyncio
async def test_qwen_dispatcher_integration() -> None:
    dispatcher = ToolDispatcher([DummyInterface()])
    adapter = QwenAdapter(api_key="test")

    mock_tc = MagicMock()
    mock_tc.id = "call_1"
    mock_tc.function.name = "my_test_tool"
    mock_tc.function.arguments = "{}"

    mock_choice_1 = MagicMock()
    mock_choice_1.message.content = ""
    mock_choice_1.message.tool_calls = [mock_tc]
    mock_choice_1.finish_reason = "tool_calls"
    mock_response_1 = MagicMock()
    mock_response_1.choices = [mock_choice_1]
    mock_response_1.usage = None

    mock_choice_2 = MagicMock()
    mock_choice_2.message.content = "Integration success"
    mock_choice_2.message.tool_calls = None
    mock_choice_2.finish_reason = "stop"
    mock_response_2 = MagicMock()
    mock_response_2.choices = [mock_choice_2]
    mock_response_2.usage = None

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=[mock_response_1, mock_response_2])
    adapter._client = mock_client

    config = GenerationConfig(model="qwen3-max", tools=dispatcher.available_tools())

    result = await adapter.generate_with_tools([], config, dispatcher)

    assert result.text == "Integration success"
