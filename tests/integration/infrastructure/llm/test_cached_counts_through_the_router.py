# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A provider's cached-token count reaches the caller through the real router, SDK and collector.

Proves: TECH-074 FR-3

Settings file → `build_router` → a real adapter → its collector. Only HTTP is faked; the replies are
the JSON each server sends, parsed by the real SDK.

| Bucket | Case |
|---|---|
| Happy | a vLLM reply with prompt details and an Anthropic reply with cache fields give their counts |
| Boundary | an OpenAI-style and an Anthropic tool loop sum the cached counts of their rounds; llama.cpp's count outside `usage` is read |
| Degradation | a reply with no cache field gives an unknown count, never 0 |
| Hostile | not applicable — counts come from the server; a malformed count is covered by the unit tests |
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx2
import pytest

from specweaver.core.config.llm_settings_parse import LlmSettingsFiles
from specweaver.infrastructure.llm.models import Message, Role, TaskType, ToolDefinition
from specweaver.infrastructure.llm.router import build_router
from tests.fake_http import fake_httpx2

pytestmark = pytest.mark.integration

_BRAKE = """
[brake]
hosted_spend_per_run = 100
tokens_per_run = 10000000
agent_turns = 5
"""
_GB10 = (
    """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2

[roles]
default = { model = "qwen3-coder-next@gb10", max_output_tokens = 100 }
"""
    + _BRAKE
)
_ANTHROPIC = (
    """\
[servers.anthropic]
kind = "anthropic"
api_key_env = "ANTHROPIC_API_KEY"
private = false
max_parallel = 1

[roles]
default = { model = "claude-opus-5-5@anthropic", max_output_tokens = 100 }
"""
    + _BRAKE
)
_PROMPT = [Message(role=Role.USER, content="hello")]


def _routed(machine: str):
    files = LlmSettingsFiles.from_texts(
        machine_text=machine,
        machine_source="settings.toml",
        project_text="",
        project_source="-",
        keys={"ANTHROPIC_API_KEY": "test-key-not-real-0123456789"},
    )
    return build_router(files, project="demo", roles=[TaskType.REVIEW]).get_for_task(
        TaskType.REVIEW
    )


def _chat(usage: dict, *, tool_call: bool = False, **extra: object) -> dict:
    message: dict = {"role": "assistant", "content": "ok"}
    if tool_call:
        message = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "t1", "type": "function", "function": {"name": "look", "arguments": "{}"}}
            ],
        }
    return {
        "id": "c1",
        "object": "chat.completion",
        "created": 1,
        "model": "m",
        "choices": [
            {"index": 0, "message": message, "finish_reason": "tool_calls" if tool_call else "stop"}
        ],
        "usage": usage,
        **extra,
    }


def _vllm(cached: int) -> dict:
    return {
        "prompt_tokens": 1000,
        "completion_tokens": 10,
        "total_tokens": 1010,
        "prompt_tokens_details": {"cached_tokens": cached},
    }


async def _generate(routed, reply: dict):
    with fake_httpx2(lambda _request: httpx2.Response(200, json=reply)):
        return await routed.adapter.generate(_PROMPT, routed.config)


async def test_a_vllm_reply_gives_its_cached_count() -> None:
    response = await _generate(_routed(_GB10), _chat(_vllm(800)))

    assert (response.usage.cached_read_tokens, response.usage.cache_write_tokens) == (800, 0)


async def test_llama_cpp_gives_its_count_outside_usage() -> None:
    plain = {"prompt_tokens": 1000, "completion_tokens": 10, "total_tokens": 1010}

    response = await _generate(_routed(_GB10), _chat(plain, timings={"cache_n": 640}))

    assert response.usage.cached_read_tokens == 640


async def test_a_reply_without_a_cache_field_is_unknown() -> None:
    plain = {"prompt_tokens": 1000, "completion_tokens": 10, "total_tokens": 1010}

    response = await _generate(_routed(_GB10), _chat(plain))

    assert response.usage.cached_read_tokens is None


async def test_a_tool_loop_sums_its_rounds() -> None:
    routed = _routed(_GB10)
    config = routed.config.model_copy(
        update={"tools": [ToolDefinition(name="look", description="look", parameters=[])]}
    )
    replies = iter([_chat(_vllm(300), tool_call=True), _chat(_vllm(500))])
    executor = AsyncMock()
    executor.execute.return_value = {"content": "seen"}

    with fake_httpx2(lambda _request: httpx2.Response(200, json=next(replies))):
        response = await routed.adapter.generate_with_tools(_PROMPT, config, executor)

    assert (response.usage.prompt_tokens, response.usage.cached_read_tokens) == (2000, 800)


async def test_an_anthropic_reply_adds_its_cached_part_to_the_prompt() -> None:
    reply = {
        "id": "m1",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": "ok"}],
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 10,
            "cache_read_input_tokens": 900,
            "cache_creation_input_tokens": 50,
        },
    }

    response = await _generate(_routed(_ANTHROPIC), reply)

    usage = response.usage
    assert (usage.prompt_tokens, usage.cached_read_tokens, usage.cache_write_tokens) == (
        1050,
        900,
        50,
    )


async def test_an_anthropic_tool_loop_sums_its_rounds() -> None:
    routed = _routed(_ANTHROPIC)
    config = routed.config.model_copy(
        update={"tools": [ToolDefinition(name="look", description="look", parameters=[])]}
    )

    def _message(stop: str, content: list, read: int) -> dict:
        return {
            "id": "m1",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "content": content,
            "stop_reason": stop,
            "usage": {
                "input_tokens": 100,
                "output_tokens": 10,
                "cache_read_input_tokens": read,
                "cache_creation_input_tokens": 0,
            },
        }

    replies = iter(
        [
            _message(
                "tool_use", [{"type": "tool_use", "id": "t1", "name": "look", "input": {}}], 400
            ),
            _message("end_turn", [{"type": "text", "text": "ok"}], 600),
        ]
    )
    executor = AsyncMock()
    executor.execute.return_value = {"content": "seen"}

    with fake_httpx2(lambda _request: httpx2.Response(200, json=next(replies))):
        response = await routed.adapter.generate_with_tools(_PROMPT, config, executor)

    assert (response.usage.prompt_tokens, response.usage.cached_read_tokens) == (1200, 1000)
