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

from specweaver.core.config.llm_settings import ModelFacts
from specweaver.infrastructure.llm.budget import BudgetExceededError, CallScope, Limit, SpendBudget
from specweaver.infrastructure.llm.collector import TelemetryCollector
from specweaver.infrastructure.llm.models import GenerationConfig, LLMResponse, TokenUsage
from specweaver.infrastructure.llm.prices import PriceBook
from specweaver.workflows.review.reviewer import Reviewer, ReviewVerdict

pytestmark = pytest.mark.integration

#: One call costs USD 2 at these rates; its worst case before sending is about USD 1, the
#: 1,000-token output cap. A USD 2.50 limit lets the first through and stops the second.
PRICED = {
    "stub-model": PriceBook.of(
        ModelFacts(usd_per_million_input=1000.0, usd_per_million_output=1000.0)
    )
}


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
    run = Limit("brake.hosted_spend_per_run", "usd", limit)
    collector = TelemetryCollector(
        adapter,
        "proj",
        prices=PRICED.get,
        budget=SpendBudget(),
        scope_of=lambda _config: CallScope(limits=(run,), prices=PRICED["stub-model"]),
    )
    return Reviewer(
        llm=collector, config=GenerationConfig(model="stub-model", max_output_tokens=1000)
    )


async def test_the_next_review_is_refused_and_the_refusal_escapes_the_reviewer() -> None:
    adapter = _Adapter()
    reviewer = _reviewer(adapter, limit=2.5)
    await reviewer._execute_review("prompt")

    with pytest.raises(BudgetExceededError):
        await reviewer._execute_review("prompt")

    assert adapter.calls == 1, "a second request reached the provider after the budget was spent"


async def test_a_generous_budget_does_not_interfere() -> None:
    """The other control: a breaker that fired regardless would pass every assertion above."""
    adapter = _Adapter()
    reviewer = _reviewer(adapter, limit=1000.0)

    for _ in range(3):
        assert (await reviewer._execute_review("prompt")).verdict is ReviewVerdict.ACCEPTED

    assert adapter.calls == 3
