# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The nightly live run's Gemini requests: at most 20, the free tier's daily quota.

`[agreed 2026-10-14]`: the key stays on the free tier. The budget counts at the SDK call, so a
retry counts as a request. Once it is used, or Gemini answers that the quota is used up, no further
request is sent, and the live tests it stops are skipped as `provider quota`, not failed.
"""

from __future__ import annotations

import typing

#: The free tier's requests a day for the model the live tests use.
REQUESTS_PER_NIGHT = 20

#: Gemini's answer when the day's quota is used up. A `503` is a busy model, not a used quota.
_QUOTA_USED = "RESOURCE_EXHAUSTED"


class BudgetSpentError(RuntimeError):
    """A request the budget did not send."""


class GeminiBudget:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.used = 0
        self.refused = 0
        self.stopped: str | None = None

    def _spend(self) -> None:
        if self.stopped is None and self.used >= self.limit:
            self.stopped = f"the nightly budget of {self.limit} Gemini requests is used"
        if self.stopped is not None:
            self.refused += 1
            raise BudgetSpentError(self.stopped)
        self.used += 1

    def wrap(self, real: typing.Callable[..., typing.Any]) -> typing.Callable[..., typing.Any]:
        """`real`, an async SDK method, sent only while the budget lasts."""

        async def send(self_: object, *args: object, **kwargs: object) -> object:
            self._spend()
            try:
                return await real(self_, *args, **kwargs)
            except Exception as exc:
                if _QUOTA_USED in str(exc):
                    self.stopped = "the free Gemini quota is used up"
                raise

        return send

    def mark(self) -> tuple[int, str | None]:
        return self.refused, self.stopped

    def hit_since(self, mark: tuple[int, str | None]) -> str | None:
        """Why a request since `mark` was refused or stopped the budget; None if none was."""
        return self.stopped if self.stopped is not None and self.mark() != mark else None


def as_quota_skip(report: typing.Any, location: tuple[str, int], reason: str | None) -> None:
    """Turn a test's failure into a skip when the budget refused or stopped one of its requests.

    A test that sends no request still runs, and still fails for its own reasons.
    """
    if report.when != "call" or not report.failed or reason is None:
        return
    report.outcome = "skipped"
    report.longrepr = (location[0], location[1], f"Skipped: provider quota: {reason}")


BUDGET = GeminiBudget(REQUESTS_PER_NIGHT)
