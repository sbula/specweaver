# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("openai")

from specweaver.infrastructure.llm.adapters.openai import OpenAIAdapter
from specweaver.infrastructure.llm.errors import AuthenticationError
from specweaver.infrastructure.llm.models import GenerationConfig, Message, Role


class TestOpenAIAdapter:
    def test_provider_metadata(self) -> None:
        adapter = OpenAIAdapter(api_key="test-key")
        assert adapter.provider_name == "openai"

    def test_available_with_key(self) -> None:
        adapter = OpenAIAdapter(api_key="test")
        assert adapter.available() is True

    def test_available_without_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        adapter = OpenAIAdapter(api_key="")
        assert adapter.available() is False

    @pytest.mark.asyncio
    async def test_generate_delegates_to_client(self) -> None:
        adapter = OpenAIAdapter(api_key="test")

        # We need a proper mock testing the openai structure
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello from OpenAI"
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 20
        mock_usage.total_tokens = 30

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        config = GenerationConfig(model="gpt-4o", max_output_tokens=1000)
        messages = [Message(role=Role.USER, content="Hello")]

        result = await adapter.generate(messages, config)

        assert result.text == "Hello from OpenAI"
        assert result.usage.total_tokens == 30
        assert result.finish_reason == "stop"

        # Check what was passed to client
        mock_client.chat.completions.create.assert_called_once()
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert kwargs["model"] == "gpt-4o"
        assert kwargs["messages"] == [{"role": "user", "content": "Hello"}]

    @pytest.mark.asyncio
    async def test_generate_auth_error(self) -> None:
        pytest.importorskip("openai")
        from openai import AuthenticationError as SDKAuthError

        adapter = OpenAIAdapter(api_key="bad")
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=SDKAuthError(message="bad key", response=MagicMock(), body=None)
        )
        adapter._client = mock_client

        config = GenerationConfig(model="gpt-4o", max_output_tokens=1000)
        messages = [Message(role=Role.USER, content="hi")]

        with pytest.raises(AuthenticationError):
            await adapter.generate(messages, config)

    @pytest.mark.asyncio
    async def test_generate_with_tools_no_calls(self) -> None:
        adapter = OpenAIAdapter(api_key="key")

        mock_choice = MagicMock()
        mock_choice.message.content = "I didn't use tools"
        mock_choice.finish_reason = "stop"
        mock_choice.message.tool_calls = None

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        from specweaver.infrastructure.llm.models import ToolDefinition

        config = GenerationConfig(
            model="gpt-4o",
            tools=[ToolDefinition(name="test", description="desc")],
            max_tool_rounds=3,
            max_output_tokens=1000,
        )

        mock_exec = AsyncMock()
        result = await adapter.generate_with_tools([], config, mock_exec)

        assert result.text == "I didn't use tools"
        mock_exec.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_with_tools_max_rounds(self) -> None:
        adapter = OpenAIAdapter(api_key="key")

        mock_tc = MagicMock()
        mock_tc.id = "call_123"
        mock_tc.function.name = "my_tool"
        mock_tc.function.arguments = "{}"

        mock_choice = MagicMock()
        mock_choice.message.content = ""
        mock_choice.message.tool_calls = [mock_tc]
        mock_choice.finish_reason = "tool_calls"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        from specweaver.infrastructure.llm.models import ToolDefinition

        config = GenerationConfig(
            model="gpt-5.4",
            tools=[ToolDefinition(name="my_tool", description="desc")],
            max_tool_rounds=2,
            max_output_tokens=1000,
        )

        mock_exec = AsyncMock()
        mock_exec.execute.return_value = {"success": True}

        from specweaver.infrastructure.llm.errors import ToolRoundsExceededError

        with pytest.raises(ToolRoundsExceededError, match=r"brake\.agent_turns") as caught:
            await adapter.generate_with_tools([], config, mock_exec)
        assert caught.value.usage.total_tokens >= 0  # the rounds' usage goes to the brake

        # It should loop exactly 2 times and call execute twice
        assert mock_exec.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_each_round_reports_the_payload_it_is_about_to_send(self) -> None:
        from specweaver.infrastructure.llm.models import Message, Role, ToolDefinition

        adapter = OpenAIAdapter(api_key="key")
        call = MagicMock()
        call.id = "c1"
        call.function.name = "my_tool"
        call.function.arguments = "{}"
        asks = MagicMock(choices=[MagicMock(finish_reason="tool_calls")], usage=None)
        asks.choices[0].message.content = ""
        asks.choices[0].message.tool_calls = [call]
        done = MagicMock(choices=[MagicMock(finish_reason="stop")], usage=None)
        done.choices[0].message.content = "fine"
        done.choices[0].message.tool_calls = None
        adapter._client = MagicMock()
        adapter._client.chat.completions.create = AsyncMock(side_effect=[asks, done])
        config = GenerationConfig(
            model="gpt-5.4",
            tools=[ToolDefinition(name="my_tool", description="d" * 8000)],
            max_tool_rounds=5,
            max_output_tokens=1000,
        )
        executor = AsyncMock()
        executor.execute.return_value = {"content": "x" * 5000}
        seen: list[tuple[int, int]] = []

        await adapter.generate_with_tools(
            [Message(role=Role.USER, content="hi")],
            config,
            executor,
            before_request=lambda round_num, chars: seen.append((round_num, chars)),
        )

        assert [r for r, _ in seen] == [0, 1]
        assert seen[1][1] > seen[0][1] + 5000  # the tool result is in round 1's payload
        assert all(chars > 8000 for _, chars in seen)  # the tool schemas are in every round

    @pytest.mark.asyncio
    async def test_a_tool_loop_that_fails_partway_keeps_the_usage_of_the_rounds_it_ran(
        self,
    ) -> None:
        from specweaver.infrastructure.llm.models import ToolDefinition

        adapter = OpenAIAdapter(api_key="key")
        call = MagicMock()
        call.id = "c1"
        call.function.name = "my_tool"
        call.function.arguments = "{}"
        first = MagicMock()
        first.choices = [MagicMock(finish_reason="tool_calls")]
        first.choices[0].message.content = ""
        first.choices[0].message.tool_calls = [call]
        first.usage = MagicMock(prompt_tokens=40, completion_tokens=10, total_tokens=50)
        adapter._client = MagicMock()
        adapter._client.chat.completions.create = AsyncMock(
            side_effect=[first, RuntimeError("provider down")]
        )
        config = GenerationConfig(
            model="gpt-5.4",
            tools=[ToolDefinition(name="my_tool", description="desc")],
            max_tool_rounds=5,
            max_output_tokens=1000,
        )
        executor = AsyncMock()
        executor.execute.return_value = {"ok": True}

        with pytest.raises(Exception) as caught:
            await adapter.generate_with_tools([], config, executor)

        assert caught.value.usage.total_tokens == 50

    @pytest.mark.asyncio
    async def test_a_tool_loop_without_a_round_limit_is_refused_before_any_call(self) -> None:
        from specweaver.infrastructure.llm.errors import ToolRoundsExceededError
        from specweaver.infrastructure.llm.models import ToolDefinition

        adapter = OpenAIAdapter(api_key="key")
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock()
        adapter._client = mock_client
        config = GenerationConfig(
            model="gpt-5.4",
            tools=[ToolDefinition(name="my_tool", description="desc")],
            max_output_tokens=1000,
        )

        with pytest.raises(ToolRoundsExceededError, match=r"brake\.agent_turns"):
            await adapter.generate_with_tools([], config, AsyncMock())
        mock_client.chat.completions.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_with_tools_json_error(self) -> None:
        adapter = OpenAIAdapter(api_key="key")

        mock_tc_bad = MagicMock()
        mock_tc_bad.id = "call_bad"
        mock_tc_bad.function.name = "my_tool"
        mock_tc_bad.function.arguments = "{ invalid json"

        mock_choice_1 = MagicMock()
        mock_choice_1.message.content = ""
        mock_choice_1.message.tool_calls = [mock_tc_bad]
        mock_choice_1.finish_reason = "tool_calls"
        mock_response_1 = MagicMock()
        mock_response_1.choices = [mock_choice_1]
        mock_response_1.usage = None

        mock_choice_2 = MagicMock()
        mock_choice_2.message.content = "Success"
        mock_choice_2.message.tool_calls = None
        mock_choice_2.finish_reason = "stop"
        mock_response_2 = MagicMock()
        mock_response_2.choices = [mock_choice_2]
        mock_response_2.usage = None

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=[mock_response_1, mock_response_2]
        )
        adapter._client = mock_client

        from specweaver.infrastructure.llm.models import ToolDefinition

        config = GenerationConfig(
            model="gpt-5.4",
            tools=[ToolDefinition(name="my_tool", description="desc")],
            max_tool_rounds=3,
            max_output_tokens=1000,
        )

        mock_exec = AsyncMock()
        mock_exec.execute.return_value = "fixed"

        result = await adapter.generate_with_tools([], config, mock_exec)

        mock_exec.execute.assert_called_once_with("my_tool", {})
        assert result.text == "Success"
