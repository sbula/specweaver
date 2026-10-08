# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every call is counted against every limit of its scope, and checked before it is sent.

Proves: B-FLOW-05 FR-1, B-FLOW-05 FR-2, B-FLOW-05 FR-4, B-FLOW-05 FR-5, B-FLOW-05 NFR-1

| Bucket | Case |
|---|---|
| Happy | a call adds its money to money limits and its tokens to token limits |
| Boundary | a worst case landing exactly on a limit passes, one unit over is refused before the call |
| Degradation | a call whose price is unknown cannot be checked against a money limit and is refused |
| Hostile | of two limits on one call the lower stops it; parallel calls cannot share one headroom |
"""

from __future__ import annotations

from datetime import date

import pytest

from specweaver.core.config.llm_settings import Currency
from specweaver.infrastructure.llm.budget import (
    BudgetExceededError,
    CallScope,
    Cost,
    Limit,
    SpendBudget,
    SpendLimitReachedError,
)

_RUN_USD = Limit("brake.hosted_spend_per_run", "usd", 10.0)
_MODEL_USD = Limit('models."claude-sonnet-5".spend_per_run', "usd", 8.0)
_ROLE_USD = Limit("roles.review.spend_per_run", "usd", 2.0)
_RUN_TOKENS = Limit("brake.tokens_per_run", "tokens", 1000)


def _scope(*limits: Limit) -> CallScope:
    return CallScope(limits=limits)


class TestCounting:
    def test_money_goes_to_money_limits_and_tokens_to_token_limits(self) -> None:
        budget = SpendBudget()

        budget.record(_scope(_RUN_USD, _MODEL_USD), Cost(usd=1.5, tokens=300))
        budget.record(_scope(_RUN_TOKENS), Cost(usd=None, tokens=200))

        assert budget.spent(_RUN_USD.key) == pytest.approx(1.5)
        assert budget.spent(_MODEL_USD.key) == pytest.approx(1.5)
        assert budget.spent(_RUN_TOKENS.key) == 200

    def test_a_limit_outside_the_calls_scope_is_untouched(self) -> None:
        budget = SpendBudget()

        budget.record(_scope(_RUN_USD), Cost(usd=1.0, tokens=10))

        assert budget.spent(_ROLE_USD.key) == 0


class TestCheckBeforeTheCall:
    def test_a_worst_case_exactly_on_the_limit_passes(self) -> None:
        budget = SpendBudget()
        budget.record(_scope(_RUN_USD), Cost(usd=6.0, tokens=0))

        budget.before_call(_scope(_RUN_USD), Cost(usd=4.0, tokens=0))

    def test_a_worst_case_over_the_limit_is_refused_naming_it(self) -> None:
        budget = SpendBudget()
        budget.record(_scope(_RUN_TOKENS), Cost(usd=None, tokens=900))

        with pytest.raises(SpendLimitReachedError) as caught:
            budget.before_call(_scope(_RUN_TOKENS), Cost(usd=None, tokens=101))

        assert caught.value.limit == _RUN_TOKENS
        assert caught.value.spent == 900
        assert "brake.tokens_per_run" in str(caught.value)

    def test_the_stop_is_a_budget_error_that_handlers_must_let_through(self) -> None:
        assert issubclass(SpendLimitReachedError, BudgetExceededError)

    def test_the_lower_of_two_limits_stops_the_call(self) -> None:
        budget = SpendBudget()

        with pytest.raises(SpendLimitReachedError) as caught:
            budget.before_call(_scope(_RUN_USD, _MODEL_USD, _ROLE_USD), Cost(usd=3.0, tokens=0))

        assert caught.value.limit == _ROLE_USD

    def test_an_unknown_price_cannot_pass_a_money_limit(self) -> None:
        budget = SpendBudget()

        with pytest.raises(SpendLimitReachedError, match="price"):
            budget.before_call(_scope(_RUN_USD), Cost(usd=None, tokens=50))

    def test_an_unknown_price_does_not_matter_to_a_token_limit(self) -> None:
        SpendBudget().before_call(_scope(_RUN_TOKENS), Cost(usd=None, tokens=50))


class TestReservations:
    def test_parallel_calls_cannot_share_one_headroom(self) -> None:
        budget = SpendBudget()
        budget.before_call(_scope(_RUN_USD), Cost(usd=6.0, tokens=0))

        with pytest.raises(SpendLimitReachedError):
            budget.before_call(_scope(_RUN_USD), Cost(usd=6.0, tokens=0))

    def test_recording_a_call_replaces_its_reservation(self) -> None:
        budget = SpendBudget()
        reservation = budget.before_call(_scope(_RUN_USD), Cost(usd=6.0, tokens=0))

        budget.record(_scope(_RUN_USD), Cost(usd=2.0, tokens=0), reservation)

        budget.before_call(_scope(_RUN_USD), Cost(usd=6.0, tokens=0))
        assert budget.spent(_RUN_USD.key) == pytest.approx(2.0)

    def test_a_free_call_counts_zero_not_its_reservation(self) -> None:
        budget = SpendBudget()
        reservation = budget.before_call(_scope(_RUN_TOKENS), Cost(usd=None, tokens=500))

        budget.record(_scope(_RUN_TOKENS), Cost(usd=None, tokens=0), reservation)

        assert budget.spent(_RUN_TOKENS.key) == 0

    def test_an_unknown_cost_counts_its_reservation(self) -> None:
        budget = SpendBudget()
        reservation = budget.before_call(_scope(_RUN_TOKENS), Cost(usd=None, tokens=500))

        budget.record(_scope(_RUN_TOKENS), None, reservation)

        assert budget.spent(_RUN_TOKENS.key) == 500


class TestWarning:
    def test_each_limit_warns_once_at_80_percent(self, caplog: pytest.LogCaptureFixture) -> None:
        budget = SpendBudget()

        with caplog.at_level("WARNING"):
            budget.record(_scope(_RUN_USD, _MODEL_USD), Cost(usd=6.5, tokens=0))
            budget.record(_scope(_RUN_USD, _MODEL_USD), Cost(usd=1.6, tokens=0))

        warned = [r.message for r in caplog.records if "80%" in r.message or "%" in r.message]
        assert len(warned) == 2  # the model at 6.5 of 8, then the run at 8.1 of 10; once each
        assert any(_MODEL_USD.key in message for message in warned)
        assert any(_RUN_USD.key in message for message in warned)

    def test_a_raised_limit_warns_again_at_its_own_80_percent(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        budget = SpendBudget(ask=lambda _q: True)
        budget.record(_scope(_RUN_USD), Cost(usd=9.0, tokens=0))  # warns at 10
        budget.before_call(_scope(_RUN_USD), Cost(usd=2.0, tokens=0))  # raised to 20
        caplog.clear()

        with caplog.at_level("WARNING"):
            budget.record(_scope(_RUN_USD), Cost(usd=8.0, tokens=0))  # 17 of 20

        [warning] = [r.message for r in caplog.records]
        assert "85%" in warning
        assert "USD 20.00" in warning

    def test_no_warning_below_80_percent(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("WARNING"):
            SpendBudget().record(_scope(_RUN_USD), Cost(usd=7.9, tokens=0))

        assert caplog.records == []

    def test_money_is_shown_in_the_users_currency(self, caplog: pytest.LogCaptureFixture) -> None:
        chf = Currency(code="CHF", per_usd=0.8, rate_date=date(2026, 9, 26))
        budget = SpendBudget(currency=chf)

        with caplog.at_level("WARNING"):
            budget.record(_scope(_RUN_USD), Cost(usd=8.5, tokens=0))
        with pytest.raises(SpendLimitReachedError) as caught:
            budget.before_call(_scope(_RUN_USD), Cost(usd=2.0, tokens=0))

        assert "CHF 6.80 of CHF 8.00" in caplog.records[0].message
        assert "CHF 6.80" in str(caught.value)
        assert "$" not in str(caught.value)


class TestAsking:
    def test_one_yes_raises_by_as_many_steps_as_the_call_needs(self) -> None:
        asked: list[str] = []
        budget = SpendBudget(ask=lambda question: asked.append(question) or True)

        budget.before_call(_scope(_RUN_USD), Cost(usd=25.0, tokens=0))

        assert len(asked) == 1
        assert "USD 30.00" in asked[0]
        assert budget.limit_of(_RUN_USD) == 30.0

    def test_yes_raises_the_limit_by_its_own_value_and_the_call_goes_on(self) -> None:
        asked: list[str] = []
        budget = SpendBudget(ask=lambda question: asked.append(question) or True)
        budget.record(_scope(_RUN_USD), Cost(usd=9.0, tokens=0))

        budget.before_call(_scope(_RUN_USD), Cost(usd=2.0, tokens=0))

        assert len(asked) == 1
        assert "brake.hosted_spend_per_run" in asked[0]
        assert budget.limit_of(_RUN_USD) == 20.0

    def test_the_next_crossing_asks_again_at_the_raised_limit(self) -> None:
        answers = iter([True, True])
        asked: list[str] = []
        budget = SpendBudget(ask=lambda q: asked.append(q) or next(answers))
        budget.record(_scope(_RUN_USD), Cost(usd=9.0, tokens=0))
        budget.before_call(_scope(_RUN_USD), Cost(usd=2.0, tokens=0))  # 10 -> 20

        budget.record(_scope(_RUN_USD), Cost(usd=10.0, tokens=0))
        budget.before_call(_scope(_RUN_USD), Cost(usd=2.0, tokens=0))  # 20 -> 30

        assert len(asked) == 2
        assert budget.limit_of(_RUN_USD) == 30.0

    def test_no_stops_the_call_and_the_budget_remembers_it(self) -> None:
        budget = SpendBudget(ask=lambda _question: False)
        budget.record(_scope(_RUN_USD), Cost(usd=9.0, tokens=0))

        with pytest.raises(SpendLimitReachedError) as caught:
            budget.before_call(_scope(_RUN_USD), Cost(usd=2.0, tokens=0))

        assert budget.stopped is caught.value

    def test_the_question_names_what_running_calls_may_still_add(self) -> None:
        asked: list[str] = []
        budget = SpendBudget(ask=lambda q: asked.append(q) or False)
        budget.before_call(_scope(_RUN_USD), Cost(usd=7.0, tokens=0))  # still running

        with pytest.raises(SpendLimitReachedError):
            budget.before_call(_scope(_RUN_USD), Cost(usd=4.0, tokens=0))

        assert "USD 0.00 of USD 10.00 spent" in asked[0]
        assert "calls already running may add up to USD 7.00" in asked[0]

    def test_after_a_no_the_run_spends_nothing_more_and_asks_nothing(self) -> None:
        asked: list[str] = []
        budget = SpendBudget(ask=lambda q: asked.append(q) or False)
        budget.record(_scope(_RUN_USD), Cost(usd=9.0, tokens=0))
        with pytest.raises(SpendLimitReachedError) as first:
            budget.before_call(_scope(_RUN_USD), Cost(usd=2.0, tokens=0))

        for worst in (2.0, 0.5):
            with pytest.raises(SpendLimitReachedError) as again:
                budget.before_call(_scope(_RUN_USD), Cost(usd=worst, tokens=0))
            assert again.value is first.value

        assert len(asked) == 1

    def test_a_refused_call_keeps_no_raise_from_its_other_limits(self) -> None:
        answers = iter([True, False])
        budget = SpendBudget(ask=lambda _q: next(answers))
        budget.record(_scope(_ROLE_USD, _MODEL_USD), Cost(usd=1.9, tokens=0))

        with pytest.raises(SpendLimitReachedError):
            budget.before_call(_scope(_ROLE_USD, _MODEL_USD), Cost(usd=7.0, tokens=0))

        assert budget.limit_of(_ROLE_USD) == 2.0

    def test_without_anyone_to_ask_the_call_stops(self) -> None:
        budget = SpendBudget()
        budget.record(_scope(_RUN_USD), Cost(usd=9.0, tokens=0))

        with pytest.raises(SpendLimitReachedError):
            budget.before_call(_scope(_RUN_USD), Cost(usd=2.0, tokens=0))

        assert budget.stopped is not None

    def test_a_call_within_its_limits_asks_nothing(self) -> None:
        budget = SpendBudget(ask=lambda _question: pytest.fail("asked without a crossing"))

        budget.before_call(_scope(_RUN_USD), Cost(usd=2.0, tokens=0))

        assert budget.stopped is None

    def test_the_question_says_what_was_spent_and_what_the_call_may_add(self) -> None:
        asked: list[str] = []
        budget = SpendBudget(ask=lambda q: asked.append(q) or False)
        budget.record(_scope(_RUN_USD), Cost(usd=9.0, tokens=0))

        with pytest.raises(SpendLimitReachedError):
            budget.before_call(_scope(_RUN_USD), Cost(usd=2.0, tokens=0))

        assert "USD 9.00" in asked[0]
        assert "USD 10.00" in asked[0]
        assert "USD 2.00" in asked[0]


class TestSnapshot:
    def test_spent_and_raised_limits_survive_a_snapshot(self) -> None:
        budget = SpendBudget(ask=lambda _q: True)
        budget.record(_scope(_RUN_USD), Cost(usd=9.0, tokens=0))
        budget.before_call(_scope(_RUN_USD), Cost(usd=2.0, tokens=0))  # raised to 20

        restored = SpendBudget()
        restored.restore(budget.snapshot())

        assert restored.spent(_RUN_USD.key) == pytest.approx(9.0)
        assert restored.limit_of(_RUN_USD) == 20.0

    def test_a_higher_limit_in_the_file_wins_after_a_resume(self) -> None:
        budget = SpendBudget(ask=lambda _q: True)
        budget.record(_scope(_RUN_USD), Cost(usd=9.0, tokens=0))
        budget.before_call(_scope(_RUN_USD), Cost(usd=2.0, tokens=0))  # raised to 20
        restored = SpendBudget()
        restored.restore(budget.snapshot())

        assert restored.limit_of(Limit(_RUN_USD.key, "usd", 50.0)) == 50.0

    def test_a_lower_limit_in_the_file_does_not_undo_a_yes(self) -> None:
        budget = SpendBudget(ask=lambda _q: True)
        budget.record(_scope(_RUN_USD), Cost(usd=9.0, tokens=0))
        budget.before_call(_scope(_RUN_USD), Cost(usd=2.0, tokens=0))  # raised to 20
        restored = SpendBudget()
        restored.restore(budget.snapshot())

        assert restored.limit_of(Limit(_RUN_USD.key, "usd", 5.0)) == 20.0

    def test_a_raised_limit_not_touched_after_a_resume_stays_raised(self) -> None:
        budget = SpendBudget(ask=lambda _q: True)
        budget.record(_scope(_RUN_USD), Cost(usd=9.0, tokens=0))
        budget.before_call(_scope(_RUN_USD), Cost(usd=2.0, tokens=0))  # raised to 20
        resumed = SpendBudget()
        resumed.restore(budget.snapshot())
        resumed.record(_scope(_RUN_TOKENS), Cost(usd=None, tokens=10))  # only tokens touched

        again = SpendBudget()
        again.restore(resumed.snapshot())

        assert again.limit_of(_RUN_USD) == 20.0

    def test_an_empty_snapshot_restores_nothing(self) -> None:
        restored = SpendBudget()

        restored.restore({})

        assert restored.spent(_RUN_USD.key) == 0


class TestALimitCheckedOnSpend:
    """A step limit compares what the step really spent, not the next call's worst case."""

    _STEP = Limit("step_limits.review.review_it", "tokens", 100, on_spent=True)

    def test_a_large_worst_case_below_the_spend_asks_nothing(self) -> None:
        budget = SpendBudget(ask=lambda _q: pytest.fail("asked before the step spent its limit"))

        budget.before_call(_scope(self._STEP), Cost(usd=None, tokens=5000))

    def test_once_the_step_spent_its_limit_the_next_call_asks(self) -> None:
        asked: list[str] = []
        budget = SpendBudget(ask=lambda q: asked.append(q) or True)
        budget.record(_scope(self._STEP), Cost(usd=None, tokens=100))

        budget.before_call(_scope(self._STEP), Cost(usd=None, tokens=10))

        assert len(asked) == 1
        assert "step_limits.review.review_it" in asked[0]
        assert budget.limit_of(self._STEP) == 200

    def test_without_an_answer_a_spent_step_stops(self) -> None:
        budget = SpendBudget()
        budget.record(_scope(self._STEP), Cost(usd=None, tokens=150))

        with pytest.raises(SpendLimitReachedError):
            budget.before_call(_scope(self._STEP), Cost(usd=None, tokens=1))

    def test_a_yes_after_a_large_overshoot_leaves_room_for_the_next_call(self) -> None:
        budget = SpendBudget(ask=lambda _q: True)
        step = Limit("step_limits.review.review_it", "tokens", 10, on_spent=True)
        budget.record(_scope(step), Cost(usd=None, tokens=30))

        budget.before_call(_scope(step), Cost(usd=None, tokens=1))

        assert budget.limit_of(step) > 30

    def test_the_question_says_the_limit_is_reached_and_nothing_about_running_calls(
        self,
    ) -> None:
        asked: list[str] = []
        budget = SpendBudget(ask=lambda q: asked.append(q) or True)
        budget.before_call(_scope(self._STEP), Cost(usd=None, tokens=5))  # still running
        budget.record(_scope(self._STEP), Cost(usd=None, tokens=100))  # another call, done

        budget.before_call(_scope(self._STEP), Cost(usd=None, tokens=5))

        assert "is reached: 100 tokens of 100 tokens spent" in asked[0]
        assert not any("already running" in question for question in asked)

    def test_without_anyone_to_ask_the_stop_says_how_to_go_on(self) -> None:
        budget = SpendBudget()
        budget.record(_scope(self._STEP), Cost(usd=None, tokens=100))

        with pytest.raises(SpendLimitReachedError) as caught:
            budget.before_call(_scope(self._STEP), Cost(usd=None, tokens=1))

        assert "resume it from a terminal with `sw resume`" in str(caught.value)

    def test_an_unknown_price_is_not_called_a_reached_step_limit(self) -> None:
        step = Limit("step_limits.review.review_it", "usd", 1.0, on_spent=True)

        with pytest.raises(SpendLimitReachedError) as caught:
            SpendBudget().before_call(_scope(step), Cost(usd=None, tokens=10))

        assert "price is unknown" in str(caught.value)
        assert "similar steps" not in str(caught.value)
