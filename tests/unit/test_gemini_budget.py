# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The nightly live run sends at most 20 Gemini requests, the free tier's daily quota.

Proves: B-FLOW-05 NFR-4

The budget counts at the SDK call, so a retry counts too. Once it is used, or Gemini says the quota
is used up, no further request is sent, and the live tests it stops are skipped with the reason
`provider quota`, not failed `[agreed 2026-10-14]`.

| Bucket | Case |
|---|---|
| Happy | 20 requests go out; each one reaches the real call |
| Boundary | the 21st is refused before it is sent |
| Degradation | a `RESOURCE_EXHAUSTED` answer stops the budget; a `503` does not |
| Hostile | a test that fails for its own reason, or sends nothing after the stop, is not skipped |
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from tests.e2e.gemini_budget import BudgetSpentError, GeminiBudget, as_quota_skip


def _sent(budget: GeminiBudget, n: int) -> list[int]:
    calls: list[int] = []

    async def real(self: object, *, n: int) -> int:
        calls.append(n)
        return n

    send = budget.wrap(real)
    for i in range(n):
        asyncio.run(send(None, n=i))
    return calls


def test_twenty_requests_reach_the_real_call() -> None:
    budget = GeminiBudget(20)
    assert _sent(budget, 20) == list(range(20))
    assert budget.used == 20 and budget.stopped is None


def test_the_twenty_first_is_not_sent() -> None:
    budget = GeminiBudget(20)
    _sent(budget, 20)
    with pytest.raises(BudgetSpentError):
        _sent(budget, 1)
    assert budget.used == 20
    assert "budget of 20" in str(budget.stopped)


@pytest.mark.parametrize(
    ("error", "stops"), [("429 RESOURCE_EXHAUSTED", True), ("503 UNAVAILABLE", False)]
)
def test_a_used_up_quota_stops_the_budget(error: str, stops: bool) -> None:
    budget = GeminiBudget(20)

    async def real(self: object) -> None:
        raise RuntimeError(error)

    with pytest.raises(RuntimeError):
        asyncio.run(budget.wrap(real)(None))
    assert (budget.stopped is not None) is stops
    if stops:
        with pytest.raises(BudgetSpentError):
            asyncio.run(budget.wrap(real)(None))
        assert budget.used == 1


def _report(failed: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        when="call", failed=failed, outcome="failed" if failed else "passed", longrepr="boom"
    )


def test_a_failure_the_budget_caused_becomes_a_quota_skip() -> None:
    report = _report()
    as_quota_skip(report, ("tests/x.py", 3), "used")
    assert report.outcome == "skipped"
    assert report.longrepr == ("tests/x.py", 3, "Skipped: provider quota: used")


@pytest.mark.parametrize(
    ("reason", "failed"), [(None, True), ("used", False)], ids=["no-hit", "passed"]
)
def test_other_results_stay_as_they_are(reason: str | None, failed: bool) -> None:
    report = _report(failed)
    outcome = report.outcome
    as_quota_skip(report, ("tests/x.py", 3), reason)
    assert report.outcome == outcome


def test_a_test_that_sends_nothing_after_the_stop_is_not_hit() -> None:
    budget = GeminiBudget(1)
    _sent(budget, 1)
    with pytest.raises(BudgetSpentError):
        _sent(budget, 1)
    mark = budget.mark()

    assert budget.hit_since(mark) is None
    with pytest.raises(BudgetSpentError):
        _sent(budget, 1)
    assert budget.hit_since(mark) == "the nightly budget of 1 Gemini requests is used"
