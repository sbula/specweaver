# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A known secret never leaves in a prompt: not in a message, not in a tool result.

Proves: E-INTL-01 FR-3

The seam: settings file and vault (`core.config`) → router → collector → a real adapter. Only
HTTP is faked. Known secrets are the API keys the settings file names and the vault's values
`[agreed 2026-10-08]`.

| Bucket | Case |
|---|---|
| Happy | an API key pasted into a prompt is sent masked |
| Boundary | a short vault value (a port) is not a secret and goes through |
| Degradation | a project with no vault still masks the API key |
| Hostile | a tool that reads the vault returns the value masked to the model |
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx2
import pytest

from specweaver.core.config.llm_settings import LlmSettingsFiles
from specweaver.infrastructure.llm.models import Message, Role, TaskType, ToolDefinition
from specweaver.infrastructure.llm.router import build_router
from tests.fake_http import fake_httpx2

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_KEY = "sk-live-0123456789abcdef"
_VAULT_TOKEN = "vault-token-zyxwvut987"

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2
api_key_env = "GB10_KEY"

[roles]
default = { model = "qwen3-coder-next@gb10", max_output_tokens = 100 }

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


def _routed(project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GB10_KEY", _KEY)
    files = LlmSettingsFiles.from_texts(
        machine_text=_MACHINE,
        machine_source="settings.toml",
        project_text="",
        project_source=str(project / "specweaver.toml"),
        project_root=project,
    )
    return build_router(files, project="demo", roles=[TaskType.REVIEW]).get_for_task(
        TaskType.REVIEW
    )


def _sent(requests: list[httpx2.Request]) -> str:
    return " ".join(request.content.decode() for request in requests)


async def test_an_api_key_in_a_prompt_is_sent_masked(tmp_path: Path, monkeypatch) -> None:
    routed = _routed(tmp_path, monkeypatch)

    with fake_httpx2(lambda _request: httpx2.Response(200, json=_REPLY)) as seen:
        await routed.adapter.generate(
            [Message(role=Role.USER, content=f"my key is {_KEY}")], routed.config
        )

    assert _KEY not in _sent(seen)
    assert "***RESTRICTED***" in _sent(seen)


async def test_vault_values_are_masked_and_short_ones_pass(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".specweaver").mkdir()
    (tmp_path / ".specweaver" / "vault.env").write_text(
        f"# vault\nTOKEN={_VAULT_TOKEN}\nPORT=5432\n", encoding="utf-8"
    )
    routed = _routed(tmp_path, monkeypatch)

    with fake_httpx2(lambda _request: httpx2.Response(200, json=_REPLY)) as seen:
        await routed.adapter.generate(
            [Message(role=Role.USER, content=f"token {_VAULT_TOKEN} on port 5432")], routed.config
        )

    assert _VAULT_TOKEN not in _sent(seen)
    assert "5432" in _sent(seen)


class _ReadsTheVault:
    async def execute(self, _name: str, _args: dict) -> dict:
        return {"content": f"TOKEN={_VAULT_TOKEN}"}


async def test_a_tool_result_reaches_the_model_masked(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".specweaver").mkdir()
    (tmp_path / ".specweaver" / "vault.env").write_text(f"TOKEN={_VAULT_TOKEN}\n")
    routed = _routed(tmp_path, monkeypatch)
    call = {
        **_REPLY,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "t1",
                            "type": "function",
                            "function": {"name": "read_file", "arguments": json.dumps({})},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
    }
    replies = iter([call, _REPLY])
    config = routed.config.model_copy(
        update={"tools": [ToolDefinition(name="read_file", description="read a file")]}
    )

    with fake_httpx2(lambda _request: httpx2.Response(200, json=next(replies))) as seen:
        await routed.adapter.generate_with_tools(
            [Message(role=Role.USER, content="read it")], config, _ReadsTheVault()
        )

    assert len(seen) == 2
    assert _VAULT_TOKEN not in _sent(seen)


async def test_the_loaded_settings_find_the_projects_vault(tmp_path: Path, monkeypatch) -> None:
    from specweaver.core.config.bootstrap.llm_settings_loader import load_llm_settings

    data = tmp_path / "data"
    data.mkdir()
    (data / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    monkeypatch.setenv("GB10_KEY", _KEY)
    (tmp_path / ".specweaver").mkdir()
    (tmp_path / ".specweaver" / "vault.env").write_text(f"TOKEN={_VAULT_TOKEN}\n")
    routed = build_router(
        load_llm_settings(tmp_path), project="demo", roles=[TaskType.REVIEW]
    ).get_for_task(TaskType.REVIEW)

    with fake_httpx2(lambda _request: httpx2.Response(200, json=_REPLY)) as seen:
        await routed.adapter.generate(
            [Message(role=Role.USER, content=_VAULT_TOKEN)], routed.config
        )

    assert _VAULT_TOKEN not in _sent(seen)
