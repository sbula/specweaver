# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""From the settings file to the wire: a role on the GB10 sends its request to the GB10.

Proves: C-FLOW-13 FR-7, FR-8

The seam is the settings reader (`core.config.bootstrap`) handing a server entry to the adapter
builder (`infrastructure.llm`); only the HTTP server is doubled.

| Bucket | Case |
|---|---|
| Happy | the machine file's GB10 entry → the request goes to its address (US-16 P2) |
| Boundary | `max_parallel = 2` and three calls → never more than two in flight |
| Degradation | not applicable — a refused file is proven by the settings reader's own tests |
| Hostile | `OPENAI_API_KEY` and `OPENAI_BASE_URL` set → neither reaches the GB10 |
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx2
import pytest

from specweaver.core.config.bootstrap.llm_settings_loader import load_llm_settings
from specweaver.core.config.llm_settings import resolve_roles
from specweaver.infrastructure.llm.adapters._rate_limit import _SEMAPHORES
from specweaver.infrastructure.llm.models import GenerationConfig, Message, Role
from specweaver.infrastructure.llm.servers import adapter_for_server
from tests.fake_http import fake_httpx2

if TYPE_CHECKING:
    from pathlib import Path

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2

[roles]
draft = "qwen3-coder-next@gb10"
"""

_REPLY = {
    "id": "c1",
    "object": "chat.completion",
    "created": 1,
    "model": "qwen3-coder-next",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
    ],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
}


@pytest.fixture()
def gb10_role(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    (tmp_path / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    _SEMAPHORES.clear()
    files = load_llm_settings(None)
    role = resolve_roles(files)["draft"]
    return role, adapter_for_server(role.server, files.machine.servers[role.server])


def _ask(adapter, model: str):
    return adapter.generate([Message(role=Role.USER, content="hi")], GenerationConfig(model=model))


@pytest.mark.asyncio
async def test_a_role_on_the_gb10_is_sent_to_the_gb10(gb10_role) -> None:
    role, adapter = gb10_role

    with fake_httpx2(lambda request: httpx2.Response(200, json=_REPLY)) as seen:
        await _ask(adapter, role.model)

    assert [str(request.url) for request in seen] == ["http://gb10:8000/v1/chat/completions"]
    assert "sk-real-openai-key" not in seen[0].headers.get("authorization", "")


@pytest.mark.asyncio
async def test_the_gb10_never_gets_more_than_its_limit(gb10_role) -> None:
    role, adapter = gb10_role
    in_flight = 0
    peak = 0

    async def slow_reply(request: httpx2.Request) -> httpx2.Response:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1
        return httpx2.Response(200, json=_REPLY)

    with fake_httpx2(slow_reply) as seen:
        await asyncio.gather(*(_ask(adapter, role.model) for _ in range(3)))

    assert len(seen) == 3
    assert peak == 2
