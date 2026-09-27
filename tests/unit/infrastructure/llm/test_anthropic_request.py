# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the Anthropic adapter sends: current Claude models refuse sampling values with a 400.

| Bucket | Case |
|---|---|
| Happy | a call reaches the Messages API with the model, messages and output limit |
| Boundary | a non-default temperature in the config is not sent |
| Degradation | not applicable — the request is built before anything can fail |
| Hostile | not applicable — no user input reaches these fields |
"""

from __future__ import annotations

import json

import httpx2
import pytest

from specweaver.infrastructure.llm.adapters.anthropic import AnthropicAdapter
from specweaver.infrastructure.llm.models import GenerationConfig, Message, Role
from tests.fake_http import fake_httpx2

_REPLY = {
    "id": "msg_1",
    "type": "message",
    "role": "assistant",
    "model": "claude-opus-5-5",
    "content": [{"type": "text", "text": "ok"}],
    "stop_reason": "end_turn",
    "stop_sequence": None,
    "usage": {"input_tokens": 1, "output_tokens": 1},
}


@pytest.mark.asyncio
async def test_no_sampling_value_is_sent() -> None:
    adapter = AnthropicAdapter(api_key="k")
    config = GenerationConfig(model="claude-opus-5-5", temperature=0.2, max_output_tokens=512)

    with fake_httpx2(lambda request: httpx2.Response(200, json=_REPLY)) as seen:
        response = await adapter.generate([Message(role=Role.USER, content="hi")], config)

    body = json.loads(seen[0].content)
    assert response.text == "ok"
    assert str(seen[0].url) == "https://api.anthropic.com/v1/messages"
    assert (body["model"], body["max_tokens"]) == ("claude-opus-5-5", 512)
    assert not {"temperature", "top_p", "top_k"} & set(body)
