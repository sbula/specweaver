# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, ClassVar

from specweaver.infrastructure.llm.adapters.base import LLMAdapter
from specweaver.infrastructure.llm.errors import (
    AuthenticationError,
    GenerationError,
    ModelNotFoundError,
    RateLimitError,
)
from specweaver.infrastructure.llm.telemetry import CostEntry

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from specweaver.infrastructure.llm.models import (
        GenerationConfig,
        LLMResponse,
        Message,
        ToolDefinition,
    )


class MistralAdapter(LLMAdapter):
    """Adapter for Mistral models."""

    provider_name = "mistral"
    api_key_env_var = "MISTRAL_API_KEY"
    default_costs: ClassVar[dict[str, CostEntry]] = {
        "mistral-small-4": CostEntry(0.00020, 0.00060),
        "mistral-large-3": CostEntry(0.00200, 0.00600),
        "mistral-large-latest": CostEntry(0.00200, 0.00600),
        "mistral-small-latest": CostEntry(0.00020, 0.00060),
    }

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the Mistral adapter."""
        super().__init__()
        self._api_key = api_key or os.environ.get(self.api_key_env_var, "")
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from mistralai import Mistral  # type: ignore

            self._client = Mistral(api_key=self._api_key)
        return self._client

    def available(self) -> bool:
        return bool(self._api_key)

    def _handle_error(self, e: Exception) -> None:
        from mistralai.models import SDKError  # type: ignore

        if isinstance(e, SDKError):
            if e.status_code == 401:
                raise AuthenticationError(str(e)) from e
            elif e.status_code == 429:
                raise RateLimitError(str(e)) from e
            elif e.status_code == 404:
                raise ModelNotFoundError(str(e)) from e
        raise GenerationError(str(e)) from e

    async def generate(self, messages: list[Message], config: GenerationConfig) -> LLMResponse:
        from specweaver.infrastructure.llm.models import LLMResponse, TokenUsage

        client = self._get_client()
        logger.debug("MistralAdapter.generate: model=%s, messages=%d", config.model, len(messages))
        mistral_messages: list[dict[str, Any]] = []
        if config.system_instruction:
            mistral_messages.append({"role": "system", "content": config.system_instruction})
        for msg in messages:
            mistral_messages.append({"role": str(msg.role.value), "content": msg.content})

        kwargs: dict[str, Any] = {
            "model": config.model,
            "messages": mistral_messages,
            "temperature": config.temperature,
            "max_tokens": config.max_output_tokens,
        }

        try:
            response = await client.chat.complete_async(**kwargs)
        except Exception as e:
            self._handle_error(e)

        choice = response.choices[0]
        text = choice.message.content or ""

        usage = TokenUsage()
        if hasattr(response, "usage") and response.usage:
            usage.prompt_tokens = getattr(response.usage, "prompt_tokens", 0)
            usage.completion_tokens = getattr(response.usage, "completion_tokens", 0)
            usage.total_tokens = getattr(response.usage, "total_tokens", 0)

        return LLMResponse(
            text=text,
            model=config.model,
            usage=usage,
            finish_reason=getattr(choice, "finish_reason", "stop") or "stop",
        )

    async def generate_stream(
        self, messages: list[Message], config: GenerationConfig
    ) -> AsyncIterator[str]:
        raise NotImplementedError
        yield ""

    def _apply_on_tool_round(
        self,
        messages: list[Message],
        mistral_messages: list[dict[str, Any]],
        round_num: int,
        on_tool_round: Callable[[int, list[Message]], None],
    ) -> None:
        old_len = len(messages)
        on_tool_round(round_num, messages)
        for new_msg in messages[old_len:]:
            if str(new_msg.role.value) != "system":
                mistral_messages.append(
                    {"role": str(new_msg.role.value), "content": new_msg.content}
                )

    def _to_mistral_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
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

    async def _execute_mistral_tools(
        self,
        tool_calls: list[Any],
        tool_executor: object,
        mistral_messages: list[dict[str, Any]],
    ) -> None:
        import json

        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except Exception:
                args = {}

            result = await tool_executor.execute(tc.function.name, args)  # type: ignore
            mistral_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": getattr(tc, "id", ""),
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
        from specweaver.infrastructure.llm.models import LLMResponse, TokenUsage

        if not config.tools:
            return await self.generate(messages, config)

        client = self._get_client()
        mistral_messages: list[dict[str, Any]] = []
        if config.system_instruction:
            mistral_messages.append({"role": "system", "content": config.system_instruction})
        for msg in messages:
            mistral_messages.append({"role": str(msg.role.value), "content": msg.content})

        kwargs: dict[str, Any] = {
            "model": config.model,
            "messages": mistral_messages,
            "temperature": config.temperature,
            "max_tokens": config.max_output_tokens,
            "tools": self._to_mistral_tools(config.tools),
        }

        cumulative_usage = TokenUsage()

        for round_num in range(config.max_tool_rounds):
            if on_tool_round:
                self._apply_on_tool_round(messages, mistral_messages, round_num, on_tool_round)

            try:
                response = await client.chat.complete_async(**kwargs)
            except Exception as e:
                self._handle_error(e)

            if hasattr(response, "usage") and response.usage:
                cumulative_usage.prompt_tokens += getattr(response.usage, "prompt_tokens", 0)
                cumulative_usage.completion_tokens += getattr(
                    response.usage, "completion_tokens", 0
                )
                cumulative_usage.total_tokens += getattr(response.usage, "total_tokens", 0)

            choice = response.choices[0]
            msg = choice.message

            if not getattr(msg, "tool_calls", None):
                return LLMResponse(
                    text=msg.content or "",
                    model=config.model,
                    usage=cumulative_usage,
                    finish_reason=getattr(choice, "finish_reason", "stop") or "stop",
                )

            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": getattr(tc, "id", ""),
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
            mistral_messages.append(assistant_msg)

            await self._execute_mistral_tools(msg.tool_calls, tool_executor, mistral_messages)

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
