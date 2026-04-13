# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import asyncio
import logging
from collections.abc import AsyncIterator

from specweaver.infrastructure.llm.adapters.base import LLMAdapter
from specweaver.infrastructure.llm.models import GenerationConfig, LLMResponse, Message

logger = logging.getLogger(__name__)

# Global tracking for Semaphores securely keyed by provider name
_PROVIDER_SEMAPHORES: dict[str, asyncio.Semaphore] = {}


class AsyncRateLimiterAdapter(LLMAdapter):
    """Wraps an LLMAdapter with an asyncio.Semaphore to natively throttle concurrency.

    This mitigates HTTP 429 Rate Limit Crash loops when the topological
    Orchestrator pipeline fan-outs multiple parallel independent waves.
    """

    def __init__(self, wrapped: LLMAdapter, limit: int = 3, timeout: float = 30.0) -> None:
        self._wrapped = wrapped
        self._limit = limit
        self._timeout = timeout

        # Dynamically mirror metadata interfaces required by upstream integrations
        self.provider_name = wrapped.provider_name
        self.api_key_env_var = wrapped.api_key_env_var

    def _get_semaphore(self) -> asyncio.Semaphore:
        """Fetch or initialize the singleton lock specific to this provider."""
        provider = self.provider_name
        if provider not in _PROVIDER_SEMAPHORES:
            _PROVIDER_SEMAPHORES[provider] = asyncio.Semaphore(self._limit)
        return _PROVIDER_SEMAPHORES[provider]

    async def _wait_for_lock(self) -> asyncio.Semaphore:
        """Acquires the adapter-specific semaphore bound by `self._timeout`."""
        semaphore = self._get_semaphore()
        logger.debug(
            "[%s] Awaiting concurrent lock access (limit=%d)...",
            self.provider_name,
            self._limit,
        )
        try:
            # We strictly enforce `wait_for` so we can bubble `LLMAdapterError` natively if gridlocked.
            await asyncio.wait_for(semaphore.acquire(), timeout=self._timeout)
            logger.debug("[%s] Concurrent lock acquired.", self.provider_name)
            return semaphore
        except TimeoutError as e:
            logger.error(
                "[%s] Concurrency lock timed out after %.1fs", self.provider_name, self._timeout
            )
            from specweaver.infrastructure.llm.factory import LLMAdapterError

            raise LLMAdapterError(
                f"Rate limit timeout: Exhausted concurrency bounds awaiting slots for {self.provider_name}."
            ) from e

    async def generate(self, messages: list[Message], config: GenerationConfig) -> LLMResponse:
        semaphore = await self._wait_for_lock()
        try:
            return await self._wrapped.generate(messages, config)
        finally:
            semaphore.release()
            logger.debug("[%s] Concurrent lock released.", self.provider_name)

    async def generate_stream(
        self, messages: list[Message], config: GenerationConfig
    ) -> AsyncIterator[str]:
        semaphore = await self._wait_for_lock()
        try:
            async for chunk in self._wrapped.generate_stream(messages, config):
                yield chunk
        finally:
            semaphore.release()
            logger.debug("[%s] Concurrent lock released.", self.provider_name)

    def available(self) -> bool:
        return self._wrapped.available()

    async def count_tokens(self, text: str, model: str) -> int:
        return await self._wrapped.count_tokens(text, model)

    def estimate_tokens(self, text: str) -> int:
        return self._wrapped.estimate_tokens(text)

    async def generate_with_tools(
        self,
        messages: list[Message],
        config: GenerationConfig,
        tool_executor: object,
        on_tool_round: object | None = None,
    ) -> LLMResponse:
        """Wraps the function-calling generation sequence inside a lock boundary."""
        semaphore = await self._wait_for_lock()
        try:
            return await self._wrapped.generate_with_tools(
                messages, config, tool_executor, on_tool_round
            )
        finally:
            semaphore.release()
            logger.debug("[%s] Concurrent lock released.", self.provider_name)
