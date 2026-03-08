# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Gemini adapter — concrete LLMAdapter for Google's Gemini API.

Uses the `google-genai` SDK (GA since May 2025).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from google import genai
from google.genai import types

from specweaver.llm.adapter import LLMAdapter
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
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


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
            contents.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg.content)],
            ))

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

        gen_config = types.GenerateContentConfig(
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
            system_instruction=system_instruction,
            response_mime_type="application/json"
            if config.response_format == "json"
            else None,
        )

        try:
            response = await client.aio.models.generate_content(
                model=config.model,
                contents=contents,
                config=gen_config,
            )
        except Exception as exc:
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

        gen_config = types.GenerateContentConfig(
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
            system_instruction=system_instruction,
        )

        try:
            async for chunk in client.aio.models.generate_content_stream(
                model=config.model,
                contents=contents,
                config=gen_config,
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as exc:
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

        # Determine finish reason
        finish_reason = "stop"
        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            fr = getattr(candidate, "finish_reason", None)
            if fr:
                fr_str = str(fr).lower()
                if "safety" in fr_str or "block" in fr_str:
                    finish_reason = "content_filter"
                elif "max" in fr_str or "length" in fr_str:
                    finish_reason = "max_tokens"

        return LLMResponse(
            text=text,
            model=model,
            usage=usage,
            finish_reason=finish_reason,
        )

    def _handle_error(self, exc: Exception) -> LLMResponse:
        """Convert Gemini SDK exceptions to SpecWeaver LLM errors."""
        exc_str = str(exc).lower()

        if "401" in exc_str or "api key" in exc_str or "unauthorized" in exc_str:
            raise AuthenticationError(str(exc), provider="gemini") from exc

        if "429" in exc_str or "rate limit" in exc_str or "quota" in exc_str:
            raise RateLimitError(str(exc), provider="gemini") from exc

        if "404" in exc_str or "not found" in exc_str or "model" in exc_str:
            raise ModelNotFoundError(str(exc), provider="gemini") from exc

        if "safety" in exc_str or "blocked" in exc_str:
            raise ContentFilterError(str(exc), provider="gemini") from exc

        raise GenerationError(str(exc), provider="gemini") from exc
