# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A call's worst case counts everything sent: messages, tool schemas and the system instruction.

Proves: B-FLOW-05 FR-2

| Bucket | Case |
|---|---|
| Happy | a small call passes a token limit |
| Boundary | a long system instruction alone crosses the limit and the call is refused |
| Degradation | not applicable — the estimate needs no server |
| Hostile | not applicable — sizes come from the call, never from outside input |
"""

from __future__ import annotations

import pytest

from specweaver.infrastructure.llm.budget import (
    CallScope,
    Limit,
    SpendBudget,
    SpendLimitReachedError,
)
from specweaver.infrastructure.llm.collector import TelemetryCollector
from specweaver.infrastructure.llm.models import GenerationConfig, LLMResponse, Message, Role


class _Echo:
    provider_name = "fake"

    async def generate(self, _messages, config):
        return LLMResponse(text="ok", model=config.model)


def _collector() -> TelemetryCollector:
    scope = CallScope(limits=(Limit("brake.tokens_per_run", "tokens", 1000),))
    return TelemetryCollector(_Echo(), "p", budget=SpendBudget(), scope_of=lambda _c: scope)


async def test_a_small_call_passes() -> None:
    config = GenerationConfig(model="m", max_output_tokens=10, system_instruction="be brief")

    await _collector().generate([Message(role=Role.USER, content="hi")], config)


async def test_a_long_system_instruction_counts() -> None:
    config = GenerationConfig(model="m", max_output_tokens=10, system_instruction="s" * 8000)

    with pytest.raises(SpendLimitReachedError):
        await _collector().generate([Message(role=Role.USER, content="hi")], config)
