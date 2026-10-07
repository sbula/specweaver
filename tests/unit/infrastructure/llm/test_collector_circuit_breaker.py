# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""No request is sent whose worst case would cross a limit.

Proves: B-FLOW-05 FR-1, B-FLOW-05 FR-2

| Bucket | Case |
|---|---|
| Happy | a call within its limits reaches the adapter and its real cost is recorded |
| Boundary | the worst case counts the prompt with a 25% margin and the full output cap |
| Degradation | a call that fails counts the worst case it reserved; a stream counts its input |
| Hostile | a call whose worst case would cross is refused on every path, and nothing is sent |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from specweaver.core.config.llm_settings import ModelFacts
from specweaver.infrastructure.llm.budget import (
    CallScope,
    Cost,
    Limit,
    SpendBudget,
    SpendLimitReachedError,
)
from specweaver.infrastructure.llm.collector import TelemetryCollector
from specweaver.infrastructure.llm.models import (
    GenerationConfig,
    LLMResponse,
    Message,
    Role,
    TokenUsage,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class _StubAdapter:
    """Answers every call with 1,000 + 1,000 tokens, and counts the calls that reached it."""

    provider_name = "stub"
    available = True

    def __init__(self, fail: bool = False) -> None:
        self.calls = 0
        self._fail = fail

    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    def _answer(self) -> LLMResponse:
        self.calls += 1
        if self._fail:
            raise RuntimeError("provider down")
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


#: USD 1 per 1,000 tokens either way, so a worst case is easy to read off.
_FACTS = ModelFacts(usd_per_million_input=1000.0, usd_per_million_output=1000.0)
_RUN = Limit("brake.hosted_spend_per_run", "usd", 10.0)
_CONFIG = GenerationConfig(model="stub-model", max_output_tokens=1000)
#: 4,000 characters → 1,000 estimated tokens → 1,250 with the margin.
_PROMPT = [Message(role=Role.USER, content="x" * 4000)]


def _collector(adapter: _StubAdapter, budget: SpendBudget | None = None) -> TelemetryCollector:
    return TelemetryCollector(
        adapter,
        "proj",
        prices=lambda _model: _FACTS,
        budget=budget or SpendBudget(),
        scope_of=lambda _config: CallScope(limits=(_RUN,), facts=_FACTS),
    )


async def test_a_call_within_its_limits_reaches_the_adapter_and_counts_its_real_cost() -> None:
    adapter = _StubAdapter()
    collector = _collector(adapter)

    await collector.generate(_PROMPT, _CONFIG)

    assert adapter.calls == 1
    assert collector.budget.spent(_RUN.key) == pytest.approx(2.0)  # 2,000 real tokens


async def test_the_worst_case_counts_the_prompt_with_its_margin_and_the_full_output_cap() -> None:
    budget = SpendBudget()
    budget.record(CallScope(limits=(_RUN,)), _cost(7.75))  # 2.25 left: the worst case exactly
    adapter = _StubAdapter()

    await _collector(adapter, budget).generate(_PROMPT, _CONFIG)  # 1.25 + 1.0 = 2.25 passes

    assert adapter.calls == 1


async def test_a_worst_case_over_the_limit_sends_nothing() -> None:
    budget = SpendBudget()
    budget.record(CallScope(limits=(_RUN,)), _cost(7.76))
    adapter = _StubAdapter()

    with pytest.raises(SpendLimitReachedError):
        await _collector(adapter, budget).generate(_PROMPT, _CONFIG)

    assert adapter.calls == 0


@pytest.mark.parametrize("path", ["tools", "stream"])
async def test_every_path_is_checked_before_it_sends(path: str) -> None:
    budget = SpendBudget()
    budget.record(CallScope(limits=(_RUN,)), _cost(9.5))
    adapter = _StubAdapter()
    collector = _collector(adapter, budget)

    with pytest.raises(SpendLimitReachedError):
        if path == "tools":
            await collector.generate_with_tools(_PROMPT, _CONFIG, None)
        else:
            async for _ in collector.generate_stream(_PROMPT, _CONFIG):
                pass

    assert adapter.calls == 0


@pytest.mark.parametrize("path", ["plain", "tools"])
async def test_a_failed_call_counts_the_worst_case_it_reserved(path: str) -> None:
    collector = _collector(_StubAdapter(fail=True))

    with pytest.raises(RuntimeError):
        if path == "plain":
            await collector.generate(_PROMPT, _CONFIG)
        else:
            await collector.generate_with_tools(_PROMPT, _CONFIG, None)

    assert collector.budget.spent(_RUN.key) == pytest.approx(2.25)


async def test_a_stream_counts_its_input_tokens() -> None:
    collector = _collector(_StubAdapter())

    async for _ in collector.generate_stream(_PROMPT, _CONFIG):
        pass

    assert collector.records[0].prompt_tokens == 1000  # estimated from the 4,000-char prompt


async def test_a_collector_without_limits_never_refuses() -> None:
    adapter = _StubAdapter()
    collector = TelemetryCollector(adapter, "proj")

    for _ in range(3):
        await collector.generate(_PROMPT, _CONFIG)

    assert adapter.calls == 3
    assert len(collector.records) == 3


def _cost(usd: float) -> Cost:
    return Cost(usd=usd, tokens=0)


class _LoopingAdapter(_StubAdapter):
    """A tool loop of `rounds` requests, asking the round hook first each time like the adapters."""

    def __init__(self, rounds: int, fail_in: int | None = None) -> None:
        super().__init__()
        self._rounds = rounds
        self._fail_in = fail_in

    async def generate_with_tools(
        self, messages: Any, config: Any, tool_executor: Any = None, on_tool_round: Any = None
    ) -> LLMResponse:
        used = TokenUsage()
        try:
            for round_num in range(self._rounds):
                if on_tool_round:
                    on_tool_round(round_num, messages)
                if round_num == self._fail_in:
                    raise RuntimeError("provider down")
                self.calls += 1
                used = used + TokenUsage(prompt_tokens=100, completion_tokens=100, total_tokens=200)
        except BaseException as exc:
            exc.usage = used  # type: ignore[attr-defined]
            raise
        return LLMResponse(text="ok", model="stub-model", usage=used)


async def test_every_tool_round_is_checked_before_its_request() -> None:
    budget = SpendBudget()
    budget.record(CallScope(limits=(_RUN,)), _cost(2.0))  # room for three worst cases of 2.25
    adapter = _LoopingAdapter(rounds=5)

    with pytest.raises(SpendLimitReachedError):
        await _collector(adapter, budget).generate_with_tools(_PROMPT, _CONFIG, None)

    assert adapter.calls == 3


async def test_a_finished_tool_loop_counts_its_real_usage_not_its_reservations() -> None:
    collector = _collector(_LoopingAdapter(rounds=3))

    await collector.generate_with_tools(_PROMPT, _CONFIG, None)

    assert collector.budget.spent(_RUN.key) == pytest.approx(0.6)  # 3 rounds of 200 tokens
    collector.budget.before_call(CallScope(limits=(_RUN,)), _cost(9.4))  # nothing still held


async def test_a_tool_loop_that_fails_partway_counts_the_rounds_it_ran() -> None:
    collector = _collector(_LoopingAdapter(rounds=5, fail_in=2))

    with pytest.raises(RuntimeError):
        await collector.generate_with_tools(_PROMPT, _CONFIG, None)

    assert collector.budget.spent(_RUN.key) == pytest.approx(0.4)  # rounds 0 and 1
