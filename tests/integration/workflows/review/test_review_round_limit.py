# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A review whose model never stops calling tools ends as a failed review that names the limit.

Proves: C-FLOW-13 FR-17

The seam: the adapter raises at `brake.agent_turns`, the `Reviewer` turns that into the result the
user reads. Before, the adapter returned the text "Max tool rounds exceeded." as the model's answer,
and the review parsed it like any other.

| Bucket | Case |
|---|---|
| Happy | not applicable — a review that finishes is proven elsewhere |
| Boundary | the model asks for a tool on every one of the allowed rounds |
| Degradation | the review is ERROR, and its summary names `brake.agent_turns` |
| Hostile | not applicable — the model's answers are not input here |
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from specweaver.infrastructure.llm.adapters.openai import OpenAIAdapter
from specweaver.infrastructure.llm.models import GenerationConfig, ToolDefinition
from specweaver.workflows.review.reviewer import Reviewer, ReviewVerdict


def _always_asks_for_a_tool() -> OpenAIAdapter:
    call = MagicMock()
    call.id = "call_1"
    call.function.name = "read_file"
    call.function.arguments = '{"path": "a.py"}'
    choice = MagicMock()
    choice.message.content = ""
    choice.message.tool_calls = [call]
    choice.finish_reason = "tool_calls"
    response = MagicMock(choices=[choice], usage=None)
    adapter = OpenAIAdapter(api_key="key")
    adapter._client = MagicMock()
    adapter._client.chat.completions.create = AsyncMock(return_value=response)
    return adapter


@pytest.mark.asyncio
async def test_a_review_stopped_at_the_round_limit_is_an_error_naming_the_limit() -> None:
    adapter = _always_asks_for_a_tool()
    dispatcher = MagicMock()
    dispatcher.available_tools.return_value = [ToolDefinition(name="read_file", description="r")]
    dispatcher.execute = AsyncMock(return_value={"content": "x = 1"})
    reviewer = Reviewer(
        llm=adapter,
        config=GenerationConfig(model="m", max_tool_rounds=2, max_output_tokens=1000),
        tool_dispatcher=dispatcher,
    )

    result = await reviewer._execute_review("Review this.")

    assert result.verdict == ReviewVerdict.ERROR
    assert "brake.agent_turns" in result.summary
    assert adapter._client.chat.completions.create.await_count == 2
