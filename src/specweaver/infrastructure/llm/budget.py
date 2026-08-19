# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A spend ceiling for one run, and the error that stops it.

`TokenBudget` in `models.py` bounds a single prompt so it fits a context window. This bounds a
whole run so it fits a wallet. The two never interact.

The threat is economic denial of service: a loop that does not terminate bills until a human
notices. `max_retries` counts attempts, not money, and three attempts at a 200k-token prompt cost
what thirty cheap calls do.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Fraction of the limit that triggers the one-time warning.
_WARN_AT = 0.8


class BudgetExceededError(Exception):
    """The run has spent its budget and must not send another request.

    Deliberately **not** an `LLMError`. Several callers wrap an LLM call in a retry loop that
    catches broad exceptions, and a breaker those loops swallow is not a breaker — it would be
    retried, then reported as an unrelated generation failure. Anything that catches this must
    re-raise it; `tests/unit/test_budget_error_propagates.py` is what holds that line.
    """

    def __init__(self, reason: str, *, setting: str) -> None:
        self.setting = setting
        super().__init__(
            f"LLM circuit breaker tripped: {reason}. No further requests will be sent this run. "
            f"Raise or disable `llm.{setting}` if this run is legitimate."
        )


class SpendBudget:
    """Accumulated cost for one run, against a ceiling.

    `limit_usd=None` disables the breaker. That is spelled as `None` rather than `0` on purpose:
    zero is what a careless config produces, and it means *refuse everything*, not *allow
    everything*. Failing closed on a mistyped limit is recoverable; failing open is the bill.
    """

    def __init__(self, limit_usd: float | None, token_limit: int | None = None) -> None:
        self._limit_usd = limit_usd
        self._token_limit = token_limit
        self._spent_usd = 0.0
        self._tokens = 0
        self._warned = False

    @property
    def limit_usd(self) -> float | None:
        return self._limit_usd

    @property
    def token_limit(self) -> int | None:
        return self._token_limit

    @property
    def spent_usd(self) -> float:
        return self._spent_usd

    @property
    def tokens(self) -> int:
        return self._tokens

    @property
    def cost_exceeded(self) -> bool:
        return self._limit_usd is not None and self._spent_usd >= self._limit_usd

    @property
    def tokens_exceeded(self) -> bool:
        return self._token_limit is not None and self._tokens >= self._token_limit

    @property
    def exceeded(self) -> bool:
        return self.cost_exceeded or self.tokens_exceeded

    def record(self, cost_usd: float, tokens: int = 0) -> None:
        """Add a completed call's cost and tokens, warning once as a ceiling approaches."""
        self._spent_usd += cost_usd
        self._tokens += tokens
        if self._limit_usd is None or self._warned or self.exceeded:
            return
        if self._spent_usd >= self._limit_usd * _WARN_AT:
            self._warned = True
            logger.warning(
                "LLM spend at %.0f%% of budget: $%.2f of $%.2f used this run",
                self._spent_usd / self._limit_usd * 100,
                self._spent_usd,
                self._limit_usd,
            )

    def check(self) -> None:
        """Raise if this run has already spent its budget.

        Called *before* a request, never after: the cost of a call is known only once it returns,
        so the breaker cannot stop the call that crosses the line — it stops the next one.
        """
        if self.cost_exceeded:
            raise BudgetExceededError(
                f"this run has spent ${self._spent_usd:.2f} against a limit of "
                f"${self._limit_usd:.2f}",
                setting="max_spend_usd",
            )
        if self.tokens_exceeded:
            raise BudgetExceededError(
                f"this run has used {self._tokens:,} tokens against a limit of "
                f"{self._token_limit:,}",
                setting="max_tokens_per_run",
            )
