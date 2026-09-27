# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every client is built with an explicit address; no environment variable can redirect it.

Proves: C-FLOW-13 FR-7

| Bucket | Case |
|---|---|
| Happy | each kind's client uses the address it was given |
| Boundary | with no address, each kind uses its official one, written out |
| Degradation | an empty key means no key: the adapter is unavailable and reads no variable |
| Hostile | `OPENAI_BASE_URL`, `ANTHROPIC_BASE_URL`, `GOOGLE_GEMINI_BASE_URL` set to another host are ignored; a local server and DashScope need an address |
"""

from __future__ import annotations

from typing import Any

import pytest

from specweaver.infrastructure.llm.adapters.anthropic import AnthropicAdapter
from specweaver.infrastructure.llm.adapters.gemini import GeminiAdapter
from specweaver.infrastructure.llm.adapters.mistral import MistralAdapter
from specweaver.infrastructure.llm.adapters.openai import OpenAIAdapter, OpenAICompatibleAdapter
from specweaver.infrastructure.llm.adapters.qwen import QwenAdapter


def _address(adapter: Any) -> str:
    client = adapter._get_client()
    if isinstance(adapter, GeminiAdapter):
        return str(client._api_client._http_options.base_url)
    if isinstance(adapter, MistralAdapter):
        return str(client.sdk_configuration.server_url)
    return str(client.base_url)


_OFFICIAL = [
    (OpenAIAdapter, "https://api.openai.com/v1"),
    (AnthropicAdapter, "https://api.anthropic.com"),
    (GeminiAdapter, "https://generativelanguage.googleapis.com/"),
    (MistralAdapter, "https://api.mistral.ai"),
]


@pytest.fixture()
def hostile_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("OPENAI_BASE_URL", "ANTHROPIC_BASE_URL", "GOOGLE_GEMINI_BASE_URL"):
        monkeypatch.setenv(name, "http://attacker.example")


@pytest.mark.parametrize(("adapter_cls", "official"), _OFFICIAL)
def test_without_an_address_the_official_one_is_used(
    adapter_cls: type, official: str, hostile_env: None
) -> None:
    address = _address(adapter_cls(api_key="k"))

    assert address.rstrip("/") == official.rstrip("/")


@pytest.mark.parametrize("adapter_cls", [*(cls for cls, _ in _OFFICIAL), QwenAdapter])
def test_a_given_address_is_used(adapter_cls: type, hostile_env: None) -> None:
    address = _address(adapter_cls(api_key="k", base_url="http://proxy.local:9000/v1"))

    assert address.rstrip("/") == "http://proxy.local:9000/v1"


def test_a_local_server_uses_its_address(hostile_env: None) -> None:
    adapter = OpenAICompatibleAdapter(api_key="k", base_url="http://gb10:8000/v1")

    assert _address(adapter).rstrip("/") == "http://gb10:8000/v1"


@pytest.mark.parametrize("adapter_cls", [OpenAICompatibleAdapter, QwenAdapter])
def test_a_server_without_an_official_address_needs_one(adapter_cls: type) -> None:
    with pytest.raises(ValueError, match="address"):
        adapter_cls(api_key="k")


@pytest.mark.parametrize("adapter_cls", [*(cls for cls, _ in _OFFICIAL), QwenAdapter])
def test_an_empty_key_reads_no_variable(adapter_cls: type, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(adapter_cls.api_key_env_var, "sk-from-the-environment")
    address = {"base_url": "https://proxy.local/v1"}

    assert adapter_cls(api_key="", **address).available() is False
    assert adapter_cls(api_key=None, **address).available() is True


def test_gemini_is_never_rerouted_to_vertex(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "someone-elses-project")

    client = GeminiAdapter(api_key="k")._get_client()

    assert client._api_client.vertexai is False
    assert (
        str(client._api_client._http_options.base_url)
        == "https://generativelanguage.googleapis.com/"
    )


@pytest.mark.asyncio
async def test_gemini_sends_exactly_the_sampling_that_is_set() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from specweaver.infrastructure.llm.models import GenerationConfig, Message, Role

    adapter = GeminiAdapter(api_key="k")
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("stop here"))
    adapter._client = client

    async def sent(config: GenerationConfig):
        with pytest.raises(Exception, match="stop here"):
            await adapter.generate([Message(role=Role.USER, content="x")], config)
        return client.aio.models.generate_content.call_args.kwargs["config"]

    unset = await sent(GenerationConfig(model="m"))
    full = await sent(GenerationConfig(model="m", temperature=1.0, top_p=0.95, top_k=40))

    assert (unset.temperature, unset.top_p, unset.top_k) == (None, None, None)
    assert (full.temperature, full.top_p, full.top_k) == (1.0, 0.95, 40)
