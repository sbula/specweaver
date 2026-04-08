# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, ClassVar

from specweaver.llm.adapters.base import LLMAdapter
from specweaver.llm.errors import (
    AuthenticationError,
    ContentFilterError,
    GenerationError,
    ModelNotFoundError,
    RateLimitError,
)
from specweaver.llm.telemetry import CostEntry

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from specweaver.llm.models import (
        GenerationConfig,
        LLMResponse,
        Message,
        ToolDefinition,
    )


class OpenAIAdapter(LLMAdapter):
    """Adapter for OpenAI models."""

    provider_name = "openai"
    api_key_env_var = "OPENAI_API_KEY"
    default_costs: ClassVar[dict[str, CostEntry]] = {
        "gpt-5.4": CostEntry(0.00250, 0.01000),
        "gpt-5.4-mini": CostEntry(0.00015, 0.00060),
        "gpt-4o": CostEntry(0.00250, 0.01000),
    }

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the OpenAI adapter."""
        super().__init__()
        self._api_key = api_key or os.environ.get(self.api_key_env_var, "")
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            import openai  # type: ignore[import-not-found]

            self._client = openai.AsyncOpenAI(api_key=self._api_key)
        return self._client

    def available(self) -> bool:
        return bool(self._api_key)

    def _handle_error(self, e: Exception) -> None:
        import openai

        if isinstance(e, openai.AuthenticationError):
            raise AuthenticationError(str(e)) from e
        elif isinstance(e, openai.RateLimitError):
            raise RateLimitError(str(e)) from e
        elif isinstance(e, openai.NotFoundError):
            raise ModelNotFoundError(str(e)) from e
        elif isinstance(e, openai.BadRequestError) and "safety" in str(e).lower():
            raise ContentFilterError(str(e)) from e
        raise GenerationError(str(e)) from e

    def _convert_messages(
        self, messages: list[Message], config: GenerationConfig
    ) -> list[dict[str, Any]]:
        oai_messages: list[dict[str, Any]] = []
        if config.system_instruction:
            oai_messages.append({"role": "system", "content": config.system_instruction})
        for msg in messages:
            oai_messages.append({"role": str(msg.role.value), "content": msg.content})
        return oai_messages

    def _to_openai_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.to_json_schema(),
                },
            }
            for t in tools
        ]

    async def generate(self, messages: list[Message], config: GenerationConfig) -> LLMResponse:
        from specweaver.llm.models import LLMResponse, TokenUsage

        client = self._get_client()
        oai_messages = self._convert_messages(messages, config)
        logger.debug("OpenAIAdapter.generate: model=%s, messages=%d", config.model, len(messages))

        kwargs: dict[str, Any] = {
            "model": config.model,
            "messages": oai_messages,
            "temperature": config.temperature,
            "max_tokens": config.max_output_tokens,
        }

        if config.response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await client.chat.completions.create(**kwargs)
        except Exception as e:
            self._handle_error(e)

        choice = response.choices[0]
        text = choice.message.content or ""

        usage = TokenUsage()
        if response.usage:
            usage.prompt_tokens = response.usage.prompt_tokens
            usage.completion_tokens = response.usage.completion_tokens
            usage.total_tokens = response.usage.total_tokens

        return LLMResponse(
            text=text,
            model=config.model,
            usage=usage,
            finish_reason=choice.finish_reason or "stop",
        )

    async def generate_stream(
        self, messages: list[Message], config: GenerationConfig
    ) -> AsyncIterator[str]:
        raise NotImplementedError
        yield ""

    async def _execute_tool_calls(
        self,
        tool_calls: list[Any],
        tool_executor: object,
        oai_messages: list[dict[str, Any]],
    ) -> None:
        import json

        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except Exception:
                args = {}

            result = await tool_executor.execute(tc.function.name, args)  # type: ignore

            oai_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                }
            )

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
        oai_messages = self._convert_messages(messages, config)

        kwargs: dict[str, Any] = {
            "model": config.model,
            "messages": oai_messages,
            "temperature": config.temperature,
            "max_tokens": config.max_output_tokens,
            "tools": self._to_openai_tools(config.tools),
        }

        cumulative_usage = TokenUsage()

        for _total_calls, round_num in enumerate(range(config.max_tool_rounds)):
            if on_tool_round:
                old_len = len(messages)
                on_tool_round(round_num, messages)
                for new_msg in messages[old_len:]:
                    if str(new_msg.role.value) != "system":
                        oai_messages.append(
                            {"role": str(new_msg.role.value), "content": new_msg.content}
                        )

            try:
                response = await client.chat.completions.create(**kwargs)
            except Exception as e:
                self._handle_error(e)

            if response.usage:
                cumulative_usage.prompt_tokens += response.usage.prompt_tokens
                cumulative_usage.completion_tokens += response.usage.completion_tokens
                cumulative_usage.total_tokens += response.usage.total_tokens

            choice = response.choices[0]
            msg = choice.message

            if not msg.tool_calls:
                return LLMResponse(
                    text=msg.content or "",
                    model=config.model,
                    usage=cumulative_usage,
                    finish_reason=choice.finish_reason or "stop",
                )

            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
            oai_messages.append(assistant_msg)

            await self._execute_tool_calls(msg.tool_calls, tool_executor, oai_messages)

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
