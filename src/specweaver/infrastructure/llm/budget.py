# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The run's limits, and the check every call passes before it is sent."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from specweaver.core.config.llm_settings import format_money

if TYPE_CHECKING:
    from specweaver.core.config.llm_settings import Currency, ModelFacts

logger = logging.getLogger(__name__)

#: Share of a limit at which it warns, once.
_WARN_AT = 0.8

Unit = Literal["usd", "tokens"]


@dataclass(frozen=True)
class Limit:
    """One limit, named by the settings key that sets it."""

    key: str
    unit: Unit
    value: float


@dataclass(frozen=True)
class Cost:
    """What a call costs: money is `None` when its price is unknown."""

    usd: float | None
    tokens: int

    def amount(self, unit: Unit) -> float | None:
        return self.usd if unit == "usd" else self.tokens


@dataclass(frozen=True)
class CallScope:
    """The limits one call counts against, and the facts that price it."""

    limits: tuple[Limit, ...] = ()
    facts: ModelFacts | None = None


@dataclass(frozen=True)
class Reservation:
    """A call's worst case, held against its limits until the call is recorded."""

    amounts: dict[str, float] = field(default_factory=dict)


class BudgetExceededError(Exception):
    """The run must not send another request.

    Not an `LLMError`: retry loops that catch those must not retry this. Anything that catches it
    re-raises it.
    """

    def __init__(self, reason: str, *, setting: str) -> None:
        self.setting = setting
        super().__init__(
            f"LLM spend brake: {reason}. No further requests will be sent this run. "
            f"Raise `{setting}` in settings.toml if this run is legitimate."
        )


class SpendLimitReachedError(BudgetExceededError):
    """The next call could cross `limit`."""

    def __init__(self, limit: Limit, spent: float, reason: str) -> None:
        self.limit = limit
        self.spent = spent
        super().__init__(reason, setting=limit.key)


class SpendBudget:
    """Spent and reserved amounts of one run, per limit key."""

    def __init__(self, currency: Currency | None = None) -> None:
        self._currency = currency
        self._spent: defaultdict[str, float] = defaultdict(float)
        self._reserved: defaultdict[str, float] = defaultdict(float)
        self._warned: set[str] = set()

    def spent(self, key: str) -> float:
        return self._spent[key]

    def before_call(self, scope: CallScope, worst: Cost) -> Reservation:
        """Reserve the call's worst case, or refuse if it could cross a limit."""
        for limit in scope.limits:
            amount = worst.amount(limit.unit)
            if amount is None:
                raise SpendLimitReachedError(
                    limit,
                    self._spent[limit.key],
                    f"the model's price is unknown, so {limit.key} cannot be checked",
                )
            if self._spent[limit.key] + self._reserved[limit.key] + amount > limit.value:
                raise SpendLimitReachedError(
                    limit,
                    self._spent[limit.key],
                    f"{limit.key} would be crossed: {self._show(limit, self._spent[limit.key])} of "
                    f"{self._show(limit, limit.value)} spent, the next call may cost up to "
                    f"{self._show(limit, amount)}",
                )
        reservation = Reservation(
            {limit.key: worst.amount(limit.unit) or 0.0 for limit in scope.limits}
        )
        for key, amount in reservation.amounts.items():
            self._reserved[key] += amount
        return reservation

    def record(
        self, scope: CallScope, cost: Cost | None, reservation: Reservation | None = None
    ) -> None:
        """Add a finished call to its limits, releasing its reservation.

        An unknown cost (`None`, or money with no price) counts the reserved worst case.
        """
        held = reservation.amounts if reservation else {}
        for limit in scope.limits:
            reserved = held.get(limit.key, 0.0)
            amount = cost.amount(limit.unit) if cost else None
            self._reserved[limit.key] -= reserved
            self._spent[limit.key] += reserved if amount is None else amount
            self._warn(limit)

    def _warn(self, limit: Limit) -> None:
        spent = self._spent[limit.key]
        if limit.key in self._warned or spent < limit.value * _WARN_AT:
            return
        self._warned.add(limit.key)
        logger.warning(
            "LLM spend at %.0f%% of %s: %s of %s used this run",
            spent / limit.value * 100,
            limit.key,
            self._show(limit, spent),
            self._show(limit, limit.value),
        )

    def _show(self, limit: Limit, amount: float) -> str:
        if limit.unit == "usd":
            return format_money(amount, self._currency)
        return f"{amount:,.0f} tokens"
