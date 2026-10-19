# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A local server that reports no cached count says once how to make vLLM report it.

Proves: C-FLOW-14 FR-5

Settings file → `build_router` → the real adapter → its collector; only HTTP is faked.

| Bucket | Case |
|---|---|
| Happy | a GB10 reply without a cached count warns, naming the vLLM flag |
| Boundary | three such replies warn once |
| Degradation | a reply with prompt details, or llama.cpp's timings, says nothing |
| Hostile | a hosted server without a cached count, and a stream (its usage is estimated), never get the hint |
"""

from __future__ import annotations

import logging

import httpx2
import pytest

from specweaver.core.config.llm_settings import LlmSettingsFiles
from specweaver.infrastructure.llm.models import Message, Role, TaskType
from specweaver.infrastructure.llm.router import build_router
from tests.fake_http import fake_httpx2

pytestmark = pytest.mark.integration

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = {private}
max_parallel = 1

[roles]
default = {{ model = "qwen3-coder-next@gb10", max_output_tokens = 100 }}

[models."qwen3-coder-next"]
usd_per_million_input = 1.0
usd_per_million_output = 1.0

[brake]
hosted_spend_per_run = 100
tokens_per_run = 10000000
agent_turns = 5
"""
_PLAIN = {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11}
_FLAG = "--enable-prompt-tokens-details"


def _reply(usage: dict, **extra: object) -> dict:
    return {
        "id": "c1",
        "object": "chat.completion",
        "created": 1,
        "model": "m",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
        ],
        "usage": usage,
        **extra,
    }


async def _hints(caplog, reply: dict, *, private: bool = True, calls: int = 1) -> list[str]:
    files = LlmSettingsFiles.from_texts(
        machine_text=_MACHINE.format(private=str(private).lower()),
        machine_source="settings.toml",
        project_text="",
        project_source="-",
    )
    routed = build_router(files, project="demo", roles=[TaskType.REVIEW]).get_for_task(
        TaskType.REVIEW
    )
    with caplog.at_level(logging.WARNING), fake_httpx2(lambda _r: httpx2.Response(200, json=reply)):
        for _ in range(calls):
            await routed.adapter.generate([Message(role=Role.USER, content="hi")], routed.config)
    return [r.getMessage() for r in caplog.records if _FLAG in r.getMessage()]


async def test_a_local_reply_without_a_count_names_the_flag(
    caplog: pytest.LogCaptureFixture,
) -> None:
    [hint] = await _hints(caplog, _reply(_PLAIN))

    assert "gb10" in hint


async def test_three_such_replies_warn_once(caplog: pytest.LogCaptureFixture) -> None:
    assert len(await _hints(caplog, _reply(_PLAIN), calls=3)) == 1


@pytest.mark.parametrize(
    "reply",
    [
        _reply({**_PLAIN, "prompt_tokens_details": {"cached_tokens": 0}}),
        _reply(_PLAIN, timings={"cache_n": 4}),
    ],
    ids=["vllm-with-details", "llama-cpp"],
)
async def test_a_reply_with_a_count_says_nothing(
    caplog: pytest.LogCaptureFixture, reply: dict
) -> None:
    assert await _hints(caplog, reply) == []


async def test_a_hosted_server_never_gets_the_hint(caplog: pytest.LogCaptureFixture) -> None:
    assert await _hints(caplog, _reply(_PLAIN), private=False) == []


async def test_a_stream_never_gets_the_hint(caplog: pytest.LogCaptureFixture) -> None:
    from specweaver.infrastructure.llm.collector import TelemetryCollector
    from specweaver.infrastructure.llm.models import GenerationConfig
    from specweaver.infrastructure.llm.prices import PriceBook

    class _Streamer:
        provider_name = "openai-compatible"

        async def generate_stream(self, _messages, _config):
            yield "y" * 400  # long enough that its estimated usage is not zero

    collector = TelemetryCollector(
        _Streamer(), "demo", prices=lambda _model: PriceBook((), local=True), server="gb10"
    )
    config = GenerationConfig(model="qwen3-coder-next", max_output_tokens=10)

    with caplog.at_level(logging.WARNING):
        async for _ in collector.generate_stream(
            [Message(role=Role.USER, content="x" * 400)], config
        ):
            pass

    assert not [r for r in caplog.records if _FLAG in r.getMessage()]
