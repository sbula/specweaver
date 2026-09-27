# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import asyncio
import logging
import weakref
from collections.abc import AsyncIterator, Callable

from specweaver.infrastructure.llm.adapters.base import LLMAdapter
from specweaver.infrastructure.llm.models import GenerationConfig, LLMResponse, Message

logger = logging.getLogger(__name__)

# One semaphore per (event loop, key). An asyncio.Semaphore binds to the loop it first waits on, so
# one shared across loops raises "bound to a different event loop" under contention.
_SEMAPHORES: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict[str, asyncio.Semaphore]] = (
    weakref.WeakKeyDictionary()
)


class AsyncRateLimiterAdapter(LLMAdapter):
    """Limits how many calls run at once against one server; the rest wait for a free slot.

    There is no wait timeout: a local server can take minutes per answer, and a queued call must not
    fail only because the server is busy. A hung call is ended by the provider client's own timeout.
    """

    def __init__(self, wrapped: LLMAdapter, limit: int = 3, key: str | None = None) -> None:
        self._wrapped = wrapped
        self._limit = limit
        self._key = key or wrapped.provider_name

        # Dynamically mirror metadata interfaces required by upstream integrations
        self.provider_name = wrapped.provider_name
        self.api_key_env_var = wrapped.api_key_env_var

    def _get_semaphore(self) -> asyncio.Semaphore:
        """The semaphore for this key on the running event loop; the first limit set wins."""
        per_loop = _SEMAPHORES.setdefault(asyncio.get_running_loop(), {})
        if self._key not in per_loop:
            per_loop[self._key] = asyncio.Semaphore(self._limit)
        return per_loop[self._key]

    async def _wait_for_lock(self) -> asyncio.Semaphore:
        semaphore = self._get_semaphore()
        logger.debug("[%s] Waiting for a slot (limit=%d)...", self._key, self._limit)
        await semaphore.acquire()
        return semaphore

    async def generate(self, messages: list[Message], config: GenerationConfig) -> LLMResponse:
        semaphore = await self._wait_for_lock()
        try:
            return await self._wrapped.generate(messages, config)
        finally:
            semaphore.release()
            logger.debug("[%s] Slot released.", self._key)

    async def generate_stream(
        self, messages: list[Message], config: GenerationConfig
    ) -> AsyncIterator[str]:
        semaphore = await self._wait_for_lock()
        try:
            async for chunk in self._wrapped.generate_stream(messages, config):
                yield chunk
        finally:
            semaphore.release()
            logger.debug("[%s] Slot released.", self._key)

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
        on_tool_round: Callable[[int, list[Message]], None] | None = None,
    ) -> LLMResponse:
        """Wraps the function-calling generation sequence inside a lock boundary."""
        semaphore = await self._wait_for_lock()
        try:
            return await self._wrapped.generate_with_tools(
                messages, config, tool_executor, on_tool_round
            )
        finally:
            semaphore.release()
            logger.debug("[%s] Slot released.", self._key)
