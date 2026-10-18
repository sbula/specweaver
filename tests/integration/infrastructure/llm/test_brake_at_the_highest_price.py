# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The brake reserves a call's prompt at its highest price, so a cache never makes it hold too little.

Proves: TECH-074 FR-5

Settings file → `build_router` → a real adapter → its collector → the brake. Only HTTP is faked.
A prompt of about 10,000 tokens and an output cap of 1,000: at the input price (1,000 USD per 1M) the
worst case is about 13.5 USD, at the cache-write price (3,000) about 38.5.

| Bucket | Case |
|---|---|
| Happy | a limit above the cache-write worst case lets the call through, billed at the input price |
| Boundary | a limit between the two worst cases stops the call before it is sent |
| Degradation | a model with no cache prices reserves at its input price |
| Hostile | a hosted model with only a cached price is refused before any call, naming the input price |
"""

from __future__ import annotations

import httpx2
import pytest

from specweaver.core.config.llm_settings import LlmSettingsFiles, SettingsFileError
from specweaver.infrastructure.llm.budget import SpendLimitReachedError
from specweaver.infrastructure.llm.models import Message, Role, TaskType
from specweaver.infrastructure.llm.router import build_router
from tests.fake_http import fake_httpx2

_HOSTED = """\
[servers.hosted]
kind = "openai-compatible"
base_url = "http://hosted.example/v1"
private = false
max_parallel = 4

[roles]
default = {{ model = "big-model@hosted", max_output_tokens = 1000 }}

[models."big-model"]
usd_per_million_input = 1000.0
usd_per_million_output = 1000.0
{cache}thinking_in_output_cap = true

[brake]
hosted_spend_per_run = {limit}
tokens_per_run = 2000000
agent_turns = 30
"""
_CACHE = "usd_per_million_cache_write = 3000.0\nusd_per_million_cached_read = 100.0\n"

_REPLY = {
    "id": "c1",
    "object": "chat.completion",
    "created": 1,
    "model": "m",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
    ],
    "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
}
_PROMPT = [Message(role=Role.USER, content="x" * 40_000)]


def _router(limit: float, cache: str = _CACHE):
    files = LlmSettingsFiles.from_texts(
        machine_text=_HOSTED.format(limit=limit, cache=cache),
        machine_source="settings.toml",
        project_text="",
        project_source="-",
    )
    return build_router(files, project="demo", roles=[TaskType.REVIEW])


async def _call(router) -> tuple[list[httpx2.Request], object]:
    routed = router.get_for_task(TaskType.REVIEW)
    with fake_httpx2(lambda _request: httpx2.Response(200, json=_REPLY)) as seen:
        await routed.adapter.generate(_PROMPT, routed.config)
    return seen, routed.adapter.budget


async def test_a_limit_above_the_cache_write_worst_case_lets_the_call_through() -> None:
    seen, budget = await _call(_router(50))

    assert len(seen) == 1
    assert budget.spent("brake.hosted_spend_per_run") == pytest.approx(0.03)


async def test_a_limit_between_the_two_worst_cases_stops_the_call() -> None:
    with (
        pytest.raises(SpendLimitReachedError) as caught,
        fake_httpx2(lambda _request: httpx2.Response(200, json=_REPLY)) as seen,
    ):
        routed = _router(20).get_for_task(TaskType.REVIEW)
        await routed.adapter.generate(_PROMPT, routed.config)

    assert caught.value.limit.key == "brake.hosted_spend_per_run"
    assert seen == []


async def test_without_cache_prices_the_input_price_is_reserved() -> None:
    seen, _budget = await _call(_router(20, cache=""))

    assert len(seen) == 1


def test_a_hosted_model_with_only_a_cached_price_is_refused() -> None:
    files = LlmSettingsFiles.from_texts(
        machine_text=_HOSTED.format(limit=50, cache="").replace(
            "usd_per_million_input = 1000.0\n", "usd_per_million_cached_read = 100.0\n"
        ),
        machine_source="settings.toml",
        project_text="",
        project_source="-",
    )

    with pytest.raises(SettingsFileError, match="usd_per_million_input"):
        build_router(files, project="demo", roles=[TaskType.REVIEW])
