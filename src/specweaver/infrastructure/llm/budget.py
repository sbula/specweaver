# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The run's limits, and the check every call passes before it is sent."""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, NoReturn

from specweaver.core.config.llm_settings import format_money

if TYPE_CHECKING:
    from collections.abc import Callable

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

    @classmethod
    def combined(cls, reservations: list[Reservation]) -> Reservation:
        total: defaultdict[str, float] = defaultdict(float)
        for reservation in reservations:
            for key, amount in reservation.amounts.items():
                total[key] += amount
        return cls(dict(total))


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


#: The refusals of the step running in this task; tasks it starts share the same list.
_step_refusals: ContextVar[list[SpendLimitReachedError] | None] = ContextVar(
    "step_refusals", default=None
)


def track_step_refusals() -> None:
    """Start collecting the refusals of the step this task runs, apart from its siblings'."""
    _step_refusals.set([])


def step_refusal() -> SpendLimitReachedError | None:
    """The last refusal of the step this task runs, if one of its calls was refused."""
    refusals = _step_refusals.get()
    return refusals[-1] if refusals else None


def _refused(error: SpendLimitReachedError) -> NoReturn:
    refusals = _step_refusals.get()
    if refusals is not None:
        refusals.append(error)
    raise error


class SpendBudget:
    """Spent and reserved amounts of one run, per limit key."""

    def __init__(
        self, currency: Currency | None = None, ask: Callable[[str], bool] | None = None
    ) -> None:
        self._currency = currency
        self._ask = ask
        self._spent: defaultdict[str, float] = defaultdict(float)
        self._reserved: defaultdict[str, float] = defaultdict(float)
        self._raised: defaultdict[str, float] = defaultdict(float)
        self._floor: dict[str, float] = {}
        self._values: dict[str, float] = {}
        #: The limit each key last warned at; a raised limit warns again.
        self._warned: dict[str, float] = {}
        #: The stop that ended the run's spending, if any.
        self.stopped: SpendLimitReachedError | None = None

    def spent(self, key: str) -> float:
        return self._spent[key]

    def limit_of(self, limit: Limit) -> float:
        """The limit as it stands now: raised by every "yes", and never below a resumed run's."""
        self._values[limit.key] = limit.value
        return max(limit.value + self._raised[limit.key], self._floor.get(limit.key, 0.0))

    def snapshot(self) -> dict[str, dict[str, float]]:
        """What a parked run keeps: its spending, and each limit as it stood."""
        return {
            "spent": dict(self._spent),
            "limits": {
                **self._floor,
                **{
                    key: max(value + self._raised[key], self._floor.get(key, 0.0))
                    for key, value in self._values.items()
                },
            },
        }

    def restore(self, state: dict[str, dict[str, float]]) -> None:
        """Continue a resumed run from its snapshot."""
        self._spent.update(state.get("spent", {}))
        self._floor.update(state.get("limits", {}))

    def before_call(self, scope: CallScope, worst: Cost) -> Reservation:
        """Reserve the call's worst case, or refuse if it could cross a limit.

        Once a call was refused, the run spends nothing more and asks nothing more.
        """
        if self.stopped is not None:
            _refused(self.stopped)
        raises: dict[str, float] = {}
        for limit in scope.limits:
            amount = worst.amount(limit.unit)
            if amount is None:
                self._stop(limit, f"the model's price is unknown, so {limit.key} cannot be checked")
            needed = self._spent[limit.key] + self._reserved[limit.key] + amount
            if needed > self.limit_of(limit):
                reason = (
                    f"{limit.key} would be crossed: {self._show(limit, self._spent[limit.key])} of "
                    f"{self._show(limit, self.limit_of(limit))} spent, the next call may cost up to "
                    f"{self._show(limit, amount)}"
                )
                steps = math.ceil((needed - self.limit_of(limit)) / limit.value)
                raised = self._show(limit, self.limit_of(limit) + steps * limit.value)
                if self._ask is None or not self._ask(f"{reason}. Continue up to {raised}?"):
                    self._stop(limit, reason)
                raises[limit.key] = steps * limit.value
        for key, amount in raises.items():
            self._raised[key] += amount
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

    def _stop(self, limit: Limit, reason: str) -> NoReturn:
        self.stopped = SpendLimitReachedError(limit, self._spent[limit.key], reason)
        _refused(self.stopped)

    def _warn(self, limit: Limit) -> None:
        spent = self._spent[limit.key]
        current = self.limit_of(limit)
        if self._warned.get(limit.key) == current or spent < current * _WARN_AT:
            return
        self._warned[limit.key] = current
        logger.warning(
            "LLM spend at %.0f%% of %s: %s of %s used this run",
            spent / current * 100,
            limit.key,
            self._show(limit, spent),
            self._show(limit, current),
        )

    def _show(self, limit: Limit, amount: float) -> str:
        if limit.unit == "usd":
            return format_money(amount, self._currency)
        return f"{amount:,.0f} tokens"
