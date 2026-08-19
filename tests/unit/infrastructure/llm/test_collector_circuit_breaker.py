# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Once the budget is gone, the collector stops sending requests.

Proves: B-FLOW-05 FR-2

`TelemetryCollector` is where the breaker belongs. It already wraps every adapter — `factory.py`
puts it there for `sw implement`, both `sw review` paths, drift and the API — and it already sees
what each call cost. Nothing else in the stack sees both.

The three generation methods are tested separately on purpose. A breaker on `generate` alone leaves
`generate_with_tools` — the *most* expensive path, because a tool round trips repeatedly — wide
open, and every test of `generate` would still pass.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from specweaver.infrastructure.llm.budget import BudgetExceededError, SpendBudget
from specweaver.infrastructure.llm.collector import TelemetryCollector
from specweaver.infrastructure.llm.models import GenerationConfig, LLMResponse, TokenUsage
from specweaver.infrastructure.llm.telemetry import CostEntry

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class _StubAdapter:
    """Answers every call, and counts how many actually reached it."""

    provider_name = "stub"
    available = True

    def __init__(self) -> None:
        self.calls = 0

    def _answer(self) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            text="ok",
            model="stub-model",
            usage=TokenUsage(prompt_tokens=1000, completion_tokens=1000, total_tokens=2000),
        )

    async def generate(self, messages: Any, config: Any) -> LLMResponse:
        return self._answer()

    async def generate_with_tools(
        self, messages: Any, config: Any, tool_executor: Any = None, on_tool_round: Any = None
    ) -> LLMResponse:
        return self._answer()

    async def generate_stream(self, messages: Any, config: Any) -> AsyncIterator[str]:
        self._answer()
        yield "ok"


#: The stub model is absent from the shipped cost table, which prices it at $0.00. Naming a
#: rate here keeps these tests about the breaker rather than about what is in the table.
PRICED = {"stub-model": CostEntry(1.0, 1.0)}


def _collector(adapter: _StubAdapter, limit: float | None) -> TelemetryCollector:
    return TelemetryCollector(
        adapter, "proj", cost_overrides=PRICED, budget=SpendBudget(limit_usd=limit)
    )


CONFIG = GenerationConfig(model="stub-model")


async def test_a_call_within_budget_reaches_the_adapter() -> None:
    """The control, and the one that matters most: the breaker must not break normal work."""
    adapter = _StubAdapter()

    await _collector(adapter, 100.0).generate([], CONFIG)

    assert adapter.calls == 1


async def test_a_call_is_refused_once_the_budget_is_spent() -> None:
    adapter = _StubAdapter()
    collector = _collector(adapter, 100.0)
    collector.budget.record(100.0)

    with pytest.raises(BudgetExceededError):
        await collector.generate([], CONFIG)

    assert adapter.calls == 0, "the request was sent anyway — the breaker only reported"


async def test_the_tool_path_is_refused_too() -> None:
    """The expensive path. A tool call loops, so an unbroken one bills the most."""
    adapter = _StubAdapter()
    collector = _collector(adapter, 100.0)
    collector.budget.record(100.0)

    with pytest.raises(BudgetExceededError):
        await collector.generate_with_tools([], CONFIG, None)

    assert adapter.calls == 0


async def test_the_stream_path_is_refused_too() -> None:
    adapter = _StubAdapter()
    collector = _collector(adapter, 100.0)
    collector.budget.record(100.0)

    with pytest.raises(BudgetExceededError):
        async for _ in collector.generate_stream([], CONFIG):
            pass

    assert adapter.calls == 0


async def test_spend_from_a_real_call_counts_towards_the_limit() -> None:
    """FR-2 end to end: the collector must feed what it measured back into the budget.

    Without this the budget stays at zero for ever and never trips, and every test above still
    passes because they record by hand.
    """
    adapter = _StubAdapter()
    collector = _collector(adapter, 100.0)

    await collector.generate([], CONFIG)

    assert collector.budget.spent_usd > 0.0


async def test_an_unlimited_collector_never_refuses() -> None:
    """The control for FR-5 at the seam: no budget configured must behave exactly as before."""
    adapter = _StubAdapter()
    collector = TelemetryCollector(adapter, "proj")

    for _ in range(3):
        await collector.generate([], CONFIG)

    assert adapter.calls == 3


async def test_telemetry_is_still_recorded() -> None:
    """The breaker must not cost the feature it was bolted onto."""
    adapter = _StubAdapter()
    collector = _collector(adapter, 100.0)

    await collector.generate([], CONFIG)

    assert len(collector.records) == 1
