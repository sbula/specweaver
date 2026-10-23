# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A cached count the offering's rule does not allow warns once: the provider's rule may have changed.

Proves: TECH-074 FR-11
Proves: C-FLOW-14 FR-1, FR-2

Settings file → `build_router` → a real adapter → its collector, with the shipped list's rules. Only
HTTP is faked. GPT-5.6 caches prefixes of 1,024 tokens or more; Claude Opus 5.5 only behind a
breakpoint, which SpecWeaver sends (C-FLOW-14), Mistral only with the cache key it sends.

| Bucket | Case |
|---|---|
| Happy | a cache within the rule says nothing |
| Boundary | a cache under the minimum prefix warns, once per model however often it happens |
| Degradation | a reply with no cached count says nothing |
| Hostile | a cache behind the breakpoint or key the request sent (Anthropic, Mistral) says nothing; one without it breaks the rule |
"""

from __future__ import annotations

import logging

import httpx2
import pytest

from specweaver.core.config.llm_settings_parse import LlmSettingsFiles
from specweaver.infrastructure.llm.models import Message, Role, TaskType
from specweaver.infrastructure.llm.router import build_router
from tests.fake_http import fake_httpx2

pytestmark = pytest.mark.integration

_MACHINE = """\
[servers.{kind}]
kind = "{kind}"
api_key_env = "KEY"
private = false
max_parallel = 1

[roles]
default = {{ model = "{model}@{kind}", max_output_tokens = 100 }}

[brake]
hosted_spend_per_run = 1000
tokens_per_run = 10000000
agent_turns = 5
"""
_PROMPT = [Message(role=Role.USER, content="hello")]
_LOGGER = "specweaver.infrastructure.llm.collector"


def _routed(kind: str, model: str):
    files = LlmSettingsFiles.from_texts(
        machine_text=_MACHINE.format(kind=kind, model=model),
        machine_source="settings.toml",
        project_text="",
        project_source="-",
        keys={"KEY": "test-key-not-real-0123456789"},
    )
    return build_router(files, project="demo", roles=[TaskType.REVIEW]).get_for_task(
        TaskType.REVIEW
    )


def _openai(prompt: int, cached: int | None) -> dict:
    usage: dict = {"prompt_tokens": prompt, "completion_tokens": 1, "total_tokens": prompt + 1}
    if cached is not None:
        usage["prompt_tokens_details"] = {"cached_tokens": cached}
    return {
        "id": "c1",
        "object": "chat.completion",
        "created": 1,
        "model": "m",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
        ],
        "usage": usage,
    }


async def _warnings(caplog, routed, replies: list[dict]) -> list[str]:
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        for reply in replies:
            with fake_httpx2(lambda _request, reply=reply: httpx2.Response(200, json=reply)):
                await routed.adapter.generate(_PROMPT, routed.config)
    return [r.getMessage() for r in caplog.records if "cache rule" in r.getMessage()]


async def test_a_cache_within_the_rule_says_nothing(caplog: pytest.LogCaptureFixture) -> None:
    assert await _warnings(caplog, _routed("openai", "gpt-5.6"), [_openai(2000, 1024)]) == []


async def test_a_cache_under_the_minimum_prefix_warns_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    found = await _warnings(caplog, _routed("openai", "gpt-5.6"), [_openai(1000, 800)] * 3)

    assert len(found) == 1
    assert "gpt-5.6" in found[0] and "1024" in found[0]


async def test_no_cached_count_says_nothing(caplog: pytest.LogCaptureFixture) -> None:
    assert await _warnings(caplog, _routed("openai", "gpt-5.6"), [_openai(1000, None)]) == []


async def test_an_anthropic_cache_behind_the_breakpoint_it_sends_says_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    reply = {
        "id": "m1",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": "ok"}],
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 1,
            "cache_read_input_tokens": 2000,
            "cache_creation_input_tokens": 0,
        },
    }

    found = await _warnings(caplog, _routed("anthropic", "claude-opus-5-5"), [reply])

    assert found == []


async def test_a_mistral_cache_behind_the_key_it_sends_says_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from unittest.mock import AsyncMock, MagicMock

    from mistralai.client.models import UsageInfo

    from specweaver.infrastructure.llm.adapters.mistral import MistralAdapter
    from specweaver.infrastructure.llm.catalogue import shipped_catalogue
    from specweaver.infrastructure.llm.collector import TelemetryCollector
    from specweaver.infrastructure.llm.models import GenerationConfig
    from specweaver.infrastructure.llm.prices import PriceBook

    reply = MagicMock()
    reply.choices = [MagicMock(message=MagicMock(content="ok"), finish_reason="stop")]
    reply.usage = UsageInfo.model_validate(
        {
            "prompt_tokens": 3000,
            "completion_tokens": 1,
            "total_tokens": 3001,
            "prompt_tokens_details": {"cached_tokens": 2048},
        }
    )
    adapter = MistralAdapter(api_key="test-key-not-real")
    adapter._client = MagicMock()
    adapter._client.chat.complete_async = AsyncMock(return_value=reply)
    book = PriceBook(
        tuple(shipped_catalogue().prices("mistral", "mistral-large-latest")), local=False
    )
    collector = TelemetryCollector(adapter, "demo", prices=lambda _model: book)
    config = GenerationConfig(model="mistral-large-latest", max_output_tokens=10)

    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        await collector.generate(_PROMPT, config)

    assert not [r for r in caplog.records if "cache rule" in r.getMessage()]


def test_a_requirement_the_request_did_not_send_still_breaks_the_rule() -> None:
    from specweaver.infrastructure.llm.prices import Rule, rule_break

    rule = Rule(requires="breakpoint")

    assert rule_break(rule, prompt_tokens=5000) != ""
    assert rule_break(rule, prompt_tokens=5000, sent=frozenset({"breakpoint"})) == ""
