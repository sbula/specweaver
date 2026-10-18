# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The prices of one model at one host, and the check that each call meets exactly one of them.

A price is the default for its token kind, or a special price that applies only while its rule
holds. A price holds from `valid_from` until a later row of the same kind and rule replaces it.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from specweaver.infrastructure.llm.models import TokenKind

if TYPE_CHECKING:
    from datetime import date

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
