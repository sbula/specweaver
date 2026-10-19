# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""TelemetryCollector — decorator that wraps an LLMAdapter for usage tracking.

Transparent proxy: callers interact with it exactly like an LLMAdapter.
Every ``generate()``, ``generate_with_tools()``, or ``generate_stream()``
call is one row in the cost ledger: written ``pending`` before the request and
closed ``ok`` or ``failed`` after it. The collector is the ledger's only writer.

NOT a subclass of ``LLMAdapter`` — uses the decorator pattern and duck
typing.  Works because ``RunContext.llm`` is typed ``Any``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from specweaver.infrastructure.llm.budget import CallScope, Cost, Reservation, SpendBudget
from specweaver.infrastructure.llm.models import LLMResponse, TokenKind, TokenUsage
from specweaver.infrastructure.llm.prices import rule_break
from specweaver.infrastructure.llm.redaction import Redactor
from specweaver.infrastructure.llm.store import LlmRepository
from specweaver.infrastructure.llm.telemetry import (
    create_usage_record,
    estimate_cost,
    worst_cost,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from specweaver.infrastructure.llm.adapters.base import LLMAdapter
    from specweaver.infrastructure.llm.models import GenerationConfig, Message
    from specweaver.infrastructure.llm.prices import PriceBook

logger = logging.getLogger(__name__)

#: Headroom on the prompt estimate, which is characters / 4.
_PROMPT_MARGIN = 1.25


def _worst_usage(prompt_tokens: int, config: GenerationConfig) -> TokenUsage:
    """A call's worst case in tokens: the prompt with headroom, plus its whole output cap."""
    prompt = math.ceil(prompt_tokens * _PROMPT_MARGIN)
    return TokenUsage(
        prompt_tokens=prompt,
        completion_tokens=config.max_output_tokens,
        total_tokens=prompt + config.max_output_tokens,
    )


class TelemetryCollector:
    """Decorator that wraps an LLMAdapter and captures usage telemetry.

    NOT a subclass of LLMAdapter — uses duck typing (RunContext.llm is Any).
    Each generate/generate_with_tools/generate_stream call is one ledger row, written as it
    happens: a killed process loses none. A write that fails is counted in ``unwritten``.

    Args:
        adapter: The LLMAdapter instance to wrap.
        project: Project name for grouping usage records.
        prices: Looks up a model's price book by the model name a call asked for.
    """

    def __init__(
        self,
        adapter: LLMAdapter,
        project: str,
        prices: Callable[[str], PriceBook | None] | None = None,
        budget: SpendBudget | None = None,
        scope_of: Callable[[GenerationConfig], CallScope] | None = None,
        redactor: Redactor | None = None,
        server: str = "",
        ledger: Any = None,
    ) -> None:
        self._adapter = adapter
        self._server = server
        self._redactor = redactor or Redactor(())
        self._project = project
        self._prices = prices or (lambda _model: None)
        self._scope_of = scope_of
        self._unpriced_warned: set[str] = set()
        self._rule_warned: set[str] = set()
        self._count_hinted = False
        self._lifetime_warned: set[str] = set()
        self._budget = budget or SpendBudget()
        self._ledger = ledger
        #: Ledger writes that failed. Counted, never raised: a cost row never stops the work.
        self.unwritten = 0

    @property
    def budget(self) -> SpendBudget:
        """The run's limits. Every generation path checks them before sending."""
        return self._budget

    def scope(self, config: GenerationConfig) -> CallScope:
        """The limits a call with this config counts against."""
        if self._scope_of is not None:
            return self._scope_of(config)
        return CallScope(prices=self._prices(config.model))

    async def _begin(
        self, messages: list[Message], config: GenerationConfig
    ) -> tuple[list[Message], GenerationConfig, CallScope, Reservation, int | None]:
        """How a single call starts: redact, key, check the limits, and open its ledger row."""
        messages = self._redactor.messages(messages)
        config = self._keyed(config)
        scope, reservation = self._reserve(messages, config)
        call_id = await self._open(config, self._prompt_tokens(messages, config))
        return messages, config, scope, reservation, call_id

    def _keyed(self, config: GenerationConfig) -> GenerationConfig:
        """The config with its cache key: calls of one step type in one project share a cache."""
        if config.cache_key:
            return config
        digest = hashlib.sha256(f"{self._project}\0{config.task_type}".encode()).hexdigest()
        return config.model_copy(update={"cache_key": f"sw-{digest[:32]}"})

    def _reserve(
        self, messages: list[Message], config: GenerationConfig
    ) -> tuple[CallScope, Reservation]:
        scope = self.scope(config)
        return scope, self._budget.before_call(scope, self._worst(messages, config, scope))

    def _worst(self, messages: list[Message], config: GenerationConfig, scope: CallScope) -> Cost:
        return self._worst_of(self._prompt_tokens(messages, config), config, scope)

    def _worst_of(self, prompt_tokens: int, config: GenerationConfig, scope: CallScope) -> Cost:
        worst = _worst_usage(prompt_tokens, config)
        return Cost(usd=worst_cost(worst, scope.prices), tokens=worst.total_tokens)

    def _record_failure(
        self, scope: CallScope, reservation: Reservation, exc: BaseException
    ) -> None:
        """Count a failed call's usage if the adapter attached it, else its reserved worst case."""
        usage = getattr(exc, "usage", None)
        cost = (
            Cost(usd=estimate_cost(usage, scope.prices), tokens=usage.total_tokens)
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
        messages, config, scope, reservation, call_id = await self._begin(messages, config)
        start = time.monotonic()
        try:
            response = await self._adapter.generate(messages, config)
        except BaseException as exc:
            self._record_failure(scope, reservation, exc)
            await self._close_failed(call_id, config, exc, time.monotonic() - start)
            raise
        await self._capture(
            config,
            response,
            time.monotonic() - start,
            scope,
            reservation,
            call_id,
            start=self._start_of(messages, config),
        )
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
        on_tool_round = self._redactor.rounds(on_tool_round)
        config = self._keyed(config)
        scope, first = self._reserve(messages, config)
        held = [first]
        prompt_tokens = [self._prompt_tokens(messages, config)]
        call_id = await self._open(config, prompt_tokens[0])
        start_hash = self._start_of(messages, config)
        widening: list[asyncio.Task[Any]] = []

        def before_request(round_num: int, prompt_chars: int) -> None:
            if round_num > 0:
                worst = self._worst_of(_estimate_chars(prompt_chars), config, scope)
                held.append(self._budget.before_call(scope, worst))
                prompt_tokens.append(_estimate_chars(prompt_chars))
                widening.append(asyncio.ensure_future(self._widen(call_id, config, prompt_tokens)))

        start = time.monotonic()
        try:
            response = await self._adapter.generate_with_tools(
                messages, config, tool_executor, on_tool_round, before_request=before_request
            )
        except BaseException as exc:
            self._record_failure(scope, Reservation.combined(held), exc)
            await asyncio.gather(*widening, return_exceptions=True)
            await self._close_failed(call_id, config, exc, time.monotonic() - start)
            raise
        elapsed = time.monotonic() - start
        await asyncio.gather(*widening, return_exceptions=True)
        await self._capture(
            config,
            response,
            elapsed,
            scope,
            Reservation.combined(held),
            call_id,
            start=start_hash,
        )
        return response

    async def generate_stream(
        self,
        messages: list[Message],
        config: GenerationConfig,
    ) -> AsyncIterator[str]:
        """Proxy ``generate_stream()`` — yields chunks; tokens are estimated from the text."""
        messages, config, scope, reservation, call_id = await self._begin(messages, config)
        start = time.monotonic()
        total_text: list[str] = []
        try:
            async for chunk in self._adapter.generate_stream(messages, config):
                total_text.append(chunk)
                yield chunk
        except BaseException as exc:
            self._record_failure(scope, reservation, exc)
            await self._close_failed(call_id, config, exc, time.monotonic() - start)
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
        await self._capture(
            config, synthetic, time.monotonic() - start, scope, reservation, call_id, reported=False
        )

    # ------------------------------------------------------------------
    # Record capture
    # ------------------------------------------------------------------

    async def _capture(
        self,
        config: GenerationConfig,
        response: LLMResponse,
        elapsed: float,
        scope: CallScope,
        reservation: Reservation,
        call_id: int | None,
        *,
        reported: bool = True,
        start: str | None = None,
    ) -> None:
        """Create a UsageRecord and append to the internal list.

        ``reported`` is false for a stream, whose usage is estimated from its text, not reported.
        ``start`` is the hash of the prompt's start (`_start_of`), remembered for the lifetime check.

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
            server=self._server,
        )
        await self._close(call_id, record.model_dump(), "ok")
        unpriced = record.estimated_cost_usd is None and not record.billed.local
        if unpriced and config.model not in self._unpriced_warned:
            self._unpriced_warned.add(config.model)
            logger.warning(
                "%s has no known price: its tokens are counted, its money is not", config.model
            )
        self._check_cache_rule(config, response.usage, scope.prices)
        if reported:
            self._hint_cache_count(response.usage, scope.prices)
        if start is not None:
            sent_at = datetime.now(UTC) - timedelta(seconds=elapsed)
            before = await self._remember_start(config.model, start, sent_at)
            self._check_cache_lifetime(config.model, response.usage, scope.prices, before, sent_at)
        # A reply that reports no usage counts its reserved worst case.
        cost = (
            None
            if response.usage == TokenUsage()
            else Cost(usd=record.estimated_cost_usd, tokens=record.total_tokens)
        )
        self._budget.record(scope, cost, reservation)

    @staticmethod
    def _start_of(messages: list[Message], config: GenerationConfig) -> str:
        """A hash of what a cache can hold from run to run: the system text and the first message
        up to the run clock. Never the text itself."""
        first = messages[0].content.split("<run_clock>")[0] if messages else ""
        text = f"{config.system_instruction or ''}\0{first}"
        return hashlib.sha256(text.encode()).hexdigest()

    async def _remember_start(self, model: str, start: str, sent_at: datetime) -> datetime | None:
        """When this start was sent before, if ever; and that it was sent now."""
        if self._ledger is None:
            return None
        server = self._server
        result = await self._write(
            lambda repo: repo.touch_prompt_start(server, model, start, sent_at)
        )
        return result if isinstance(result, datetime) else None

    def _check_cache_lifetime(
        self,
        model: str,
        usage: TokenUsage,
        prices: PriceBook | None,
        before: datetime | None,
        sent_at: datetime,
    ) -> None:
        """Warn once per model when a cache answers more than twice its rule's lifetime after the
        start was last sent: the provider keeps caches longer than the shipped list says."""
        if not usage.cached_read_tokens or prices is None or before is None:
            return
        if model in self._lifetime_warned:
            return
        price = prices.price_for(TokenKind.CACHED_READ, usage.prompt_tokens)
        lifetime = price.rule.max_age_seconds if price and price.rule else None
        gap = (sent_at - before).total_seconds()
        if lifetime is None or gap <= 2 * lifetime:
            return
        self._lifetime_warned.add(model)
        logger.warning(
            "%s read %d tokens from a cache %.0f s after the prompt start was last sent; its cache "
            "lifetime is %d s. The provider may keep caches longer; check catalogue_data/models.toml",
            model,
            usage.cached_read_tokens,
            gap,
            lifetime,
        )

    def _hint_cache_count(self, usage: TokenUsage, prices: PriceBook | None) -> None:
        """Once per local server whose reply carries no cached count: how vLLM is made to report it."""
        if self._count_hinted or prices is None or not prices.local:
            return
        if usage == TokenUsage() or usage.cached_read_tokens is not None:
            return
        self._count_hinted = True
        logger.warning(
            "%s reports no cached tokens, so `sw usage` cannot show them; if it is vLLM, start it "
            "with --enable-prompt-tokens-details",
            self._server or "the local server",
        )

    def _check_cache_rule(
        self, config: GenerationConfig, usage: TokenUsage, prices: PriceBook | None
    ) -> None:
        """Warn once per model when a cache hit breaks the offering's rule: the provider's rule
        may have changed, and the shipped list with it."""
        model = config.model
        if not usage.cached_read_tokens or prices is None or model in self._rule_warned:
            return
        price = prices.price_for(TokenKind.CACHED_READ, usage.prompt_tokens)
        if price is None or price.rule is None:
            return
        sent: frozenset[str] = getattr(self._adapter, "cache_sent", lambda _c: frozenset())(config)
        reason = rule_break(price.rule, prompt_tokens=usage.prompt_tokens, sent=sent)
        if reason:
            self._rule_warned.add(model)
            logger.warning(
                "%s cached %d tokens against its cache rule: %s. The provider may have changed "
                "the rule; check catalogue_data/models.toml",
                model,
                usage.cached_read_tokens,
                reason,
            )

    # ------------------------------------------------------------------
    # The ledger: the one writer of `llm_usage_log`
    # ------------------------------------------------------------------

    def _row(self, config: GenerationConfig, usage: TokenUsage, elapsed: float) -> dict[str, Any]:
        response = LLMResponse(text="", model=config.model, usage=usage)
        return create_usage_record(
            config,
            response,
            self._adapter.provider_name,
            self._project,
            int(elapsed * 1000),
            self._prices(config.model),
            server=self._server,
        ).model_dump()

    async def _write(self, action: Callable[[LlmRepository], Any]) -> Any:
        """One ledger write; a failure is logged and gives None, never raised."""
        try:
            async with self._ledger.async_session_scope() as session:
                return await action(LlmRepository(session))
        except Exception:
            logger.warning("A call could not be written to the cost ledger", exc_info=True)
            return None

    async def _open(self, config: GenerationConfig, prompt_tokens: int) -> int | None:
        """The call's `pending` row, with its worst case, before the request is sent."""
        if self._ledger is None:
            return None
        row = self._row(config, _worst_usage(prompt_tokens, config), 0.0)
        result = await self._write(lambda repo: repo.open_call(row))
        if not isinstance(result, int):
            self.unwritten += 1
            return None
        return result

    async def _widen(
        self, call_id: int | None, config: GenerationConfig, prompt_tokens: list[int]
    ) -> None:
        """A tool loop's `pending` row: the worst case of every round so far."""
        if call_id is None:
            return
        rounds = [_worst_usage(tokens, config) for tokens in prompt_tokens]
        total = TokenUsage(
            prompt_tokens=sum(r.prompt_tokens for r in rounds),
            completion_tokens=sum(r.completion_tokens for r in rounds),
            total_tokens=sum(r.total_tokens for r in rounds),
        )
        row = self._row(config, total, 0.0)
        await self._write(lambda repo: repo.widen_call(call_id, row))

    async def _close(self, call_id: int | None, row: dict[str, Any], status: str) -> None:
        """A call whose row cannot be closed, or is gone, counts as missing."""
        if (
            call_id is not None
            and await self._write(lambda repo: repo.close_call(call_id, row, status)) is not True
        ):
            self.unwritten += 1

    async def _close_failed(
        self, call_id: int | None, config: GenerationConfig, exc: BaseException, elapsed: float
    ) -> None:
        """`failed`, with the usage the error reported; without one, tokens and cost unknown."""
        usage = getattr(exc, "usage", None)
        if not isinstance(usage, TokenUsage):
            usage = None
        row = self._row(config, usage or TokenUsage(), elapsed)
        if usage is None:
            row["estimated_cost_usd"] = None
        await self._close(call_id, row, "failed")

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
