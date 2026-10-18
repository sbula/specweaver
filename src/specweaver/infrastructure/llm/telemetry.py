# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Token & cost telemetry — pure-logic module (no I/O, no DB access).

Provides data models and cost estimation for LLM usage tracking.
The ``TelemetryCollector`` (in ``collector.py``) uses these to build
``UsageRecord`` instances and writes each call's row through ``LlmRepository``.

"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from specweaver.infrastructure.llm.models import (
    GenerationConfig,
    LLMResponse,
    TaskType,
    TokenKind,
    TokenUsage,
)

if TYPE_CHECKING:
    from specweaver.infrastructure.llm.prices import Price, PriceBook

logger = logging.getLogger(__name__)


class Billed(BaseModel):
    """How a call was billed: what it took from a cache, and the price of each token kind."""

    #: `None`: not reported, unknown.
    cached_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    #: A call to a local server: no cost is *not applicable*, never *unknown*.
    local: bool | None = None
    #: The price each token kind was billed at: `kind`, `usd_per_million`, `source`.
    price_lines: list[dict[str, object]] = []


class UsageRecord(BaseModel):
    """A single LLM usage telemetry record.

    One record per ``generate()`` / ``generate_with_tools()`` /
    ``generate_stream()`` call.  Persisted as one row in
    ``llm_usage_log``.
    """

    timestamp: str
    project_name: str
    task_type: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float | None = None
    duration_ms: int = 0
    run_id: str = ""
    server: str = ""
    dal_level: str = ""
    step_name: str = ""
    billed: Billed = Billed()


@dataclass(frozen=True)
class BillLine:
    """The price one token kind of a call was billed at, and where it came from."""

    kind: TokenKind
    usd_per_million: float
    source: str


@dataclass(frozen=True)
class Bill:
    """A call's cost, `None` when not fully known, and the price of each kind it used."""

    cost: float | None
    lines: tuple[BillLine, ...] = ()


def bill(usage: TokenUsage, prices: PriceBook | None) -> Bill:
    """The call's cost in USD: uncached input, cached reads, cache writes and output, each at its
    own price.

    A cached kind with no price of its own is billed at the input price, which can only overstate;
    an unknown cached count bills the whole prompt as uncached. Unknown is never reported as 0: a
    free model and an unpriced one are different facts.
    """
    if prices is None:
        return Bill(None)
    prompt = usage.prompt_tokens
    price_in = prices.price_for(TokenKind.INPUT, prompt)
    price_out = prices.price_for(TokenKind.OUTPUT, prompt)
    if price_in is None or price_out is None:
        return Bill(None)
    read = min(usage.cached_read_tokens or 0, prompt)
    write = min(usage.cache_write_tokens or 0, prompt - read)
    lines = [_line(price_in), _line(price_out)]
    cost = (prompt - read - write) * price_in.usd_per_million
    cost += usage.completion_tokens * price_out.usd_per_million
    for kind, count in ((TokenKind.CACHED_READ, read), (TokenKind.CACHE_WRITE, write)):
        if count:
            own = prices.price_for(kind, prompt)
            line = (
                _line(own)
                if own
                else BillLine(kind, price_in.usd_per_million, f"{price_in.source}, as input")
            )
            lines.append(line)
            cost += count * line.usd_per_million
    return Bill(round(cost / 1_000_000, 8), tuple(lines))


def _line(price: Price) -> BillLine:
    return BillLine(price.kind, price.usd_per_million, price.source)


def estimate_cost(usage: TokenUsage, prices: PriceBook | None) -> float | None:
    """The call's cost in USD, or `None` when the model's price is not fully known."""
    return bill(usage, prices).cost


def worst_cost(usage: TokenUsage, prices: PriceBook | None) -> float | None:
    """The most `usage` can cost: every prompt token at its highest price, cached or not."""
    price_in = prices.highest_prompt_price() if prices else None
    price_out = prices.default(TokenKind.OUTPUT) if prices else None
    if price_in is None or price_out is None:
        return None
    cost = usage.prompt_tokens * price_in + usage.completion_tokens * price_out.usd_per_million
    return round(cost / 1_000_000, 8)


def create_usage_record(
    config: GenerationConfig,
    response: LLMResponse,
    provider: str,
    project: str,
    duration_ms: int,
    prices: PriceBook | None = None,
    server: str = "",
) -> UsageRecord:
    """Build a ``UsageRecord`` from generation config and response.

    Args:
        config: The GenerationConfig used for the call (carries ``task_type``).
        response: The LLMResponse returned by the adapter.
        provider: Provider name (e.g. ``"gemini"``).
        project: Project name for grouping.
        duration_ms: Wall-clock time of the call in milliseconds.
        prices: The requested model's price book; `None` if unknown.

    Returns:
        A fully populated ``UsageRecord``.
    """
    task_type = config.task_type if config.task_type else TaskType.UNKNOWN
    logger.debug(
        "Creating usage record for %r (model: %r, project: %r)",
        task_type,
        response.model,
        project,
    )
    billed = bill(response.usage, prices)

    return UsageRecord(
        timestamp=datetime.now(UTC).isoformat(),
        project_name=project,
        task_type=str(task_type),
        model=response.model,
        provider=provider,
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
        total_tokens=response.usage.total_tokens,
        estimated_cost_usd=billed.cost,
        duration_ms=duration_ms,
        run_id=config.run_id,
        server=server,
        dal_level=config.dal_level,
        step_name=config.step_name,
        billed=Billed(
            cached_read_tokens=response.usage.cached_read_tokens,
            cache_write_tokens=response.usage.cache_write_tokens,
            local=prices.local if prices else None,
            price_lines=[
                {
                    "kind": line.kind.value,
                    "usd_per_million": line.usd_per_million,
                    "source": line.source,
                }
                for line in billed.lines
            ],
        ),
    )
