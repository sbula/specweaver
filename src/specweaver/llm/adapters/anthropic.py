# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, ClassVar

from specweaver.llm.adapters.base import LLMAdapter
from specweaver.llm.errors import (
    AuthenticationError,
    GenerationError,
    ModelNotFoundError,
    RateLimitError,
)
from specweaver.llm.telemetry import CostEntry

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from specweaver.llm.models import (
        GenerationConfig,
        LLMResponse,
        Message,
        ToolDefinition,
    )


class AnthropicAdapter(LLMAdapter):
    """Adapter for Anthropic Claude models."""

    provider_name = "anthropic"
    api_key_env_var = "ANTHROPIC_API_KEY"
    default_costs: ClassVar[dict[str, CostEntry]] = {
        "claude-4-6-sonnet": CostEntry(0.00300, 0.01500),
        "claude-4-6-opus": CostEntry(0.01500, 0.07500),
        "claude-3-7-sonnet-20250219": CostEntry(0.00300, 0.01500),
    }

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the Anthropic adapter."""
        super().__init__()
        self._api_key = api_key or os.environ.get(self.api_key_env_var, "")
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic  # type: ignore

            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        return self._client

    def available(self) -> bool:
        return bool(self._api_key)

    def _handle_error(self, e: Exception) -> None:
        import anthropic

        if isinstance(e, anthropic.AuthenticationError):
            raise AuthenticationError(str(e)) from e
        elif isinstance(e, anthropic.RateLimitError):
            raise RateLimitError(str(e)) from e
        elif isinstance(e, anthropic.NotFoundError):
            raise ModelNotFoundError(str(e)) from e
        raise GenerationError(str(e)) from e

    def _convert_messages(
        self, messages: list[Message]
    ) -> list[dict[str, Any]]:
        anthropic_messages: list[dict[str, Any]] = []
        for msg in messages:
            # Anthropic only accepts "user" or "assistant" inside the messages array
            role = "assistant" if str(msg.role.value) == "assistant" else "user"
            anthropic_messages.append({"role": role, "content": msg.content})
        return anthropic_messages

    async def generate(
        self, messages: list[Message], config: GenerationConfig
    ) -> LLMResponse:
        from specweaver.llm.models import LLMResponse, TokenUsage

        client = self._get_client()
        anthropic_messages = self._convert_messages(messages)

        kwargs: dict[str, Any] = {
            "model": config.model,
            "messages": anthropic_messages,
            "temperature": config.temperature,
            "max_tokens": config.max_output_tokens,
        }

        if config.system_instruction:
            kwargs["system"] = config.system_instruction

        try:
            response = await client.messages.create(**kwargs)
        except Exception as e:
            self._handle_error(e)

        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        usage = TokenUsage()
        if hasattr(response, "usage") and response.usage:
            usage.prompt_tokens = response.usage.input_tokens
            usage.completion_tokens = response.usage.output_tokens
            usage.total_tokens = usage.prompt_tokens + usage.completion_tokens

        finish_reason = "stop"
        if getattr(response, "stop_reason", None) == "max_tokens":
            finish_reason = "max_tokens"

        return LLMResponse(
            text=text,
            model=config.model,
            usage=usage,
            finish_reason=finish_reason,
        )

    async def generate_stream(
        self, messages: list[Message], config: GenerationConfig
    ) -> AsyncIterator[str]:
        raise NotImplementedError
        yield ""

    def _to_anthropic_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.to_json_schema(),
            }
            for t in tools
        ]

    async def _execute_anthropic_tools(
        self,
        tool_blocks: list[Any],
        tool_executor: object,
        anthropic_messages: list[dict[str, Any]],
        assistant_content: list[Any],
    ) -> None:
        import json

        # Anthropic requires the assistant's content block and the tool_result in the subsequent user block
        anthropic_messages.append({"role": "assistant", "content": assistant_content})

        tool_results_content = []

        for block in tool_blocks:
            try:
                args = block.input
            except Exception:
                args = {}

            result = await tool_executor.execute(block.name, args)  # type: ignore

            tool_results_content.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                }
            )

        anthropic_messages.append({"role": "user", "content": tool_results_content})

    def _extract_text(self, content_blocks: list[Any]) -> str:
        text = ""
        for block in content_blocks:
             if getattr(block, "type", "text") == "text" and hasattr(block, "text"):
                 text += block.text
        return text

    def _apply_on_tool_round(
        self,
        messages: list[Message],
        anthropic_messages: list[dict[str, Any]],
        round_num: int,
        on_tool_round: Callable[[int, list[Message]], None],
    ) -> None:
        old_len = len(messages)
        on_tool_round(round_num, messages)
        for new_msg in messages[old_len:]:
            if str(new_msg.role.value) != "system":
                role = "assistant" if str(new_msg.role.value) == "assistant" else "user"
                anthropic_messages.append({"role": role, "content": new_msg.content})

    async def generate_with_tools(
        self,
        messages: list[Message],
        config: GenerationConfig,
        tool_executor: object,
        on_tool_round: Callable[[int, list[Message]], None] | None = None,
    ) -> LLMResponse:
        from specweaver.llm.models import LLMResponse, TokenUsage

        if not config.tools:
            return await self.generate(messages, config)

        client = self._get_client()
        anthropic_messages = self._convert_messages(messages)

        kwargs: dict[str, Any] = {
            "model": config.model,
            "messages": anthropic_messages,
            "temperature": config.temperature,
            "max_tokens": config.max_output_tokens,
            "tools": self._to_anthropic_tools(config.tools),
        }

        if config.system_instruction:
            kwargs["system"] = config.system_instruction

        cumulative_usage = TokenUsage()

        for round_num in range(config.max_tool_rounds):
            if on_tool_round:
                self._apply_on_tool_round(messages, anthropic_messages, round_num, on_tool_round)

            try:
                response = await client.messages.create(**kwargs)
            except Exception as e:
                 self._handle_error(e)

            if hasattr(response, "usage") and response.usage:
                cumulative_usage.prompt_tokens += response.usage.input_tokens
                cumulative_usage.completion_tokens += response.usage.output_tokens
                cumulative_usage.total_tokens += response.usage.input_tokens + response.usage.output_tokens

            # Anthropic tool use works via stop_reason == "tool_use"
            if getattr(response, "stop_reason", None) != "tool_use":
                text = self._extract_text(response.content)
                finish_reason = "stop"
                if getattr(response, "stop_reason", None) == "max_tokens":
                    finish_reason = "max_tokens"

                return LLMResponse(
                    text=text,
                    model=config.model,
                    usage=cumulative_usage,
                    finish_reason=finish_reason,
                )

            # Isolate tool_use blocks and text blocks
            tool_blocks = [b for b in response.content if getattr(b, "type", "") == "tool_use"]

            # The API requires us to supply exactly the assistant content format that was returned
            # Anthropic SDK message content blocks can just be appended as-is
            await self._execute_anthropic_tools(tool_blocks, tool_executor, anthropic_messages, response.content)

        return LLMResponse(
            text="Max tool rounds exceeded.",
            model=config.model,
            usage=cumulative_usage,
            finish_reason="max_tokens",
        )

    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    async def count_tokens(self, text: str, model: str) -> int:
        return len(text) // 4
