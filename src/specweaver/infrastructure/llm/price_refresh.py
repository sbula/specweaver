# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Prices from models.dev: its `api.json` entry for a model, as price rows.

models.dev gives prices, never cache rules; a downloaded cached price keeps the shipped list's rule
for its kind. A price that cannot be right — missing, zero, negative, not a number — is refused, and
the stored one stays.
"""

from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING, Any

from specweaver.infrastructure.llm.models import TokenKind
from specweaver.infrastructure.llm.prices import Price, Rule

if TYPE_CHECKING:
    from datetime import date

#: models.dev's name for each cost field.
_FIELDS = {
    "input": TokenKind.INPUT,
    "output": TokenKind.OUTPUT,
    "cache_read": TokenKind.CACHED_READ,
    "cache_write": TokenKind.CACHE_WRITE,
}
_NEEDED = (TokenKind.INPUT, TokenKind.OUTPUT)
#: A tier table, such as `context_over_200k`: its prices apply from that prompt length on.
_TIER = re.compile(r"context_over_(\d+)k")
SOURCE = "models.dev"


def downloaded_prices(
    entry: dict[str, Any], *, day: date, rules: dict[TokenKind, Rule | None]
) -> tuple[list[Price], list[str]]:
    """The entry's prices from `day`, and why each refused one was refused."""
    cost = entry.get("cost")
    if not isinstance(cost, dict):
        return [], [f"{entry.get('id', '?')}: no cost table"]
    rows, problems = _table(cost, day, rules, tier=None)
    for key, table in cost.items():
        match = _TIER.fullmatch(key)
        if match and isinstance(table, dict):
            tier_rows, tier_problems = _table(table, day, rules, tier=int(match[1]) * 1000)
            rows += tier_rows
            problems += [p for p in tier_problems if "missing" not in p]
    return rows, problems


def shipped_rules(prices: list[Price]) -> dict[TokenKind, Rule | None]:
    """Per kind, the rule of the shipped price a single downloaded one replaces: the untiered one
    with the shortest cache lifetime, as `PriceBook.price_for` picks."""
    rules: dict[TokenKind, Rule | None] = {}
    for kind in TokenKind:
        untiered = [
            p for p in prices if p.kind == kind and not (p.rule and p.rule.min_prompt_tokens)
        ]
        if untiered:
            first = min(untiered, key=lambda p: (p.rule.max_age_seconds or 0) if p.rule else 0)
            rules[kind] = first.rule
    return rules


def _table(
    table: dict[str, Any], day: date, rules: dict[TokenKind, Rule | None], *, tier: int | None
) -> tuple[list[Price], list[str]]:
    rows: list[Price] = []
    problems: list[str] = []
    for field, kind in _FIELDS.items():
        value = table.get(field)
        if value is None:
            if kind in _NEEDED:
                problems.append(f"{field}: missing")
            continue
        if isinstance(value, bool) or not isinstance(value, int | float):
            problems.append(f"{field}: {value!r} is not a price")
        elif not math.isfinite(value) or value <= 0:
            problems.append(f"{field}: {value} is not a price")
        else:
            rows.append(Price(kind, float(value), day, SOURCE, _rule(rules.get(kind), tier)))
    return rows, problems


def _rule(shipped: Rule | None, tier: int | None) -> Rule | None:
    if tier is None:
        return shipped
    base = shipped or Rule()
    return Rule(base.min_prefix_tokens, base.max_age_seconds, tier, base.requires)
