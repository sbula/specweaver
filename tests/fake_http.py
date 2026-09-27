# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Fake HTTP for the SDKs built on `httpx2`, and the guard that keeps tests off the network.

openai 3.x and anthropic 1.x send through `httpx2`. `respx` patches only `httpx`, so it cannot see
their requests — measured 2026-09-27, the first run on openai 3.19 sent a test's request to the
real `api.openai.com`. Use `fake_httpx2` for these SDKs; `respx` still serves `httpx` users
(google-genai, mistralai).

`block_real_httpx2` is applied to every test not marked `live` by `tests/conftest.py`: a request
that no fake answers fails the test instead of leaving the machine.
"""

from __future__ import annotations

import inspect
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import httpx2

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


@contextmanager
def fake_httpx2(handler: Callable[[httpx2.Request], Any]) -> Iterator[list[httpx2.Request]]:
    """Answer every `httpx2` request with `handler(request)`; yields the requests, in order.

    `handler` returns an `httpx2.Response`, or awaits one.
    """
    seen: list[httpx2.Request] = []

    async def handle(_transport: object, request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        response = handler(request)
        if inspect.isawaitable(response):
            response = await response
        return response

    with patch.object(httpx2.AsyncHTTPTransport, "handle_async_request", handle):
        yield seen


@contextmanager
def block_real_httpx2() -> Iterator[None]:
    """Any `httpx2` request fails loudly: a test never talks to a real server by accident."""

    def refuse(request: httpx2.Request) -> None:
        msg = f"a test tried to reach the network: {request.method} {request.url} — use fake_httpx2"
        raise RuntimeError(msg)

    async def refuse_async(_transport: object, request: httpx2.Request) -> None:
        refuse(request)

    with (
        patch.object(httpx2.AsyncHTTPTransport, "handle_async_request", refuse_async),
        patch.object(httpx2.HTTPTransport, "handle_request", lambda _t, request: refuse(request)),
    ):
        yield
