# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""TelemetryCollector — decorator that wraps an LLMAdapter for usage tracking.

Transparent proxy: callers interact with it exactly like an LLMAdapter.
Every ``generate()``, ``generate_with_tools()``, or ``generate_stream()``
call produces one ``UsageRecord`` accumulated in memory.  The caller
persists records by calling ``flush(db)`` when done.

NOT a subclass of ``LLMAdapter`` — uses the decorator pattern and duck
typing.  Works because ``RunContext.llm`` is typed ``Any``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

import anyio
import nest_asyncio

from specweaver.infrastructure.llm.models import LLMResponse, TokenUsage
from specweaver.infrastructure.llm.store import LlmRepository
from specweaver.infrastructure.llm.telemetry import CostEntry, UsageRecord, create_usage_record

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from specweaver.infrastructure.llm.adapters.base import LLMAdapter
    from specweaver.infrastructure.llm.models import GenerationConfig, Message

logger = logging.getLogger(__name__)


class TelemetryCollector:
    """Decorator that wraps an LLMAdapter and captures usage telemetry.

    NOT a subclass of LLMAdapter — uses duck typing (RunContext.llm is Any).
    Each generate/generate_with_tools/generate_stream call creates one
    UsageRecord.  Records accumulate in memory until ``flush(db)`` is called.

    Args:
        adapter: The LLMAdapter instance to wrap.
        project: Project name for grouping usage records.
        cost_overrides: Optional user-configured cost table (from DB).
    """

    def __init__(
        self,
        adapter: LLMAdapter,
        project: str,
        cost_overrides: dict[str, CostEntry] | None = None,
    ) -> None:
        self._adapter = adapter
        self._project = project
        self._cost_overrides = cost_overrides
        self._records: list[UsageRecord] = []

    # ------------------------------------------------------------------
    # Generation proxies (telemetry captured per call)
    # ------------------------------------------------------------------

    async def generate(
        self,
        messages: list[Message],
        config: GenerationConfig,
    ) -> LLMResponse:
        """Proxy ``generate()`` — captures timing and usage."""
        start = time.monotonic()
        response = await self._adapter.generate(messages, config)
        self._capture(config, response, time.monotonic() - start)
        return response

    async def generate_with_tools(
        self,
        messages: list[Message],
        config: GenerationConfig,
        tool_executor: Any,
        on_tool_round: Any = None,
    ) -> LLMResponse:
        """Proxy ``generate_with_tools()`` — captures cumulative usage."""
        start = time.monotonic()
        response = await self._adapter.generate_with_tools(
            messages,
            config,
            tool_executor,
            on_tool_round,
        )
        self._capture(config, response, time.monotonic() - start)
        return response

    async def generate_stream(
        self,
        messages: list[Message],
        config: GenerationConfig,
    ) -> AsyncIterator[str]:
        """Proxy ``generate_stream()`` — yields chunks, estimates telemetry.

        After the stream is fully consumed, estimates output tokens from
        accumulated text.  ``prompt_tokens`` is 0 for streaming calls
        (exact counts require adapter-level support — see backlog).
        """
        start = time.monotonic()
        total_text: list[str] = []
        async for chunk in self._adapter.generate_stream(messages, config):
            total_text.append(chunk)
            yield chunk

        # Build synthetic response for telemetry after stream exhaustion.
        elapsed = time.monotonic() - start
        full_text = "".join(total_text)
        estimated_output = self._adapter.estimate_tokens(full_text)
        synthetic = LLMResponse(
            text="",
            model=config.model,
            usage=TokenUsage(
                prompt_tokens=0,
                completion_tokens=estimated_output,
                total_tokens=estimated_output,
            ),
        )
        self._capture(config, synthetic, elapsed)

    # ------------------------------------------------------------------
    # Record capture
    # ------------------------------------------------------------------

    def _capture(
        self,
        config: GenerationConfig,
        response: LLMResponse,
        elapsed: float,
    ) -> None:
        """Create a UsageRecord and append to the internal list.

        ``task_type`` is read from ``config.task_type`` (set per call
        by each handler), NOT from the constructor.
        """
        self._records.append(
            create_usage_record(
                config,
                response,
                self._adapter.provider_name,
                self._project,
                int(elapsed * 1000),
                cost_overrides=self._cost_overrides,
            )
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @property
    def records(self) -> list[UsageRecord]:
        """Return a copy of accumulated records (for testing)."""
        return list(self._records)

    def flush(self, db: Any) -> int:
        """Persist all accumulated records to DB.

        Never raises — telemetry failures are logged, not propagated.
        Returns the number of records that were flushed.

        Args:
            db: Database instance with a ``log_usage(record)`` method.
        """
        count = len(self._records)
        if count == 0:
            return 0

        async def _flush() -> None:
            async with db.async_session_scope() as session:
                repo = LlmRepository(session)
                for r in self._records:
                    await repo.log_usage(r.model_dump())

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                nest_asyncio.apply(loop)
                loop.run_until_complete(_flush())
            else:
                anyio.run(_flush)
            self._records.clear()
            logger.debug("Flushed %d telemetry records for project '%s'", count, self._project)
        except Exception:
            logger.warning(
                "Failed to flush %d telemetry records for project '%s'",
                count,
                self._project,
                exc_info=True,
            )
        return count

    # ------------------------------------------------------------------
    # Delegate remaining LLMAdapter interface
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        """Delegate to wrapped adapter."""
        return self._adapter.provider_name

    def available(self) -> bool:
        """Delegate to wrapped adapter."""
        return self._adapter.available()

    async def count_tokens(self, text: str, model: str) -> int:
        """Delegate to wrapped adapter."""
        return await self._adapter.count_tokens(text, model)

    def estimate_tokens(self, text: str) -> int:
        """Delegate to wrapped adapter."""
        return self._adapter.estimate_tokens(text)
