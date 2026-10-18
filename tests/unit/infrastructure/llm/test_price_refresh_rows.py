# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A models.dev entry becomes price rows; a price that cannot be right is refused, never stored.

Proves: TECH-074 FR-7, FR-8

The entry is shaped as models.dev's `api.json` writes it: provider → `models` → `cost`.

| Bucket | Case |
|---|---|
| Happy | input, output, cache read and cache write become rows from today, source `models.dev` |
| Boundary | a tier table becomes a special price with its prompt-length minimum; a cached price keeps the shipped rule |
| Degradation | a missing input or output price is refused and named; a missing cached price is simply absent |
| Hostile | zero, negative, text, infinite and boolean prices are refused |
"""

from __future__ import annotations

from datetime import date

import pytest

from specweaver.infrastructure.llm.models import TokenKind
from specweaver.infrastructure.llm.price_refresh import downloaded_prices, shipped_rules
from specweaver.infrastructure.llm.prices import Price, Rule

_TODAY = date(2026, 10, 18)
_CACHED = Rule(min_prefix_tokens=512, max_age_seconds=300, requires="breakpoint")
_RULES = {TokenKind.CACHED_READ: _CACHED}


def _rows(cost: dict) -> tuple[list[Price], list[str]]:
    return downloaded_prices({"id": "claude-opus-5-5", "cost": cost}, day=_TODAY, rules=_RULES)


def _by_kind(rows: list[Price]) -> dict[tuple[str, Rule | None], float]:
    return {(p.kind.value, p.rule): p.usd_per_million for p in rows}


def test_each_cost_field_becomes_a_row() -> None:
    rows, problems = _rows({"input": 4, "output": 20, "cache_read": 0.4, "cache_write": 5})

    assert problems == []
    assert _by_kind(rows) == {
        ("input", None): 4.0,
        ("output", None): 20.0,
        ("cached_read", _CACHED): 0.4,
        ("cache_write", None): 5.0,
    }
    assert {(p.valid_from, p.source) for p in rows} == {(_TODAY, "models.dev")}


def test_a_tier_becomes_a_special_price_with_its_minimum() -> None:
    rows, _ = _rows(
        {
            "input": 4,
            "output": 20,
            "cache_read": 0.4,
            "context_over_200k": {"input": 6, "cache_read": 0.6},
        }
    )

    assert _by_kind(rows)[("input", Rule(min_prompt_tokens=200_000))] == 6.0
    tier_read = Rule(
        min_prefix_tokens=512, max_age_seconds=300, requires="breakpoint", min_prompt_tokens=200_000
    )
    assert _by_kind(rows)[("cached_read", tier_read)] == 0.6


@pytest.mark.parametrize("missing", ["input", "output"])
def test_a_missing_input_or_output_is_refused(missing: str) -> None:
    cost = {"input": 4, "output": 20}
    del cost[missing]

    rows, problems = _rows(cost)

    assert missing not in {p.kind.value for p in rows}
    assert len(problems) == 1 and missing in problems[0]


def test_a_missing_cached_price_is_absent() -> None:
    rows, problems = _rows({"input": 4, "output": 20})

    assert problems == []
    assert {p.kind for p in rows} == {TokenKind.INPUT, TokenKind.OUTPUT}


@pytest.mark.parametrize("bad", [0, -1, "4", float("inf"), True])
def test_a_price_that_cannot_be_right_is_refused(bad: object) -> None:
    rows, problems = _rows({"input": bad, "output": 20})

    assert TokenKind.INPUT not in {p.kind for p in rows}
    assert len(problems) == 1 and "input" in problems[0]


def test_an_entry_without_a_cost_table_is_refused() -> None:
    rows, problems = downloaded_prices({"id": "x"}, day=_TODAY, rules={})

    assert rows == []
    assert problems


def test_the_shipped_rule_of_a_kind_is_its_shortest_lived_untiered_price() -> None:
    day = date(2026, 10, 17)
    shipped = [
        Price(TokenKind.INPUT, 4.0, day, "catalogue"),
        Price(TokenKind.CACHE_WRITE, 5.0, day, "catalogue"),
        Price(TokenKind.CACHE_WRITE, 8.0, day, "catalogue", Rule(max_age_seconds=3600)),
        Price(TokenKind.CACHED_READ, 0.2, day, "catalogue", _CACHED),
    ]

    assert shipped_rules(shipped) == {
        TokenKind.INPUT: None,
        TokenKind.CACHE_WRITE: None,
        TokenKind.CACHED_READ: _CACHED,
    }
