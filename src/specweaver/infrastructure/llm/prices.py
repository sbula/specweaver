# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The prices of one model at one host, and the check that each call meets exactly one of them.

A price is the default for its token kind, or a special price that applies only while its rule
holds. A price holds from `valid_from` until a later row of the same kind and rule replaces it.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from typing import TYPE_CHECKING

from specweaver.infrastructure.llm.models import TokenKind

if TYPE_CHECKING:
    from specweaver.core.config.llm_settings import ModelFacts

REQUIREMENTS: frozenset[str] = frozenset({"nothing", "breakpoint", "cache_key"})
#: Every hosted model needs these two; a cached kind with no price falls back to input.
_NEEDED = (TokenKind.INPUT, TokenKind.OUTPUT)


@dataclass(frozen=True)
class Rule:
    """What must be true for a special price to apply. `None` sets no condition."""

    min_prefix_tokens: int | None = None
    max_age_seconds: int | None = None
    min_prompt_tokens: int | None = None
    requires: str = "nothing"

    def sets_a_condition(self) -> bool:
        limits = (self.min_prefix_tokens, self.max_age_seconds, self.min_prompt_tokens)
        return any(limit is not None for limit in limits) or self.requires != "nothing"


@dataclass(frozen=True)
class Price:
    kind: TokenKind
    usd_per_million: float
    valid_from: date
    source: str
    rule: Rule | None = None


def check_prices(prices: list[Price], *, local: bool) -> list[str]:
    """Each way `prices` breaks the exactly-one check, for one model at one host; empty when none.

    A local offering costs nothing to call, so it has no prices at all.
    """
    if local:
        return ["a local model has no prices"] if prices else []
    problems = [_rule_problem(p.kind, p.rule) for p in prices if p.rule is not None]
    problems += [
        f"{p.kind.value}: a negative price or not a number, {p.usd_per_million}"
        for p in prices
        if p.usd_per_million < 0 or not math.isfinite(p.usd_per_million)
    ]
    same = Counter((p.kind, p.rule, p.valid_from) for p in prices)
    problems += [
        f"{kind.value}: two {'defaults' if rule is None else 'special prices with one rule'} "
        f"from {day}"
        for (kind, rule, day), count in same.items()
        if count > 1
    ]
    problems += _gaps(prices)
    return [problem for problem in problems if problem]


def _rule_problem(kind: TokenKind, rule: Rule) -> str:
    if rule.requires not in REQUIREMENTS:
        return f"{kind.value}: requires {rule.requires!r}, not one of {sorted(REQUIREMENTS)}"
    if not rule.sets_a_condition():
        return f"{kind.value}: a special price whose rule sets no condition"
    return ""


def _gaps(prices: list[Price]) -> list[str]:
    """Each needed default missing at a time some price of this model already holds."""
    starts = {kind: _first_default(prices, kind) for kind in _NEEDED}
    problems = [f"{kind.value}: no default price" for kind, day in starts.items() if day is None]
    earliest = min((p.valid_from for p in prices), default=None)
    for kind, day in starts.items():
        if day is not None and earliest is not None and earliest < day:
            problems.append(f"{kind.value}: no default price from {earliest} until {day}")
    return problems


def _first_default(prices: list[Price], kind: TokenKind) -> date | None:
    return min((p.valid_from for p in prices if p.kind == kind and p.rule is None), default=None)


#: The settings-file field that sets each kind's price.
SETTING_OF = {
    TokenKind.INPUT: "usd_per_million_input",
    TokenKind.OUTPUT: "usd_per_million_output",
    TokenKind.CACHED_READ: "usd_per_million_cached_read",
    TokenKind.CACHE_WRITE: "usd_per_million_cache_write",
}


@dataclass(frozen=True)
class PriceBook:
    """The prices of one model at one host. A local model has none: its cost is not applicable."""

    prices: tuple[Price, ...]
    local: bool

    def current(self, kind: TokenKind, today: date | None = None) -> list[Price]:
        """The prices of `kind` that hold today: the newest per rule."""
        day = today or date.today()
        newest: dict[Rule | None, Price] = {}
        for price in self.prices:
            if price.kind != kind or price.valid_from > day:
                continue
            held = newest.get(price.rule)
            if held is None or price.valid_from > held.valid_from:
                newest[price.rule] = price
        return list(newest.values())

    def default(self, kind: TokenKind) -> Price | None:
        return next((p for p in self.current(kind) if p.rule is None), None)

    def price_for(self, kind: TokenKind, prompt_tokens: int) -> Price | None:
        """The price of `kind` for a call with this prompt: the highest prompt-length tier it
        reaches, and of those the shortest cache lifetime, as no call asks for a longer one yet.

        A cached count the provider reported already met its rule, so the rule's cache conditions
        are not checked again here.
        """
        fits = [p for p in self.current(kind) if _tier(p) <= prompt_tokens]
        return max(fits, key=lambda p: (_tier(p), -_lifetime(p)), default=None)

    def highest_prompt_price(self) -> float | None:
        """The most a prompt token can cost: uncached, read from or written to a cache. `None`
        while the input price is unknown."""
        if self.default(TokenKind.INPUT) is None:
            return None
        kinds = (TokenKind.INPUT, TokenKind.CACHED_READ, TokenKind.CACHE_WRITE)
        return max(p.usd_per_million for kind in kinds for p in self.current(kind))

    @classmethod
    def of(cls, facts: ModelFacts) -> PriceBook:
        """A hosted model's book holding only the prices `facts` sets."""
        return cls((), local=False).with_settings(facts)

    def with_settings(self, facts: ModelFacts | None) -> PriceBook:
        """Each price the settings file sets replaces every price of its kind, rules included."""
        if facts is None:
            return self
        own = {
            kind: value
            for kind, field in SETTING_OF.items()
            if (value := getattr(facts, field)) is not None
        }
        kept = [p for p in self.prices if p.kind not in own]
        mine = [Price(kind, usd, date.min, "settings") for kind, usd in own.items()]
        return replace(self, prices=(*kept, *mine))


def _tier(price: Price) -> int:
    return (price.rule.min_prompt_tokens or 0) if price.rule else 0


def _lifetime(price: Price) -> int:
    return (price.rule.max_age_seconds or 0) if price.rule else 0


def rule_break(rule: Rule, *, prompt_tokens: int, sent: frozenset[str] = frozenset()) -> str:
    """Why a cached read breaks `rule`, or "" when it does not: a prefix under the rule's minimum,
    or a cache without the breakpoint or key the rule requires, of which `sent` names what the
    request did send."""
    if rule.min_prefix_tokens is not None and prompt_tokens < rule.min_prefix_tokens:
        return f"a {prompt_tokens}-token prompt is under its minimum prefix of {rule.min_prefix_tokens}"
    if rule.requires != "nothing" and rule.requires not in sent:
        return f"it requires a {rule.requires.replace('_', ' ')}, which the request did not send"
    return ""
