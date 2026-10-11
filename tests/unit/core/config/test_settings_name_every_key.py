# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The settings name every key variable; the code holds none `[agreed 2026-10-11]`.

Proves: C-FLOW-13 FR-7, NFR-2

| Bucket | Case |
|---|---|
| Happy | a cloud server that names its key variable loads, and its adapter gets that key |
| Boundary | a local `openai-compatible` server needs no key variable |
| Degradation | a cloud server that names none is refused, naming the key to set |
| Hostile | a provider's usual variable set in the shell is never read by an adapter on its own |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.llm_settings import SettingsFileError, parse_machine_file
from specweaver.infrastructure.llm.adapters.registry import get_all_adapters
from specweaver.infrastructure.llm.servers import adapter_for_server


def _server(kind: str, extra: str = "") -> str:
    return f'[servers.s]\nkind = "{kind}"\nprivate = false\nmax_parallel = 1\n{extra}'


@pytest.mark.parametrize("kind", ["gemini", "openai", "anthropic", "mistral"])
def test_a_cloud_server_without_a_key_variable_is_refused(kind: str) -> None:
    with pytest.raises(SettingsFileError) as caught:
        parse_machine_file(_server(kind), "settings.toml")

    assert caught.value.key == "servers.s"
    assert "api_key_env" in caught.value.message


def test_a_local_server_needs_no_key_variable() -> None:
    text = _server("openai-compatible", 'base_url = "http://gb10:8000/v1"\n')

    assert parse_machine_file(text, "settings.toml").servers["s"].api_key_env is None


def test_the_named_variable_is_the_one_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_GEMINI", "mine")
    monkeypatch.setenv("GEMINI_API_KEY", "not-mine")
    server = parse_machine_file(
        _server("gemini", 'api_key_env = "MY_GEMINI"\n'), "settings.toml"
    ).servers["s"]

    assert adapter_for_server("s", server)._wrapped._api_key == "mine"


@pytest.mark.parametrize(
    "variable",
    [
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "MISTRAL_API_KEY",
        "DASHSCOPE_API_KEY",
    ],
)
def test_no_adapter_reads_a_key_on_its_own(monkeypatch: pytest.MonkeyPatch, variable: str) -> None:
    monkeypatch.setenv(variable, "from-the-shell")

    shipped = {
        kind: cls
        for kind, cls in get_all_adapters().items()
        if cls.__module__.startswith("specweaver.")
    }
    assert len(shipped) >= 5
    for kind, adapter_cls in shipped.items():
        base = None if adapter_cls.default_base_url else "http://local.example/v1"
        assert adapter_cls(base_url=base)._api_key != "from-the-shell", kind
        assert not hasattr(adapter_cls, "api_key_env_var"), kind
