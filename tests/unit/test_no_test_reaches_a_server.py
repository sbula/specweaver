# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A test not marked `live` cannot open a connection that leaves the machine, whatever opens it.

Proves: TECH-094 FR-4, FR-9
Proves: TECH-094 NFR-3 — the block below has no `CI` condition, so this canary runs in every local run

The canary for the guard in `tests/conftest.py`: if the guard is removed or weakened, these fail.
The outside addresses are documentation ranges (RFC 5737, RFC 3849) and a `.invalid` name, so a
missing guard sends nothing anywhere real.

| Bucket | Case |
|---|---|
| Happy | a connect to an outside address is refused, naming it |
| Boundary | loopback port 11434 (Ollama) is refused; another loopback port and IPv6 loopback answer; loopback names and numbers resolve |
| Degradation | `connect_ex` and an `asyncio` connection are refused the same way |
| Hostile | a host name is refused before it is resolved, and so is its lookup; an outside IPv6 address is refused |
"""

from __future__ import annotations

import asyncio
import socket
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

_REFUSED = "a test tried to reach the network"


def _tcp(family: int = socket.AF_INET) -> socket.socket:
    sock = socket.socket(family, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    return sock


@pytest.fixture()
def listener() -> Iterator[int]:
    """A server on a free loopback port, as a test's own fake server would be."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen()
    yield server.getsockname()[1]
    server.close()


def test_an_outside_address_is_refused() -> None:
    with _tcp() as sock, pytest.raises(RuntimeError, match=_REFUSED) as caught:
        sock.connect(("192.0.2.1", 443))
    assert "192.0.2.1" in str(caught.value)


def test_the_ollama_port_on_loopback_is_refused() -> None:
    with _tcp() as sock, pytest.raises(RuntimeError, match=_REFUSED):
        sock.connect(("127.0.0.1", 11434))


def test_a_loopback_server_of_the_test_answers(listener: int) -> None:
    with _tcp() as sock:
        sock.connect(("127.0.0.1", listener))


def test_ipv6_loopback_is_allowed() -> None:
    server = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    server.bind(("::1", 0))
    server.listen()
    with server, _tcp(socket.AF_INET6) as sock:
        sock.connect(("::1", server.getsockname()[1]))


def test_connect_ex_is_refused() -> None:
    with _tcp() as sock, pytest.raises(RuntimeError, match=_REFUSED):
        sock.connect_ex(("192.0.2.1", 80))


def test_an_async_connection_is_refused() -> None:
    async def reach() -> None:
        await asyncio.wait_for(asyncio.open_connection("192.0.2.1", 443), timeout=0.5)

    with pytest.raises(RuntimeError, match=_REFUSED):
        asyncio.run(reach())


def test_a_host_name_is_refused_before_it_is_resolved() -> None:
    with _tcp() as sock, pytest.raises(RuntimeError, match=_REFUSED):
        sock.connect(("api.example.invalid", 443))


def test_an_outside_ipv6_address_is_refused() -> None:
    with _tcp(socket.AF_INET6) as sock, pytest.raises(RuntimeError, match=_REFUSED):
        sock.connect(("2001:db8::1", 443))


def test_a_name_lookup_of_an_outside_host_is_refused() -> None:
    """A lookup already sends a DNS query off the machine, before any connection."""
    with pytest.raises(RuntimeError, match=_REFUSED):
        socket.getaddrinfo("api.example.invalid", 443)


def test_loopback_names_and_numbers_still_resolve() -> None:
    assert socket.getaddrinfo("localhost", 80)
    assert socket.getaddrinfo("192.0.2.1", 80)
