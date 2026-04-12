# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""LLM adapter — abstract interface for LLM providers.

All LLM interactions go through this interface.
Concrete adapters are self-describing: each declares its own
provider_name, api_key_env_var, and default_costs as class attributes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from specweaver.infrastructure.llm.models import GenerationConfig, LLMResponse, Message
    from specweaver.infrastructure.llm.telemetry import CostEntry


class LLMAdapter(ABC):
    """Abstract base class for LLM provider adapters.

    All methods are async to support non-blocking I/O.
    Concrete adapters implement provider-specific API calls
    but expose the same interface.

    Subclasses MUST override the metadata class attributes:
    - ``provider_name``: registry key (e.g. ``"gemini"``, ``"openai"``)
    - ``api_key_env_var``: environment variable name for the API key
    - ``default_costs``: ``{model_name: CostEntry}`` for cost estimation
    """

    # --- Metadata (subclasses MUST override) ---
    provider_name: str = ""
    api_key_env_var: str = ""
    default_costs: ClassVar[dict[str, CostEntry]] = {}

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

    @abstractmethod
    async def count_tokens(
        self,
        text: str,
        model: str,
    ) -> int:
        """Count tokens using the provider's native tokenizer.

        This makes a (typically free) API call to get the exact token count
        for the given text and model.

        Args:
            text: The text to count tokens for.
            model: The model name (tokenizers differ per model).

        Returns:
            Exact token count from the provider.

        Raises:
            LLMError: If the provider call fails.
        """
        ...

    def estimate_tokens(self, text: str) -> int:
        """Fast offline token estimate. No API call.

        Default heuristic: ``len(text) // 4`` (~25% error margin).
        Concrete adapters may override with provider-specific heuristics.

        Args:
            text: The text to estimate tokens for.

        Returns:
            Approximate token count.
        """
        return len(text) // 4

    async def generate_with_tools(
        self,
        messages: list[Message],
        config: GenerationConfig,
        tool_executor: object,
        on_tool_round: Callable[[int, list[Message]], None] | None = None,
    ) -> LLMResponse:
        """Agentic generation loop with tool use.

        Default implementation: ignores tools, calls generate() directly.
        Adapters that support function calling override this.

        Returns:
            LLMResponse with cumulative token usage across all rounds.
        """
        import logging

        logging.getLogger(__name__).warning(
            "%s does not support tool use — falling back to generate()",
            self.provider_name,
        )
        return await self.generate(messages, config)
