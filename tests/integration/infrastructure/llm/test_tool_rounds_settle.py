# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every adapter's tool loop settles each round with the spend brake before the next is checked.

Proves: TECH-092 FR-5

The seam is each real adapter (its provider client faked) handing each round's usage to the real
collector's round hook, and the real budget settling it. Each round really costs USD 0.03 and
reserves USD 3.50 to 6.60 as its worst case: holding the finished rounds' worst cases crosses the
USD 7 limit at round 1; settled, three rounds fit and the loop ends at its round limit.

| Bucket | Case |
|---|---|
| Happy | Gemini, Anthropic, OpenAI and Mistral each run three rounds under the limit |
| Boundary | the loop's spent total is the three rounds' real cost, counted once |
| Degradation | the loop ends at its round limit, and that failure counts nothing twice |
| Hostile | not applicable — the provider answers are fixed doubles |
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from specweaver.core.config.llm_settings import ModelFacts
from specweaver.infrastructure.llm.budget import CallScope, Limit, SpendBudget
from specweaver.infrastructure.llm.collector import TelemetryCollector
from specweaver.infrastructure.llm.errors import ToolRoundsExceededError
from specweaver.infrastructure.llm.models import GenerationConfig, Message, Role, ToolDefinition
from specweaver.infrastructure.llm.prices import PriceBook

pytestmark = pytest.mark.integration

#: USD 1 per 1,000 tokens either way.
_FACTS = PriceBook.of(ModelFacts(usd_per_million_input=1000.0, usd_per_million_output=1000.0))
_RUN = Limit("brake.hosted_spend_per_run", "usd", 7.0)


def _call(name: str = "my_tool") -> MagicMock:
    call = MagicMock()
    call.id = "c1"
    call.name = name
    call.args = {}
    call.function.name = name
    call.function.arguments = "{}"
    return call


def _gemini() -> Any:
    from specweaver.infrastructure.llm.adapters.gemini import GeminiAdapter

    adapter = GeminiAdapter(api_key="key")
    meta = MagicMock(
        prompt_token_count=10,
        candidates_token_count=20,
        thoughts_token_count=0,
        total_token_count=30,
        cached_content_token_count=None,
    )
    response = MagicMock(text="", usage_metadata=meta, function_calls=[_call()])
    response.candidates = [MagicMock(content=MagicMock(), finish_reason="STOP")]
    adapter._client = MagicMock()
    adapter._client.aio.models.generate_content = AsyncMock(return_value=response)
    return adapter


def _anthropic() -> Any:
    from specweaver.infrastructure.llm.adapters.anthropic import AnthropicAdapter

    adapter = AnthropicAdapter(api_key="key")
    tool_use = MagicMock(type="tool_use", id="t1", input={})
    tool_use.name = "my_tool"
    message = MagicMock(content=[tool_use], stop_reason="tool_use")
    message.usage = MagicMock(
        input_tokens=10,
        output_tokens=20,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )
    adapter._client = MagicMock()
    adapter._client.messages.create = AsyncMock(return_value=message)
    return adapter


def _openai() -> Any:
    from specweaver.infrastructure.llm.adapters.openai import OpenAIAdapter

    adapter = OpenAIAdapter(api_key="key")
    asks = MagicMock(choices=[MagicMock(finish_reason="tool_calls")])
    asks.choices[0].message.content = ""
    asks.choices[0].message.tool_calls = [_call()]
    asks.usage = MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
    asks.usage.prompt_tokens_details = MagicMock(cached_tokens=0)
    adapter._client = MagicMock()
    adapter._client.chat.completions.create = AsyncMock(return_value=asks)
    return adapter


def _mistral() -> Any:
    from specweaver.infrastructure.llm.adapters.mistral import MistralAdapter

    adapter = MistralAdapter(api_key="key")
    choice = MagicMock(finish_reason="tool_calls")
    choice.message.content = ""
    choice.message.tool_calls = [_call()]
    message = MagicMock(choices=[choice])
    message.usage = MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
    adapter._client = MagicMock()
    adapter._client.chat.complete_async = AsyncMock(return_value=message)
    return adapter


@pytest.mark.parametrize("build", [_gemini, _anthropic, _openai, _mistral])
async def test_each_round_settles_so_three_rounds_fit_the_limit(build: Any) -> None:
    budget = SpendBudget()
    collector = TelemetryCollector(
        build(),
        "proj",
        prices=lambda _model: _FACTS,
        budget=budget,
        scope_of=lambda _config: CallScope(limits=(_RUN,), prices=_FACTS),
    )
    config = GenerationConfig(
        model="m",
        tools=[ToolDefinition(name="my_tool", description="d" * 8000)],
        max_tool_rounds=3,
        max_output_tokens=1000,
    )
    executor = AsyncMock()
    executor.execute.return_value = {"content": "x" * 5000}

    with pytest.raises(ToolRoundsExceededError):
        await collector.generate_with_tools(
            [Message(role=Role.USER, content="hi")], config, executor
        )

    assert budget.spent(_RUN.key) == pytest.approx(3 * 0.03)
