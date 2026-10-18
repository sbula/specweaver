# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A call's cost: each token kind at the price that applies to it.

Proves: TECH-074 FR-4

| Bucket | Case |
|---|---|
| Happy | uncached input, cached reads, cache writes and output each at their own price |
| Boundary | of several prices of one kind, the one whose rule fits the call: the prompt-length tier, and the shortest lifetime while none is asked for |
| Degradation | a cached kind with no price is billed at the input price; an unknown cached count bills the prompt as uncached |
| Hostile | cached counts larger than the prompt never make the uncached part negative |
"""

from __future__ import annotations

from datetime import date

import pytest

from specweaver.core.config.llm_settings import ModelFacts
from specweaver.infrastructure.llm.models import TokenKind, TokenUsage
from specweaver.infrastructure.llm.prices import Price, PriceBook, Rule
from specweaver.infrastructure.llm.telemetry import bill, estimate_cost

_BOOK = PriceBook.of(
    ModelFacts(
        usd_per_million_input=1000.0,
        usd_per_million_output=1000.0,
        usd_per_million_cached_read=100.0,
        usd_per_million_cache_write=1250.0,
    )
)
_DAY = date(2026, 10, 17)


def _usage(read: int | None, write: int | None, prompt: int = 10_000) -> TokenUsage:
    return TokenUsage(
        prompt_tokens=prompt,
        completion_tokens=10,
        total_tokens=prompt + 10,
        cached_read_tokens=read,
        cache_write_tokens=write,
    )


def test_each_kind_is_billed_at_its_own_price() -> None:
    cost = estimate_cost(_usage(read=8000, write=1000), _BOOK)

    # 1,000 uncached at 1,000 + 8,000 read at 100 + 1,000 written at 1,250 + 10 out at 1,000
    assert cost == pytest.approx((1_000_000 + 800_000 + 1_250_000 + 10_000) / 1e6)


def test_the_bill_lists_the_price_of_each_kind_it_used() -> None:
    lines = bill(_usage(read=8000, write=0), _BOOK).lines

    assert {(line.kind, line.usd_per_million) for line in lines} == {
        (TokenKind.INPUT, 1000.0),
        (TokenKind.CACHED_READ, 100.0),
        (TokenKind.OUTPUT, 1000.0),
    }


def test_a_cached_kind_without_a_price_is_billed_as_input() -> None:
    book = PriceBook.of(ModelFacts(usd_per_million_input=1000.0, usd_per_million_output=1000.0))

    result = bill(_usage(read=9000, write=0), book)

    assert result.cost == pytest.approx(10.01)
    [line] = [x for x in result.lines if x.kind == TokenKind.CACHED_READ]
    assert (line.usd_per_million, line.source) == (1000.0, "settings, as input")


def test_an_unknown_cached_count_bills_the_prompt_as_uncached() -> None:
    assert estimate_cost(_usage(read=None, write=None), _BOOK) == pytest.approx(10.01)


def test_counts_above_the_prompt_never_go_negative() -> None:
    cost = estimate_cost(_usage(read=20_000, write=0), _BOOK)

    assert cost is not None and cost >= 0


def _anthropic_write() -> PriceBook:
    prices = (
        Price(TokenKind.INPUT, 4.0, _DAY, "catalogue"),
        Price(TokenKind.OUTPUT, 20.0, _DAY, "catalogue"),
        Price(TokenKind.CACHE_WRITE, 8.0, _DAY, "catalogue", Rule(max_age_seconds=3600)),
        Price(TokenKind.CACHE_WRITE, 5.0, _DAY, "catalogue"),
        Price(TokenKind.INPUT, 6.0, _DAY, "catalogue", Rule(min_prompt_tokens=200_000)),
    )
    return PriceBook(prices, local=False)


def test_a_write_is_billed_at_the_shortest_lifetime_while_none_is_asked_for() -> None:
    price = _anthropic_write().price_for(TokenKind.CACHE_WRITE, prompt_tokens=1000)

    assert price is not None and price.usd_per_million == 5.0


def test_a_long_prompt_meets_its_tier() -> None:
    book = _anthropic_write()

    short = book.price_for(TokenKind.INPUT, prompt_tokens=1000)
    long = book.price_for(TokenKind.INPUT, prompt_tokens=250_000)

    assert (short and short.usd_per_million, long and long.usd_per_million) == (4.0, 6.0)
