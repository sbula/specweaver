# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A tripped circuit breaker reaches the operator instead of being retried or relabelled.

Proves: B-FLOW-05 FR-3

This is the requirement that decides whether the capability is real. Three callers wrap an LLM
call in `except Exception`, and two of those are retry loops:

- `Planner.generate_plan` retries `max_retries` times;
- `ScenarioGenerator.generate_scenarios` does the same;
- `Reviewer._execute_review` converts any exception into a `ReviewVerdict.ERROR`.

A breaker they swallow is not a breaker. The run would keep going, the operator would be told
"plan generation failed after 3 attempts", and the actual cause — *you have spent your budget* —
would never be printed. The bill is the only thing that would say so.

The stub raises on the first call, which is exactly what a tripped `TelemetryCollector` does.
"""

from __future__ import annotations

from typing import Any

import pytest

from specweaver.infrastructure.llm.budget import BudgetExceededError


class _BrokenBudgetLLM:
    """Behaves as a collector whose budget is spent: every path refuses."""

    provider_name = "stub"
    available = True

    def __init__(self) -> None:
        self.attempts = 0

    def _refuse(self) -> Any:
        self.attempts += 1
        raise BudgetExceededError("this run has spent $9.99 of $9.99", setting="max_spend_usd")

    async def generate(self, *args: Any, **kwargs: Any) -> Any:
        return self._refuse()

    async def generate_with_tools(self, *args: Any, **kwargs: Any) -> Any:
        return self._refuse()


async def test_the_planner_does_not_retry_a_tripped_breaker() -> None:
    from specweaver.infrastructure.llm.prompt.builder import PromptBuilder
    from specweaver.workflows.planning.planner import Planner

    llm = _BrokenBudgetLLM()
    planner = Planner(llm=llm, max_retries=3)

    with pytest.raises(BudgetExceededError):
        await planner.generate_plan("spec", "spec.md", "spec", PromptBuilder())

    assert llm.attempts == 1, (
        f"the breaker was retried {llm.attempts} times — a spend limit that a retry loop "
        "swallows does not limit spend"
    )


async def test_the_scenario_generator_does_not_retry_a_tripped_breaker() -> None:
    from specweaver.workflows.scenarios.scenario_generator import ScenarioGenerator

    llm = _BrokenBudgetLLM()
    generator = ScenarioGenerator(llm=llm, max_retries=3)

    with pytest.raises(BudgetExceededError):
        await generator.generate_scenarios("spec", "contract", ["FR-1"])

    assert llm.attempts == 1


async def test_the_reviewer_does_not_relabel_a_tripped_breaker() -> None:
    """A verdict of ERROR reads as *the review found problems*, not *you are out of money*."""
    from specweaver.workflows.review.reviewer import Reviewer

    reviewer = Reviewer(llm=_BrokenBudgetLLM())

    with pytest.raises(BudgetExceededError):
        await reviewer._execute_review("prompt")


async def test_malformed_output_is_still_retried_by_the_planner() -> None:
    """The control. Without it, "the breaker propagates" would also be satisfied by a planner
    that had stopped retrying anything at all.

    The retry loop exists for malformed *content* — the LLM answering with something that is not
    the JSON it was asked for. Note that the call itself sits OUTSIDE the loop's `try`, so a
    raising adapter has never been retried; moving that call inside the `try` is the change this
    test and the two above would catch together.
    """
    from specweaver.infrastructure.llm.models import LLMResponse
    from specweaver.infrastructure.llm.prompt.builder import PromptBuilder
    from specweaver.workflows.planning.planner import Planner

    class _MalformedLLM:
        provider_name = "stub"

        def __init__(self) -> None:
            self.attempts = 0

        async def generate(self, *args: Any, **kwargs: Any) -> LLMResponse:
            self.attempts += 1
            return LLMResponse(text="not json at all", model="stub")

    llm = _MalformedLLM()
    planner = Planner(llm=llm, max_retries=3)

    with pytest.raises(ValueError, match="after 3 attempts"):
        await planner.generate_plan("spec", "spec.md", "spec", PromptBuilder())

    assert llm.attempts == 3, "malformed output must still be retried"
