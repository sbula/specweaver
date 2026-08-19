# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A run cannot spend without limit.

Proves: B-FLOW-05 FR-1, B-FLOW-05 FR-4, B-FLOW-05 FR-5, B-FLOW-05 NFR-1

Economic denial of service is the failure this prevents: a loop that never terminates bills until
somebody notices. The engine has three live loops — the autonomous flow, the dual-pipeline
verification round, and the reflection retries inside `Planner` and `ScenarioGenerator` — and until
now the only guard on any of them was `max_retries`, which counts attempts and not money. A step
that retries three times with a 200k-token prompt costs the same as thirty cheap ones.

`TokenBudget` is a different thing and does not overlap: it bounds ONE prompt so it fits a context
window. This bounds a whole run so it fits a wallet.
"""

from __future__ import annotations

import pytest

from specweaver.infrastructure.llm.budget import BudgetExceededError, SpendBudget


def test_a_fresh_budget_permits_a_call() -> None:
    assert SpendBudget(limit_usd=1.0).exceeded is False


def test_spend_accumulates() -> None:
    budget = SpendBudget(limit_usd=1.0)

    budget.record(0.30)
    budget.record(0.20)

    assert budget.spent_usd == pytest.approx(0.50)


def test_the_budget_trips_when_the_limit_is_reached() -> None:
    budget = SpendBudget(limit_usd=1.0)

    budget.record(1.0)

    assert budget.exceeded is True


def test_the_budget_does_not_trip_below_the_limit() -> None:
    """The control. A breaker that trips early stops legitimate work and gets switched off."""
    budget = SpendBudget(limit_usd=1.0)

    budget.record(0.99)

    assert budget.exceeded is False


def test_checking_a_tripped_budget_raises() -> None:
    """FR-1 into FR-2: the check is what refuses, so it must be an error, not a boolean nobody reads."""
    budget = SpendBudget(limit_usd=1.0)
    budget.record(1.5)

    with pytest.raises(BudgetExceededError) as caught:
        budget.check()

    assert "1.50" in str(caught.value)
    assert "1.00" in str(caught.value)


def test_checking_an_untripped_budget_is_silent() -> None:
    """The control for `check`. One that always raised would stop the first call of every run."""
    SpendBudget(limit_usd=1.0).check()


def test_a_disabled_budget_never_trips() -> None:
    """FR-5. Disabling is deliberate and explicit — `None`, not a zero somebody typed by mistake."""
    budget = SpendBudget(limit_usd=None)

    budget.record(1_000_000.0)

    assert budget.exceeded is False
    budget.check()


def test_a_zero_limit_refuses_everything_rather_than_meaning_unlimited() -> None:
    """`0` is the value a careless config produces. It must fail closed, not open."""
    budget = SpendBudget(limit_usd=0.0)

    assert budget.exceeded is True


def test_a_warning_fires_before_the_limit(caplog: pytest.LogCaptureFixture) -> None:
    """FR-4. A long run should be savable while it still can be — after the trip it is too late."""
    budget = SpendBudget(limit_usd=1.0)

    with caplog.at_level("WARNING"):
        budget.record(0.85)

    assert any("85" in record.message or "0.85" in record.message for record in caplog.records)


def test_no_warning_well_below_the_limit(caplog: pytest.LogCaptureFixture) -> None:
    """The control for FR-4. A warning on every call is a warning nobody reads."""
    budget = SpendBudget(limit_usd=1.0)

    with caplog.at_level("WARNING"):
        budget.record(0.10)

    assert caplog.records == []


def test_the_warning_fires_once_not_on_every_later_call(caplog: pytest.LogCaptureFixture) -> None:
    """A warning repeated per call is noise, and noise is how the real one gets missed."""
    budget = SpendBudget(limit_usd=1.0)
    budget.record(0.85)
    caplog.clear()

    with caplog.at_level("WARNING"):
        budget.record(0.01)
        budget.record(0.01)

    assert caplog.records == []


class TestTokenCeiling:
    """A cost ceiling alone can be bypassed by a model nobody priced.

    `estimate_cost` returns `0.0` for any model absent from the cost table — it warns, but the
    budget still accrues nothing, so the breaker never trips. Pointing a config at a model name
    the table does not know is therefore an unbounded run, which is precisely the failure this
    capability exists to stop.

    Tokens come back from the provider on every response and need no price list, so they bound
    the case dollars cannot.
    """

    def test_a_run_trips_on_tokens_when_the_model_has_no_price(self) -> None:
        budget = SpendBudget(limit_usd=10.0, token_limit=1000)

        budget.record(0.0, tokens=1000)

        assert budget.exceeded is True

    def test_tokens_below_the_ceiling_do_not_trip(self) -> None:
        """The control."""
        budget = SpendBudget(limit_usd=10.0, token_limit=1000)

        budget.record(0.0, tokens=999)

        assert budget.exceeded is False

    def test_either_ceiling_trips_the_breaker(self) -> None:
        """Cost is still enforced when tokens are nowhere near their limit."""
        budget = SpendBudget(limit_usd=1.0, token_limit=1_000_000)

        budget.record(1.0, tokens=10)

        assert budget.exceeded is True

    def test_the_token_ceiling_can_be_disabled_on_its_own(self) -> None:
        budget = SpendBudget(limit_usd=10.0, token_limit=None)

        budget.record(0.0, tokens=10_000_000)

        assert budget.exceeded is False

    def test_the_error_names_the_ceiling_that_tripped(self) -> None:
        """Two ceilings means the operator must be told which one to raise."""
        budget = SpendBudget(limit_usd=10.0, token_limit=1000)
        budget.record(0.0, tokens=5000)

        with pytest.raises(BudgetExceededError) as caught:
            budget.check()

        assert "token" in str(caught.value).lower()
