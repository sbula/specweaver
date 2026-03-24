# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Gemini adapter — concrete LLMAdapter for Google's Gemini API.

Uses the `google-genai` SDK (GA since May 2025).
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from google import genai
from google.genai import types

from specweaver.llm.adapters.base import LLMAdapter
from specweaver.llm.errors import (
    AuthenticationError,
    ContentFilterError,
    GenerationError,
    ModelNotFoundError,
    RateLimitError,
)
from specweaver.llm.models import (
    GenerationConfig,
    LLMResponse,
    Message,
    Role,
    TokenUsage,
    ToolCall,
    ToolDefinition,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


def _messages_to_gemini(
    messages: list[Message],
) -> tuple[str | None, list[types.Content]]:
    """Convert Message list to Gemini's format.

    Extracts system instruction (if present) and converts
    remaining messages to Gemini Content objects.

    Returns:
        Tuple of (system_instruction, contents).
    """
    system_instruction: str | None = None
    contents: list[types.Content] = []

    for msg in messages:
        if msg.role == Role.SYSTEM:
            system_instruction = msg.content
        else:
            role = "user" if msg.role == Role.USER else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg.content)],
                )
            )

    return system_instruction, contents


class GeminiAdapter(LLMAdapter):
    """Google Gemini LLM adapter.

    Requires GEMINI_API_KEY environment variable or explicit api_key.
    """

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the Gemini adapter.

        Args:
            api_key: Gemini API key. If None, reads from GEMINI_API_KEY env var.
        """
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self._client: genai.Client | None = None

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _get_client(self) -> genai.Client:
        """Lazy-initialize the Gemini client."""
        if self._client is None:
            if not self._api_key:
                msg = "GEMINI_API_KEY is not set"
                raise AuthenticationError(msg, provider="gemini")
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def available(self) -> bool:
        """Check if the adapter has a valid API key configured."""
        return bool(self._api_key)

    async def generate(
        self,
        messages: list[Message],
        config: GenerationConfig,
    ) -> LLMResponse:
        """Generate a response using the Gemini API."""
        client = self._get_client()
        system_instruction, contents = _messages_to_gemini(messages)
        logger.debug(
            "GeminiAdapter.generate: model=%s temp=%.2f max_tokens=%d messages=%d",
            config.model, config.temperature, config.max_output_tokens, len(messages),
        )

        gen_config = types.GenerateContentConfig(
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
            system_instruction=system_instruction,
            response_mime_type="application/json" if config.response_format == "json" else None,
        )

        try:
            response = await client.aio.models.generate_content(
                model=config.model,
                contents=contents,
                config=gen_config,
            )
        except Exception as exc:
            logger.error("GeminiAdapter.generate: API call failed — %s", exc)
            return self._handle_error(exc)

        return self._parse_response(response, config.model)

    async def generate_stream(
        self,
        messages: list[Message],
        config: GenerationConfig,
    ) -> AsyncIterator[str]:
        """Generate a streaming response using the Gemini API."""
        client = self._get_client()
        system_instruction, contents = _messages_to_gemini(messages)
        logger.debug("GeminiAdapter.generate_stream: model=%s", config.model)

        gen_config = types.GenerateContentConfig(
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
            system_instruction=system_instruction,
        )

        try:
            stream = client.aio.models.generate_content_stream(
                model=config.model,
                contents=contents,
                config=gen_config,
            )
            async for chunk in await stream:
                if chunk.text:
                    yield chunk.text
        except Exception as exc:
            logger.error("GeminiAdapter.generate_stream: streaming failed — %s", exc)
            self._handle_error(exc)

    def _parse_response(self, response: Any, model: str) -> LLMResponse:
        """Parse Gemini response into LLMResponse."""
        text = response.text or ""

        # Extract token usage if available
        usage = TokenUsage()
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            meta = response.usage_metadata
            usage = TokenUsage(
                prompt_tokens=getattr(meta, "prompt_token_count", 0) or 0,
                completion_tokens=getattr(meta, "candidates_token_count", 0) or 0,
                total_tokens=getattr(meta, "total_token_count", 0) or 0,
            )
            logger.debug(
                "GeminiAdapter: tokens used — prompt=%d completion=%d total=%d",
                usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
            )

        # Determine finish reason
        finish_reason = "stop"
        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            fr = getattr(candidate, "finish_reason", None)
            if fr:
                fr_str = str(fr).lower()
                if "safety" in fr_str or "block" in fr_str:
                    finish_reason = "content_filter"
                    logger.warning("GeminiAdapter: response blocked by content filter (model=%s)", model)
                elif "max" in fr_str or "length" in fr_str:
                    finish_reason = "max_tokens"
                    logger.warning("GeminiAdapter: response truncated at max_tokens (model=%s)", model)

        logger.info("GeminiAdapter.generate: model=%s finish=%s chars=%d", model, finish_reason, len(text))
        return LLMResponse(
            text=text,
            model=model,
            usage=usage,
            finish_reason=finish_reason,
        )

    # ------------------------------------------------------------------
    # Agentic tool-use loop
    # ------------------------------------------------------------------

    def _to_gemini_tools(self, tools: list[ToolDefinition]) -> list[types.Tool]:
        """Convert SpecWeaver ToolDefinitions to Gemini FunctionDeclarations."""
        declarations = []
        for tool in tools:
            schema = tool.to_json_schema()
            declarations.append(types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters=schema if schema["properties"] else None,  # type: ignore[arg-type]
            ))
        return [types.Tool(function_declarations=declarations)]

    def _extract_tool_calls(self, response: Any) -> list[ToolCall]:
        """Convert Gemini function_calls to SpecWeaver ToolCall models."""
        if not hasattr(response, "function_calls") or not response.function_calls:
            return []
        return [
            ToolCall(name=fc.name, args=dict(fc.args) if fc.args else {})
            for fc in response.function_calls
        ]

    def _extract_usage(self, response: Any) -> TokenUsage:
        """Extract token usage from a Gemini response."""
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            meta = response.usage_metadata
            return TokenUsage(
                prompt_tokens=getattr(meta, "prompt_token_count", 0) or 0,
                completion_tokens=getattr(meta, "candidates_token_count", 0) or 0,
                total_tokens=getattr(meta, "total_token_count", 0) or 0,
            )
        return TokenUsage()

    async def generate_with_tools(
        self,
        messages: list[Message],
        config: GenerationConfig,
        tool_executor: object,
    ) -> LLMResponse:
        """Agentic generation loop with tool use via Gemini function calling.

        Converts SpecWeaver ToolDefinitions to Gemini FunctionDeclarations,
        runs multi-turn loop, dispatches tool calls via executor.

        All Gemini-specific types are confined to this method.
        """
        if not config.tools:
            return await self.generate(messages, config)

        client = self._get_client()
        system_instruction, contents = _messages_to_gemini(messages)

        gemini_tools = self._to_gemini_tools(config.tools)
        gen_config = types.GenerateContentConfig(
            tools=gemini_tools,  # type: ignore[arg-type]
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
            system_instruction=system_instruction,
        )

        cumulative_usage = TokenUsage()
        total_calls = 0

        for round_num in range(config.max_tool_rounds):
            logger.debug(
                "GeminiAdapter.generate_with_tools: round %d/%d",
                round_num + 1, config.max_tool_rounds,
            )

            try:
                response = await client.aio.models.generate_content(
                    model=config.model,
                    contents=contents,
                    config=gen_config,
                )
            except Exception as exc:
                logger.error("GeminiAdapter.generate_with_tools: API call failed — %s", exc)
                return self._handle_error(exc)

            cumulative_usage = cumulative_usage + self._extract_usage(response)
            total_calls += 1

            tool_calls = self._extract_tool_calls(response)
            if tool_calls:
                logger.debug(
                    "GeminiAdapter: %d tool call(s) in round %d: %s",
                    len(tool_calls), round_num + 1,
                    [tc.name for tc in tool_calls],
                )
                tool_results = []
                for tc in tool_calls:
                    # Provider-agnostic call: (name, args)
                    result = await tool_executor.execute(tc.name, tc.args)  # type: ignore[attr-defined]
                    tool_results.append((tc, result))

                # Append in Gemini-specific format (only here, inside the adapter)
                contents.append(response.candidates[0].content)  # type: ignore[index,arg-type]
                contents.append(types.Content(
                    role="user",
                    parts=[
                        types.Part.from_function_response(
                            name=tc.name, response=r,
                        )
                        for tc, r in tool_results
                    ],
                ))
            else:
                # LLM produced final text response
                resp = self._parse_response(response, config.model)
                resp.usage = cumulative_usage
                return resp

        # Max rounds reached — log warning and return
        if total_calls > 5:
            logger.warning(
                "GeminiAdapter: tool loop used %d LLM calls (max_rounds=%d)",
                total_calls, config.max_tool_rounds,
            )
        resp = self._parse_response(response, config.model)
        resp.usage = cumulative_usage
        return resp

    async def count_tokens(
        self,
        text: str,
        model: str,
    ) -> int:
        """Count tokens using the Gemini API's native tokenizer.

        This is a free API call — it doesn't consume generation quota.
        """
        client = self._get_client()
        try:
            response = await client.aio.models.count_tokens(
                model=model,
                contents=text,
            )
            return response.total_tokens  # type: ignore[return-value]
        except Exception as exc:
            self._handle_error(exc)
            return self.estimate_tokens(text)  # pragma: no cover

    def _handle_error(self, exc: Exception) -> LLMResponse:
        """Convert Gemini SDK exceptions to SpecWeaver LLM errors."""
        exc_str = str(exc).lower()

        if "401" in exc_str or "api key" in exc_str or "unauthorized" in exc_str:
            logger.error("GeminiAdapter: authentication failed — check GEMINI_API_KEY")
            raise AuthenticationError(str(exc), provider="gemini") from exc

        if "429" in exc_str or "rate limit" in exc_str or "quota" in exc_str:
            logger.warning("GeminiAdapter: rate limit / quota exceeded")
            raise RateLimitError(str(exc), provider="gemini") from exc

        if "404" in exc_str or "not found" in exc_str or "model" in exc_str:
            logger.error("GeminiAdapter: model not found")
            raise ModelNotFoundError(str(exc), provider="gemini") from exc

        if "safety" in exc_str or "blocked" in exc_str:
            logger.warning("GeminiAdapter: content blocked by safety filter")
            raise ContentFilterError(str(exc), provider="gemini") from exc

        logger.error("GeminiAdapter: unclassified generation error — %s", exc)
        raise GenerationError(str(exc), provider="gemini") from exc
