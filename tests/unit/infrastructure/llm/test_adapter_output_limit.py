# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Each OpenAI-style server gets the output limit in the field it honours.

Proves: C-FLOW-13 FR-7

| Bucket | Case |
|---|---|
| Happy | OpenAI and local (vLLM) servers get `max_completion_tokens`; vLLM deprecates `max_tokens` |
| Boundary | Qwen (DashScope) gets `max_tokens`, the only field it documents |
| Degradation | not applicable — the fields are chosen before any request is sent |
| Hostile | OpenAI never gets a sampling value its current models refuse |
| Hostile | OpenAI never gets the deprecated `max_tokens` |
"""

from __future__ import annotations

import json

import httpx2
import pytest

from specweaver.infrastructure.llm.adapters.openai import OpenAIAdapter, OpenAICompatibleAdapter
from specweaver.infrastructure.llm.adapters.qwen import QwenAdapter
from specweaver.infrastructure.llm.models import GenerationConfig, Message, Role, ToolDefinition
from tests.fake_http import fake_httpx2

_REPLY = {
    "id": "c1",
    "object": "chat.completion",
    "created": 1,
    "model": "m",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
    ],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
}


async def _sent_body(adapter: OpenAIAdapter, expected_url: str) -> dict:
    with fake_httpx2(lambda request: httpx2.Response(200, json=_REPLY)) as seen:
        await adapter.generate(
            [Message(role=Role.USER, content="hi")],
            GenerationConfig(model="m", max_output_tokens=512),
        )
    assert str(seen[0].url) == expected_url
    return json.loads(seen[0].content)


@pytest.mark.asyncio
async def test_openai_and_local_servers_get_the_current_field() -> None:
    openai = await _sent_body(
        OpenAIAdapter(api_key="k"), "https://api.openai.com/v1/chat/completions"
    )
    local = await _sent_body(
        OpenAICompatibleAdapter(base_url="http://gb10:8000/v1"),
        "http://gb10:8000/v1/chat/completions",
    )

    for body in (openai, local):
        assert body["max_completion_tokens"] == 512
        assert "max_tokens" not in body


@pytest.mark.asyncio
async def test_qwen_gets_max_tokens() -> None:
    address = "https://dashscope-us.aliyuncs.com/compatible-mode/v1"
    body = await _sent_body(
        QwenAdapter(api_key="k", base_url=address), f"{address}/chat/completions"
    )

    assert body["max_tokens"] == 512
    assert "max_completion_tokens" not in body


@pytest.mark.asyncio
async def test_the_tool_calling_path_sends_the_same_field() -> None:
    adapter = OpenAIAdapter(api_key="k")
    config = GenerationConfig(
        model="m", max_output_tokens=512, tools=[ToolDefinition(name="grep", description="search")]
    )

    with fake_httpx2(lambda request: httpx2.Response(200, json=_REPLY)) as seen:
        await adapter.generate_with_tools([Message(role=Role.USER, content="hi")], config, object())

    body = json.loads(seen[0].content)
    assert body["tools"][0]["function"]["name"] == "grep"
    assert body["max_completion_tokens"] == 512
    assert "max_tokens" not in body


@pytest.mark.asyncio
async def test_openai_gets_no_sampling_value_but_qwen_and_local_servers_do() -> None:
    """GPT-5 and later refuse a non-default temperature with a 400; vLLM and DashScope use it."""
    openai = await _sent_body(
        OpenAIAdapter(api_key="k"), "https://api.openai.com/v1/chat/completions"
    )
    local = await _sent_body(
        OpenAICompatibleAdapter(base_url="http://gb10:8000/v1"),
        "http://gb10:8000/v1/chat/completions",
    )
    address = "https://dashscope-us.aliyuncs.com/compatible-mode/v1"
    qwen = await _sent_body(
        QwenAdapter(api_key="k", base_url=address), f"{address}/chat/completions"
    )

    assert "temperature" not in openai
    assert local["temperature"] == qwen["temperature"] == 0.7
