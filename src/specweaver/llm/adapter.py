# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""LLM adapter — abstract interface for LLM providers.

All LLM interactions go through this interface.
MVP: Gemini adapter. Future: OpenAI, Anthropic, Mistral, Ollama, vLLM, Qwen.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from specweaver.llm.models import GenerationConfig, LLMResponse, Message


class LLMAdapter(ABC):
    """Abstract base class for LLM provider adapters.

    All methods are async to support non-blocking I/O.
    Concrete adapters implement provider-specific API calls
    but expose the same interface.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier (e.g., 'gemini', 'openai', 'anthropic')."""
        ...

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        config: GenerationConfig,
    ) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            messages: Conversation history (role + content pairs).
            config: Generation parameters (model, temperature, etc.).

        Returns:
            LLMResponse with generated text, token usage, and finish reason.

        Raises:
            LLMError: Base error for all LLM failures.
            AuthenticationError: Invalid or missing API key.
            RateLimitError: Provider rate limit exceeded.
            ModelNotFoundError: Requested model doesn't exist.
        """
        ...

    @abstractmethod
    async def generate_stream(
        self,
        messages: list[Message],
        config: GenerationConfig,
    ) -> AsyncIterator[str]:
        """Generate a streaming response from the LLM.

        Yields text chunks as they arrive. Useful for interactive
        drafting where the user sees output in real time.

        Args:
            messages: Conversation history.
            config: Generation parameters.

        Yields:
            Text chunks as they arrive from the provider.
        """
        ...
        # Make this a valid async generator for type checking
        yield ""  # pragma: no cover

    @abstractmethod
    def available(self) -> bool:
        """Check if this adapter is configured and ready to use.

        Returns:
            True if the adapter has valid credentials and can make requests.
        """
        ...
