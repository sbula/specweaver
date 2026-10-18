# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

import anthropic

from specweaver.infrastructure.llm.adapters.base import LLMAdapter
from specweaver.infrastructure.llm.errors import (
    AuthenticationError,
    GenerationError,
    ModelNotFoundError,
    RateLimitError,
    ToolRoundsExceededError,
    attach_usage,
)
from specweaver.infrastructure.llm.models import (
    TokenUsage,
    count_or_unknown,
    payload_chars,
    tool_rounds,
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


#: Automatic caching: one breakpoint that moves to the end of each request, so every tool round
#: reads the rounds before it from the cache. No `ttl`: the 5-minute lifetime.
AUTOMATIC_CACHE: dict[str, str] = {"type": "ephemeral"}


def _usage_of(usage: Any) -> TokenUsage:
    """One response's token counts.

    Anthropic reports no total, and its `input_tokens` leaves out the cached part: what was read
    from and written to the cache is added back, so the prompt total is the whole prompt.
    """
    if not usage:
        return TokenUsage()
    read = count_or_unknown(getattr(usage, "cache_read_input_tokens", None))
    write = count_or_unknown(getattr(usage, "cache_creation_input_tokens", None))
    prompt = usage.input_tokens + (read or 0) + (write or 0)
    return TokenUsage(
        prompt_tokens=prompt,
        completion_tokens=usage.output_tokens,
        total_tokens=prompt + usage.output_tokens,
        cached_read_tokens=read,
        cache_write_tokens=write,
    )


def _finish_reason(response: Any) -> str:
    """`max_tokens` when the model was cut off, `stop` otherwise."""
    return "max_tokens" if getattr(response, "stop_reason", None) == "max_tokens" else "stop"


class AnthropicAdapter(LLMAdapter):
    """Adapter for Anthropic Claude models."""

    provider_name = "anthropic"

    default_base_url: ClassVar[str | None] = "https://api.anthropic.com"

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key, base_url=self._base_url)
        return self._client

    def _handle_error(self, e: Exception) -> None:
        import anthropic

        if isinstance(e, anthropic.AuthenticationError):
            logger.error("AnthropicAdapter: authentication failed - check ANTHROPIC_API_KEY")
            raise AuthenticationError(str(e)) from e
        elif isinstance(e, anthropic.RateLimitError):
            logger.warning("AnthropicAdapter: rate limit / quota exceeded")
            raise RateLimitError(str(e)) from e
        elif isinstance(e, anthropic.NotFoundError):
            logger.error("AnthropicAdapter: model not found")
            raise ModelNotFoundError(str(e)) from e
        logger.error("AnthropicAdapter: unclassified generation error - %s", e)
        raise GenerationError(str(e)) from e

    def _convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        anthropic_messages: list[dict[str, Any]] = []
        for msg in messages:
            # Anthropic only accepts "user" or "assistant" inside the messages array
            role = "assistant" if str(msg.role.value) == "assistant" else "user"
            anthropic_messages.append({"role": role, "content": msg.content})
        return anthropic_messages

    async def generate(self, messages: list[Message], config: GenerationConfig) -> LLMResponse:
        from specweaver.infrastructure.llm.models import LLMResponse

        client = self._get_client()
        anthropic_messages = self._convert_messages(messages)
        logger.debug(
            "AnthropicAdapter.generate: model=%s, messages=%d", config.model, len(messages)
        )

        # No sampling values: current Claude models refuse them with a 400, and anthropic 1.x
        # does not accept them at all.
        kwargs: dict[str, Any] = {
            "model": config.model,
            "messages": anthropic_messages,
            "max_tokens": config.max_output_tokens,
            "cache_control": AUTOMATIC_CACHE,
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

        usage = _usage_of(getattr(response, "usage", None))

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
        from specweaver.commons import json

        # Anthropic requires the assistant's content block and the tool_result in the subsequent user block
        anthropic_messages.append({"role": "assistant", "content": assistant_content})

        tool_results_content = []

        for block in tool_blocks:
            try:
                args = block.input
            except Exception:
                logger.warning(
                    "AnthropicAdapter: failed to parse tool arguments for %s", block.name
                )
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
        before_request: Callable[[int, int], None] | None = None,
    ) -> LLMResponse:
        from specweaver.infrastructure.llm.models import LLMResponse, TokenUsage

        if not config.tools:
            return await self.generate(messages, config)

        client = self._get_client()
        anthropic_messages = self._convert_messages(messages)

        kwargs: dict[str, Any] = {
            "model": config.model,
            "messages": anthropic_messages,
            "max_tokens": config.max_output_tokens,
            "tools": self._to_anthropic_tools(config.tools),
            "cache_control": AUTOMATIC_CACHE,
        }

        if config.system_instruction:
            kwargs["system"] = config.system_instruction

        cumulative_usage = TokenUsage()

        try:
            for round_num in tool_rounds(config):
                if on_tool_round:
                    self._apply_on_tool_round(
                        messages, anthropic_messages, round_num, on_tool_round
                    )

                if before_request:
                    before_request(round_num, payload_chars(kwargs))
                try:
                    response = await client.messages.create(**kwargs)
                except Exception as e:
                    self._handle_error(e)

                cumulative_usage = cumulative_usage + _usage_of(getattr(response, "usage", None))

                # Anthropic signals tool use via stop_reason, not a tool_calls field.
                if getattr(response, "stop_reason", None) != "tool_use":
                    return LLMResponse(
                        text=self._extract_text(response.content),
                        model=config.model,
                        usage=cumulative_usage,
                        finish_reason=_finish_reason(response),
                    )

                # Isolate tool_use blocks and text blocks
                tool_blocks = [b for b in response.content if getattr(b, "type", "") == "tool_use"]

                # The API requires us to supply exactly the assistant content format that was returned
                # Anthropic SDK message content blocks can just be appended as-is
                await self._execute_anthropic_tools(
                    tool_blocks, tool_executor, anthropic_messages, response.content
                )

            raise ToolRoundsExceededError.reached(config.max_tool_rounds)
        except BaseException as exc:
            attach_usage(exc, cumulative_usage)
            raise

    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    async def count_tokens(self, text: str, model: str) -> int:
        return len(text) // 4
