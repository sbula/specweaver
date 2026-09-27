# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""From the settings files to the wire, through the one resolver.

Proves: C-FLOW-13 FR-10, FR-11

The seam is the settings reader (`core.config.bootstrap`), the shipped catalogue and the resolver
(`infrastructure.llm`) working together; only the HTTP server is doubled.

| Bucket | Case |
|---|---|
| Happy | two roles on the GB10 → both requests reach it, with the catalogue's sampling |
| Boundary | the two roles count against one budget and record into one collector |
| Degradation | a role missing from a file without `default` → refused before any request |
| Hostile | not applicable here — the privacy rule is proven where it is enforced (resolve_roles) |
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx2
import pytest

from specweaver.core.config.bootstrap.llm_settings_loader import load_llm_settings
from specweaver.core.config.llm_settings import SettingsFileError
from specweaver.infrastructure.llm.adapters._rate_limit import _SEMAPHORES
from specweaver.infrastructure.llm.budget import SpendBudget
from specweaver.infrastructure.llm.models import Message, Role
from specweaver.infrastructure.llm.resolve import RoleResolver
from tests.fake_http import fake_httpx2

if TYPE_CHECKING:
    from pathlib import Path

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 4

[roles]
draft = "qwen3-coder-next@gb10"
review = { model = "qwen3-coder-next@gb10", max_output_tokens = 1024 }
"""

_REPLY = {
    "id": "c1",
    "object": "chat.completion",
    "created": 1,
    "model": "qwen3-coder-next",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
}


@pytest.fixture()
def files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path))
    _SEMAPHORES.clear()

    def write(machine: str):
        (tmp_path / "settings.toml").write_text(machine, encoding="utf-8")
        return load_llm_settings(None)

    return write


@pytest.mark.asyncio
async def test_two_roles_reach_the_gb10_on_one_budget(files) -> None:
    budget = SpendBudget(limit_usd=None)
    resolver = RoleResolver(files(_MACHINE), telemetry_project="demo", budget=budget)

    with fake_httpx2(lambda request: httpx2.Response(200, json=_REPLY)) as seen:
        for role in ("draft", "review"):
            adapter, config = resolver.for_role(role)
            await adapter.generate([Message(role=Role.USER, content="hi")], config)

    bodies = [json.loads(request.content) for request in seen]
    assert [str(request.url) for request in seen] == ["http://gb10:8000/v1/chat/completions"] * 2
    assert bodies[0]["temperature"] == 1.0  # the model card's value, from the shipped catalogue
    assert bodies[1]["max_completion_tokens"] == 1024
    assert budget.tokens == 30
    [collector] = resolver.collectors()
    assert len(collector.records) == 2


def test_a_role_nobody_set_refuses_before_any_request(files) -> None:
    resolver = RoleResolver(files(_MACHINE), telemetry_project="demo", budget=SpendBudget(None))

    with (
        fake_httpx2(lambda request: httpx2.Response(200, json=_REPLY)) as seen,
        pytest.raises(SettingsFileError) as caught,
    ):
        resolver.require(["draft", "implement"])

    assert caught.value.key == "roles.implement"
    assert seen == []
