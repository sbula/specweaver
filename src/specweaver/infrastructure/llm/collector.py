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

import json
import logging
import math
import time
from typing import TYPE_CHECKING, Any

from specweaver.commons.async_bridge import run_sync
from specweaver.infrastructure.llm.budget import CallScope, Cost, Reservation, SpendBudget
from specweaver.infrastructure.llm.models import LLMResponse, TokenUsage
from specweaver.infrastructure.llm.redaction import Redactor
from specweaver.infrastructure.llm.store import LlmRepository
from specweaver.infrastructure.llm.telemetry import UsageRecord, create_usage_record, estimate_cost

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from specweaver.core.config.llm_settings import ModelFacts
    from specweaver.infrastructure.llm.adapters.base import LLMAdapter
    from specweaver.infrastructure.llm.models import GenerationConfig, Message

logger = logging.getLogger(__name__)

#: Headroom on the prompt estimate, which is characters / 4.
_PROMPT_MARGIN = 1.25


class TelemetryCollector:
    """Decorator that wraps an LLMAdapter and captures usage telemetry.

    NOT a subclass of LLMAdapter — uses duck typing (RunContext.llm is Any).
    Each generate/generate_with_tools/generate_stream call creates one
    UsageRecord.  Records accumulate in memory until ``flush(db)`` is called.

    Args:
        adapter: The LLMAdapter instance to wrap.
        project: Project name for grouping usage records.
        prices: Looks up a model's facts (its price) by the model name a call asked for.
    """

    def __init__(
        self,
        adapter: LLMAdapter,
        project: str,
        prices: Callable[[str], ModelFacts | None] | None = None,
        budget: SpendBudget | None = None,
        scope_of: Callable[[GenerationConfig], CallScope] | None = None,
        redactor: Redactor | None = None,
    ) -> None:
        self._adapter = adapter
        self._redactor = redactor or Redactor(())
        self._project = project
        self._prices = prices or (lambda _model: None)
        self._scope_of = scope_of
        self._unpriced_warned: set[str] = set()
        self._records: list[UsageRecord] = []
        self._budget = budget or SpendBudget()

    @property
    def budget(self) -> SpendBudget:
        """The run's limits. Every generation path checks them before sending."""
        return self._budget

    def scope(self, config: GenerationConfig) -> CallScope:
        """The limits a call with this config counts against."""
        if self._scope_of is not None:
            return self._scope_of(config)
        return CallScope(facts=self._prices(config.model))

    def _reserve(
        self, messages: list[Message], config: GenerationConfig
    ) -> tuple[CallScope, Reservation]:
        scope = self.scope(config)
        return scope, self._budget.before_call(scope, self._worst(messages, config, scope))

    def _worst(self, messages: list[Message], config: GenerationConfig, scope: CallScope) -> Cost:
        return self._worst_of(self._prompt_tokens(messages, config), config, scope)

    def _worst_of(self, prompt_tokens: int, config: GenerationConfig, scope: CallScope) -> Cost:
        prompt = math.ceil(prompt_tokens * _PROMPT_MARGIN)
        worst = TokenUsage(
            prompt_tokens=prompt,
            completion_tokens=config.max_output_tokens,
            total_tokens=prompt + config.max_output_tokens,
        )
        return Cost(usd=estimate_cost(worst, scope.facts), tokens=worst.total_tokens)

    def _record_failure(
        self, scope: CallScope, reservation: Reservation, exc: BaseException
    ) -> None:
        """Count a failed call's usage if the adapter attached it, else its reserved worst case."""
        usage = getattr(exc, "usage", None)
        cost = (
            Cost(usd=estimate_cost(usage, scope.facts), tokens=usage.total_tokens)
            if isinstance(usage, TokenUsage)
            else None
        )
        self._budget.record(scope, cost, reservation)

    def _prompt_tokens(self, messages: list[Message], config: GenerationConfig) -> int:
        text = (config.system_instruction or "") + "".join(m.content for m in messages)
        if config.tools:
            text += json.dumps([tool.model_dump(mode="json") for tool in config.tools])
        return _estimate_tokens(text)

    # ------------------------------------------------------------------
    # Generation proxies (telemetry captured per call)
    # ------------------------------------------------------------------

    async def generate(
        self,
        messages: list[Message],
        config: GenerationConfig,
    ) -> LLMResponse:
        """Proxy ``generate()`` — captures timing and usage."""
        messages = self._redactor.messages(messages)
        scope, reservation = self._reserve(messages, config)
        start = time.monotonic()
        try:
            response = await self._adapter.generate(messages, config)
        except BaseException as exc:
            self._record_failure(scope, reservation, exc)
            raise
        self._capture(config, response, time.monotonic() - start, scope, reservation)
        return response

    async def generate_with_tools(
        self,
        messages: list[Message],
        config: GenerationConfig,
        tool_executor: Any,
        on_tool_round: Any = None,
    ) -> LLMResponse:
        """Proxy ``generate_with_tools()``; every round is checked before its request."""
        messages = self._redactor.messages(messages)
        tool_executor = self._redactor.tools(tool_executor)
        scope, first = self._reserve(messages, config)
        held = [first]

        def before_request(round_num: int, prompt_chars: int) -> None:
            if round_num > 0:
                worst = self._worst_of(_estimate_chars(prompt_chars), config, scope)
                held.append(self._budget.before_call(scope, worst))

        start = time.monotonic()
        try:
            response = await self._adapter.generate_with_tools(
                messages, config, tool_executor, on_tool_round, before_request=before_request
            )
        except BaseException as exc:
            self._record_failure(scope, Reservation.combined(held), exc)
            raise
        elapsed = time.monotonic() - start
        self._capture(config, response, elapsed, scope, Reservation.combined(held))
        return response

    async def generate_stream(
        self,
        messages: list[Message],
        config: GenerationConfig,
    ) -> AsyncIterator[str]:
        """Proxy ``generate_stream()`` — yields chunks; tokens are estimated from the text."""
        messages = self._redactor.messages(messages)
        scope, reservation = self._reserve(messages, config)
        start = time.monotonic()
        total_text: list[str] = []
        try:
            async for chunk in self._adapter.generate_stream(messages, config):
                total_text.append(chunk)
                yield chunk
        except BaseException as exc:
            self._record_failure(scope, reservation, exc)
            raise
        prompt = self._prompt_tokens(messages, config)
        output = _estimate_tokens("".join(total_text))
        synthetic = LLMResponse(
            text="",
            model=config.model,
            usage=TokenUsage(
                prompt_tokens=prompt, completion_tokens=output, total_tokens=prompt + output
            ),
        )
        self._capture(config, synthetic, time.monotonic() - start, scope, reservation)

    # ------------------------------------------------------------------
    # Record capture
    # ------------------------------------------------------------------

    def _capture(
        self,
        config: GenerationConfig,
        response: LLMResponse,
        elapsed: float,
        scope: CallScope,
        reservation: Reservation,
    ) -> None:
        """Create a UsageRecord and append to the internal list.

        ``task_type`` is read from ``config.task_type`` (set per call
        by each handler), NOT from the constructor.
        """
        record = create_usage_record(
            config,
            response,
            self._adapter.provider_name,
            self._project,
            int(elapsed * 1000),
            self._prices(config.model),
        )
        self._records.append(record)
        if record.estimated_cost_usd is None and config.model not in self._unpriced_warned:
            self._unpriced_warned.add(config.model)
            logger.warning(
                "%s has no known price: its tokens are counted, its money is not", config.model
            )
        # A reply that reports no usage counts its reserved worst case.
        cost = (
            None
            if response.usage == TokenUsage()
            else Cost(usd=record.estimated_cost_usd, tokens=record.total_tokens)
        )
        self._budget.record(scope, cost, reservation)

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
            # Never re-enters a running loop — see `commons.async_bridge`. Async callers should
            # prefer `flush_async` and skip the thread hop entirely.
            run_sync(_flush)
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

    async def flush_async(self, db: Any) -> int:
        """Persist all accumulated records to DB asynchronously.

        Never raises — telemetry failures are logged, not propagated.
        Returns the number of records that were flushed.
        """
        count = len(self._records)
        if count == 0:
            return 0

        try:
            async with db.async_session_scope() as session:
                repo = LlmRepository(session)
                for r in self._records:
                    await repo.log_usage(r.model_dump())
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


def _estimate_tokens(text: str) -> int:
    """About four characters per token; the brake adds its margin on top."""
    return _estimate_chars(len(text))


def _estimate_chars(chars: int) -> int:
    return chars // 4
