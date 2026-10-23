# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Calls of one step type in one project share a cache key; the key names neither.

Proves: C-FLOW-14 FR-2, NFR-2, NFR-3

Settings file → `build_router` → the real adapter → its collector, which sets the key; only HTTP is
faked for the OpenAI SDK. Mistral's SDK sends over `httpx`, so its client is replaced and the
request it was asked to send is read.

| Bucket | Case |
|---|---|
| Happy | two OpenAI calls of one step type send one key; Mistral sends it too |
| Boundary | another step type, or another project, sends another key |
| Degradation | not applicable — the key is sent, never read back |
| Hostile | the key holds neither the project nor the step type; `openai-compatible` and Qwen servers get none |
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import httpx2
import pytest

from specweaver.core.config.llm_settings_parse import LlmSettingsFiles
from specweaver.infrastructure.llm.adapters.mistral import MistralAdapter
from specweaver.infrastructure.llm.collector import TelemetryCollector
from specweaver.infrastructure.llm.models import GenerationConfig, Message, Role, TaskType
from specweaver.infrastructure.llm.router import build_router
from tests.fake_http import fake_httpx2

pytestmark = pytest.mark.integration

_BRAKE = """
[brake]
hosted_spend_per_run = 100
tokens_per_run = 10000000
agent_turns = 5
"""
_SERVER = """\
[servers.s]
kind = "{kind}"
{extra}private = false
max_parallel = 1

[roles]
default = {{ model = "gpt-5.6@s", max_output_tokens = 100 }}

[models."gpt-5.6"]
usd_per_million_input = 1.0
usd_per_million_output = 1.0
"""
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
_PROMPT = [Message(role=Role.USER, content="hello")]


def _routed(kind: str = "openai", project: str = "demo", extra: str = 'api_key_env = "KEY"\n'):
    files = LlmSettingsFiles.from_texts(
        machine_text=_SERVER.format(kind=kind, extra=extra) + _BRAKE,
        machine_source="settings.toml",
        project_text="",
        project_source="-",
        keys={"KEY": "test-key-not-real-0123456789"},
    )
    return build_router(files, project=project, roles=[TaskType.REVIEW]).get_for_task(
        TaskType.REVIEW
    )


async def _keys(routed, *task_types: TaskType) -> list[str | None]:
    with fake_httpx2(lambda _request: httpx2.Response(200, json=_REPLY)) as seen:
        for task_type in task_types:
            config = routed.config.model_copy(update={"task_type": task_type})
            await routed.adapter.generate(_PROMPT, config)
    return [json.loads(request.content).get("prompt_cache_key") for request in seen]


async def test_one_step_type_shares_one_key() -> None:
    first, second = await _keys(_routed(), TaskType.REVIEW, TaskType.REVIEW)

    assert first is not None and first == second
    assert first.startswith("sw-") and len(first) == 35


async def test_another_step_type_or_project_has_another_key() -> None:
    review, implement = await _keys(_routed(), TaskType.REVIEW, TaskType.IMPLEMENT)
    [other] = await _keys(_routed(project="other"), TaskType.REVIEW)

    assert len({review, implement, other}) == 3


async def test_the_key_names_neither_the_project_nor_the_step() -> None:
    [key] = await _keys(_routed(project="secret-project"), TaskType.REVIEW)

    assert "secret" not in key and "review" not in key.lower()


@pytest.mark.parametrize(
    ("kind", "extra"),
    [
        ("openai-compatible", 'base_url = "http://hosted.example/v1"\n'),
        ("qwen", 'api_key_env = "KEY"\nbase_url = "https://dashscope.example/v1"\n'),
    ],
)
async def test_servers_that_may_not_know_the_field_get_none(kind: str, extra: str) -> None:
    keys = await _keys(_routed(kind, extra=extra), TaskType.REVIEW)

    assert keys == [None]


async def test_mistral_sends_the_key() -> None:
    reply = MagicMock()
    reply.choices = [MagicMock(message=MagicMock(content="ok"), finish_reason="stop")]
    reply.usage = None
    adapter = MistralAdapter(api_key="test-key-not-real")
    adapter._client = MagicMock()
    adapter._client.chat.complete_async = AsyncMock(return_value=reply)
    collector = TelemetryCollector(adapter, "demo")
    config = GenerationConfig(
        model="mistral-large-latest", max_output_tokens=10, task_type=TaskType.REVIEW
    )

    await collector.generate(_PROMPT, config)

    sent = adapter._client.chat.complete_async.call_args.kwargs
    assert sent["prompt_cache_key"].startswith("sw-")
