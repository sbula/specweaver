# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One adapter per server entry: its kind, its address, its key variable, its parallel limit.

Proves: C-FLOW-13 FR-7, FR-8

| Bucket | Case |
|---|---|
| Happy | a hosted server gets its kind's adapter and the key from the variable it names |
| Boundary | the limit is the server's `max_parallel`, keyed by the server's name |
| Degradation | a named key variable that is unset → unavailable, no other variable read |
| Hostile | a keyless local server never receives `OPENAI_API_KEY` |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.core.config.llm_settings import ServerEntry
from specweaver.infrastructure.llm.adapters.anthropic import AnthropicAdapter
from specweaver.infrastructure.llm.adapters.openai import OpenAICompatibleAdapter
from specweaver.infrastructure.llm.servers import adapter_for_server

if TYPE_CHECKING:
    import pytest

_GB10 = ServerEntry(
    kind="openai-compatible", base_url="http://gb10:8000/v1", private=True, max_parallel=4
)


def test_a_hosted_server_reads_the_key_variable_it_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORK_ANTHROPIC_KEY", "sk-work")
    server = ServerEntry(
        kind="anthropic", api_key_env="WORK_ANTHROPIC_KEY", private=False, max_parallel=3
    )

    adapter = adapter_for_server("work", server)

    assert isinstance(adapter._wrapped, AnthropicAdapter)
    assert adapter._wrapped._api_key == "sk-work"
    assert adapter.available() is True


def test_the_limit_is_the_servers_own(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = adapter_for_server("gb10", _GB10)

    assert (adapter._key, adapter._limit) == ("gb10", 4)
    assert isinstance(adapter._wrapped, OpenAICompatibleAdapter)
    assert adapter._wrapped._base_url == "http://gb10:8000/v1"


def test_an_unset_key_variable_leaves_the_server_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WORK_ANTHROPIC_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-personal")
    server = ServerEntry(
        kind="anthropic", api_key_env="WORK_ANTHROPIC_KEY", private=False, max_parallel=3
    )

    adapter = adapter_for_server("work", server)

    assert adapter.available() is False


def test_a_keyless_local_server_never_gets_the_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-openai-key")

    adapter = adapter_for_server("gb10", _GB10)

    assert adapter.available() is True
    assert adapter._wrapped._api_key != "sk-real-openai-key"
