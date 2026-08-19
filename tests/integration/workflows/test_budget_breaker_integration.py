# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A spent budget stops a real reviewer driving a real collector.

Proves: B-FLOW-05 FR-3

`FR-3` is a seam requirement, and the seam is the point: the breaker is raised inside
`infrastructure.llm` and has to survive `workflows.review`, which wraps every LLM call in
`except Exception` and turns what it catches into a verdict.

The unit test for this hands `Reviewer` a stub that raises on call. That proves the re-raise but
not the chain — it never builds a `TelemetryCollector`, never spends a budget, and would stay
green if the collector stopped checking, if the ceiling never reached it, or if the two modules
disagreed about which exception type crosses the boundary.

Here the budget is spent by a real priced call through the real collector, and the refusal has to
travel out through the reviewer intact.
"""

from __future__ import annotations

from typing import Any

import pytest

from specweaver.infrastructure.llm.budget import BudgetExceededError, SpendBudget
from specweaver.infrastructure.llm.collector import TelemetryCollector
from specweaver.infrastructure.llm.models import GenerationConfig, LLMResponse, TokenUsage
from specweaver.infrastructure.llm.telemetry import CostEntry
from specweaver.workflows.review.reviewer import Reviewer, ReviewVerdict

pytestmark = pytest.mark.integration

#: One call costs $2 at these rates, so a $1 ceiling is spent by the first one.
PRICED = {"stub-model": CostEntry(1.0, 1.0)}


class _Adapter:
    provider_name = "stub"
    available = True

    def __init__(self) -> None:
        self.calls = 0

    def _answer(self) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            text="VERDICT: ACCEPTED\n- nothing [confidence: 90]\nfine.",
            model="stub-model",
            usage=TokenUsage(prompt_tokens=1000, completion_tokens=1000, total_tokens=2000),
        )

    async def generate(self, messages: Any, config: Any) -> LLMResponse:
        return self._answer()

    async def generate_with_tools(self, *args: Any, **kwargs: Any) -> LLMResponse:
        return self._answer()


def _reviewer(adapter: _Adapter, limit: float) -> Reviewer:
    collector = TelemetryCollector(
        adapter, "proj", cost_overrides=PRICED, budget=SpendBudget(limit_usd=limit)
    )
    return Reviewer(llm=collector, config=GenerationConfig(model="stub-model"))


async def test_the_first_review_succeeds_and_spends_the_budget() -> None:
    """The control, and the setup: without it the next test could pass by never working at all."""
    adapter = _Adapter()
    reviewer = _reviewer(adapter, limit=1.0)

    result = await reviewer._execute_review("prompt")

    assert result.verdict is ReviewVerdict.ACCEPTED
    assert adapter.calls == 1


async def test_the_next_review_is_refused_and_the_refusal_escapes_the_reviewer() -> None:
    adapter = _Adapter()
    reviewer = _reviewer(adapter, limit=1.0)
    await reviewer._execute_review("prompt")

    with pytest.raises(BudgetExceededError):
        await reviewer._execute_review("prompt")

    assert adapter.calls == 1, "a second request reached the provider after the budget was spent"


async def test_the_refusal_is_not_relabelled_as_a_review_outcome() -> None:
    """The failure this seam exists to prevent: `ERROR` reads as *the review found problems*, and
    the pipeline would carry on past a tripped breaker."""
    adapter = _Adapter()
    reviewer = _reviewer(adapter, limit=1.0)
    await reviewer._execute_review("prompt")

    try:
        await reviewer._execute_review("prompt")
    except BudgetExceededError as caught:
        assert "max_spend_usd" in str(caught)
    else:
        pytest.fail("the breaker was swallowed and turned into a verdict")


async def test_a_generous_budget_does_not_interfere() -> None:
    """The other control: a breaker that fired regardless would pass every assertion above."""
    adapter = _Adapter()
    reviewer = _reviewer(adapter, limit=1000.0)

    for _ in range(3):
        assert (await reviewer._execute_review("prompt")).verdict is ReviewVerdict.ACCEPTED

    assert adapter.calls == 3
