# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A provider's default key goes only to that provider's own address.

Proves: C-FLOW-13 FR-7

| Bucket | Case |
|---|---|
| Happy | `kind = "openai"` with no address reads `OPENAI_API_KEY` |
| Boundary | an explicit `api_key_env` is used whatever the address |
| Degradation | not applicable — an unset variable is proven by the resolver tests |
| Hostile | `kind = "openai"` pointed at another host without its own key variable is refused |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.llm_settings import ServerEntry


def _server(**fields) -> ServerEntry:
    return ServerEntry(kind="openai", private=False, max_parallel=1, **fields)


def test_the_providers_own_address_reads_its_default_key() -> None:
    assert _server().api_key_env == "OPENAI_API_KEY"


def test_the_providers_own_domain_reads_its_default_key() -> None:
    assert _server(base_url="https://eu.api.openai.com/v1").api_key_env == "OPENAI_API_KEY"


@pytest.mark.parametrize(
    "address",
    [
        "http://elsewhere.example/v1",
        "https://openai.com.evil.example/v1",
        "https://notopenai.com/v1",
    ],
)
def test_another_host_without_its_own_key_variable_is_refused(address: str) -> None:
    with pytest.raises(ValueError, match="needs its own api_key_env"):
        _server(base_url=address)


def test_an_explicit_key_variable_is_used_for_any_address() -> None:
    server = _server(base_url="http://proxy.example/v1", api_key_env="PROXY_KEY")

    assert server.api_key_env == "PROXY_KEY"
