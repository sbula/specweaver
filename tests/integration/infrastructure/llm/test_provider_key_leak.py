# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A provider's key is never sent to another host, even when the settings name no key.

Proves: C-FLOW-13 FR-7

Settings file → router → a real OpenAI adapter; only HTTP is faked.

| Bucket | Case |
|---|---|
| Happy | not applicable — the provider's own address is proven by the server tests |
| Boundary | an `openai` server pointed at another host, with no `api_key_env`, is refused |
| Degradation | not applicable — an unset key variable is proven by the resolver tests |
| Hostile | `OPENAI_API_KEY` is set; with its own variable, the host gets only that key |
"""

from __future__ import annotations

import httpx2
import pytest

from specweaver.core.config.llm_settings import LlmSettingsFiles, SettingsFileError
from specweaver.infrastructure.llm.models import Message, Role, TaskType
from specweaver.infrastructure.llm.router import build_router
from tests.fake_http import fake_httpx2

pytestmark = pytest.mark.integration

_SECRET = "sk-real-openai-key-0123456789"

_MACHINE = """\
[servers.proxy]
kind = "openai"
base_url = "http://elsewhere.example/v1"
private = true
max_parallel = 2

[roles]
default = { model = "gpt-5.4@proxy", max_output_tokens = 100 }

[brake]
hosted_spend_per_run = 10
tokens_per_run = 1000000
agent_turns = 5
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


def test_settings_that_would_send_the_openai_key_elsewhere_are_refused(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", _SECRET)

    with (
        fake_httpx2(lambda _request: httpx2.Response(200, json=_REPLY)) as seen,
        pytest.raises(SettingsFileError) as caught,
    ):
        files = LlmSettingsFiles.from_texts(
            machine_text=_MACHINE,
            machine_source="settings.toml",
            project_text="",
            project_source="-",
        )
        build_router(files, project="demo", roles=[TaskType.REVIEW])

    assert seen == []
    assert caught.value.key.startswith("servers.proxy")
    assert caught.value.line == 1


async def test_its_own_key_variable_is_what_another_host_gets(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", _SECRET)
    files = LlmSettingsFiles.from_texts(
        machine_text=_MACHINE.replace(
            "private = true", 'private = true\napi_key_env = "PROXY_KEY"'
        ),
        machine_source="settings.toml",
        project_text="",
        project_source="-",
        keys={"OPENAI_API_KEY": _SECRET, "PROXY_KEY": "proxy-key-0123456789"},
    )
    routed = build_router(files, project="demo", roles=[TaskType.REVIEW]).get_for_task(
        TaskType.REVIEW
    )

    with fake_httpx2(lambda _request: httpx2.Response(200, json=_REPLY)) as seen:
        await routed.adapter.generate([Message(role=Role.USER, content="hi")], routed.config)

    sent = [value for request in seen for value in dict(request.headers).values()]
    assert any("proxy-key-0123456789" in value for value in sent)
    assert all(_SECRET not in value for value in sent)
