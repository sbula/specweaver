# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from specweaver.infrastructure.llm.adapters.base import LLMAdapter
from specweaver.infrastructure.llm.errors import (
    AuthenticationError,
    GenerationError,
    ModelNotFoundError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from specweaver.infrastructure.llm.models import (
        GenerationConfig,
        LLMResponse,
        Message,
        ToolDefinition,
    )


def _accumulate_usage(cumulative: Any, usage: Any) -> None:
    """Add one response's token counts to the running total.

    Every field is read defensively: Mistral's usage object has varied across SDK versions, and a
    missing count should not abort a run that otherwise succeeded.
    """
    if not usage:
        return
    cumulative.prompt_tokens += getattr(usage, "prompt_tokens", 0)
    cumulative.completion_tokens += getattr(usage, "completion_tokens", 0)
    cumulative.total_tokens += getattr(usage, "total_tokens", 0)


def _assistant_message(msg: Any) -> dict[str, Any]:
    """The assistant turn to echo back, carrying the tool calls the model asked for."""
    return {
        "role": "assistant",
        "content": msg.content or "",
        "tool_calls": [
            {
                "id": getattr(tc, "id", ""),
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ],
    }


def _request(messages: list[Message], config: GenerationConfig) -> dict[str, Any]:
    """The chat request both generation paths send; the tool path adds its tools."""
    mistral_messages: list[dict[str, Any]] = []
    if config.system_instruction:
        mistral_messages.append({"role": "system", "content": config.system_instruction})
    for msg in messages:
        mistral_messages.append({"role": str(msg.role.value), "content": msg.content})
    return {
        "model": config.model,
        "messages": mistral_messages,
        "max_tokens": config.max_output_tokens,
        **_sampling(config),
    }


def _sampling(config: GenerationConfig) -> dict[str, float]:
    """The sampling values that are set; Mistral has no `top_k`."""
    return {
        name: value
        for name in ("temperature", "top_p")
        if (value := getattr(config, name)) is not None
    }


class MistralAdapter(LLMAdapter):
    """Adapter for Mistral models."""

    provider_name = "mistral"
    api_key_env_var = "MISTRAL_API_KEY"

    default_base_url: ClassVar[str | None] = "https://api.mistral.ai"

    def _get_client(self) -> Any:
        if self._client is None:
            from mistralai.client import Mistral

            self._client = Mistral(api_key=self._api_key, server_url=self._base_url)
        return self._client

    def _handle_error(self, e: Exception) -> None:
        from mistralai.client.errors import SDKError

        if isinstance(e, SDKError):
            if e.status_code == 401:
                logger.error("MistralAdapter: authentication failed - check MISTRAL_API_KEY")
                raise AuthenticationError(str(e)) from e
            elif e.status_code == 429:
                logger.warning("MistralAdapter: rate limit / quota exceeded")
                raise RateLimitError(str(e)) from e
            elif e.status_code == 404:
                logger.error("MistralAdapter: model not found")
                raise ModelNotFoundError(str(e)) from e
        logger.error("MistralAdapter: unclassified generation error - %s", e)
        raise GenerationError(str(e)) from e

    async def generate(self, messages: list[Message], config: GenerationConfig) -> LLMResponse:
        from specweaver.infrastructure.llm.models import LLMResponse, TokenUsage

        client = self._get_client()
        logger.debug("MistralAdapter.generate: model=%s, messages=%d", config.model, len(messages))
        kwargs = _request(messages, config)

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
        from specweaver.commons import json

        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except Exception:
                logger.warning(
                    "MistralAdapter: failed to parse tool arguments for %s", tc.function.name
                )
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

        kwargs = _request(messages, config)
        kwargs["tools"] = self._to_mistral_tools(config.tools)
        mistral_messages = kwargs["messages"]
        client = self._get_client()

        cumulative_usage = TokenUsage()

        for round_num in range(config.max_tool_rounds):
            if on_tool_round:
                self._apply_on_tool_round(messages, mistral_messages, round_num, on_tool_round)

            try:
                response = await client.chat.complete_async(**kwargs)
            except Exception as e:
                self._handle_error(e)

            _accumulate_usage(cumulative_usage, getattr(response, "usage", None))

            choice = response.choices[0]
            msg = choice.message

            if not getattr(msg, "tool_calls", None):
                return LLMResponse(
                    text=msg.content or "",
                    model=config.model,
                    usage=cumulative_usage,
                    finish_reason=getattr(choice, "finish_reason", "stop") or "stop",
                )

            mistral_messages.append(_assistant_message(msg))

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
