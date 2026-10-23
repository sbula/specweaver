# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A review agent gets web search when the machine file names a key, and that key reaches Tavily.

Proves: E-SENS-02 FR-5

The seam: settings file and keys.env → resolver → router → review step's tools → Tavily request.

| Bucket | Case |
|---|---|
| Happy | `[search]` + key: the reviewer's tools include web_search, and the call carries the key |
| Boundary | no `[search]`: no web tools, whatever the environment holds |
| Degradation | `[search]` but keys.env lacks the variable: refused, naming the setting |
| Hostile | the old `SEARCH_API_KEY` variable switches nothing on |
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from specweaver.core.config.llm_settings import LlmSettingsFiles
from specweaver.core.config.settings_file import SettingsFileError
from specweaver.core.flow.handlers.review import _build_tool_dispatcher
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext
from specweaver.infrastructure.llm.budget import SpendBudget
from specweaver.infrastructure.llm.resolve import RoleResolver
from specweaver.infrastructure.llm.router import ModelRouter

if TYPE_CHECKING:
    from pathlib import Path

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 4

[roles]
default = "qwen3-coder-next@gb10"
"""
_SEARCH = '\n[search]\napi_key_env = "TAVILY_API_KEY"\n'


def _dispatcher(tmp_path: Path, machine: str, keys: dict[str, str]):  # type: ignore[no-untyped-def]
    files = LlmSettingsFiles.from_texts(
        machine_text=machine,
        machine_source="settings.toml",
        project_text="",
        project_source="-",
        keys=keys,
    )
    router = ModelRouter(RoleResolver(files, telemetry_project="p", budget=SpendBudget()))
    context = RunContext(
        model=ModelAccess(llm_router=router),
        project_path=tmp_path,
        spec_path=tmp_path / "spec.md",
    )
    adapter = MagicMock()
    return _build_tool_dispatcher(context, role="reviewer", adapter=adapter)


def _tool_names(dispatcher) -> set[str]:  # type: ignore[no-untyped-def]
    return {d.name for d in dispatcher.available_tools()}


@respx.mock
async def test_the_reviewer_searches_with_the_key_keys_env_holds(tmp_path: Path) -> None:
    # Proves: E-SENS-02 FR-5
    route = respx.post("https://api.tavily.com/search").mock(
        return_value=httpx.Response(
            200, json={"results": [{"title": "T", "url": "https://a.example", "content": "C"}]}
        )
    )
    dispatcher = _dispatcher(tmp_path, _MACHINE + _SEARCH, {"TAVILY_API_KEY": "tvly-test"})

    assert {"web_search", "read_url"} <= _tool_names(dispatcher)
    answer = await dispatcher.execute("web_search", {"query": "pydantic strict mode"})

    assert answer == {"results": [{"title": "T", "snippet": "C", "url": "https://a.example"}]}
    assert route.calls.last.request.headers["Authorization"] == "Bearer tvly-test"
    assert json.loads(route.calls.last.request.content)["query"] == "pydantic strict mode"


def test_without_a_search_section_the_reviewer_has_no_web_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SEARCH_API_KEY", "old-style-key")
    dispatcher = _dispatcher(tmp_path, _MACHINE, {"TAVILY_API_KEY": "tvly-test"})
    assert not {"web_search", "read_url"} & _tool_names(dispatcher)
    assert _tool_names(dispatcher)  # the file tools are still there


def test_a_search_section_whose_key_is_missing_refuses(tmp_path: Path) -> None:
    with pytest.raises(SettingsFileError, match=r"search\.api_key_env"):
        _dispatcher(tmp_path, _MACHINE + _SEARCH, {})
