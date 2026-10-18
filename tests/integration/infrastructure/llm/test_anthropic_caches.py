# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every request to Anthropic asks for automatic caching, so a tool loop reuses its earlier rounds.

Proves: C-FLOW-14 FR-1, NFR-1

Settings file → `build_router` → the real Anthropic adapter → its collector; only HTTP is faked, and
the request bodies the SDK sends are read back.

| Bucket | Case |
|---|---|
| Happy | a single call asks for automatic caching with the default (5-minute) lifetime |
| Boundary | every round of a tool loop asks for it |
| Degradation | not applicable — the field is sent, never read back |
| Hostile | the prompt text sent is exactly the prompt asked |
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import httpx2
import pytest

from specweaver.core.config.llm_settings import LlmSettingsFiles
from specweaver.infrastructure.llm.models import Message, Role, TaskType, ToolDefinition
from specweaver.infrastructure.llm.router import build_router
from tests.fake_http import fake_httpx2

pytestmark = pytest.mark.integration

_MACHINE = """\
[servers.anthropic]
kind = "anthropic"
api_key_env = "ANTHROPIC_API_KEY"
private = false
max_parallel = 1

[roles]
default = { model = "claude-opus-5-5@anthropic", max_output_tokens = 100 }

[brake]
hosted_spend_per_run = 100
tokens_per_run = 10000000
agent_turns = 5
"""
_ASK = "Review the spec. " * 20
_PROMPT = [Message(role=Role.USER, content=_ASK)]


def _routed():
    files = LlmSettingsFiles.from_texts(
        machine_text=_MACHINE,
        machine_source="settings.toml",
        project_text="",
        project_source="-",
        keys={"ANTHROPIC_API_KEY": "test-key-not-real-0123456789"},
    )
    return build_router(files, project="demo", roles=[TaskType.REVIEW]).get_for_task(
        TaskType.REVIEW
    )


def _message(stop: str, content: list) -> dict:
    return {
        "id": "m1",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": content,
        "stop_reason": stop,
        "usage": {"input_tokens": 10, "output_tokens": 1},
    }


def _bodies(seen: list[httpx2.Request]) -> list[dict]:
    return [json.loads(request.content) for request in seen]


async def test_a_call_asks_for_automatic_caching() -> None:
    routed = _routed()
    reply = _message("end_turn", [{"type": "text", "text": "ok"}])

    with fake_httpx2(lambda _request: httpx2.Response(200, json=reply)) as seen:
        await routed.adapter.generate(_PROMPT, routed.config)

    [body] = _bodies(seen)
    assert body["cache_control"] == {"type": "ephemeral"}
    assert body["messages"] == [{"role": "user", "content": _ASK}]


async def test_every_round_of_a_tool_loop_asks_for_it() -> None:
    routed = _routed()
    config = routed.config.model_copy(
        update={"tools": [ToolDefinition(name="look", description="look", parameters=[])]}
    )
    replies = iter(
        [
            _message("tool_use", [{"type": "tool_use", "id": "t1", "name": "look", "input": {}}]),
            _message("end_turn", [{"type": "text", "text": "ok"}]),
        ]
    )
    executor = AsyncMock()
    executor.execute.return_value = {"content": "seen"}

    with fake_httpx2(lambda _request: httpx2.Response(200, json=next(replies))) as seen:
        await routed.adapter.generate_with_tools(_PROMPT, config, executor)

    bodies = _bodies(seen)
    assert len(bodies) == 2
    assert all(body["cache_control"] == {"type": "ephemeral"} for body in bodies)
    assert bodies[0]["messages"][0] == {"role": "user", "content": _ASK}
