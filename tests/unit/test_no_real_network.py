# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A test cannot reach a real server through `httpx2`, and a fake answers in its place."""

from __future__ import annotations

import httpx2
import pytest

from tests.fake_http import fake_httpx2


@pytest.mark.asyncio
async def test_a_real_request_fails_the_test() -> None:
    async with httpx2.AsyncClient() as client:
        with pytest.raises(RuntimeError, match="network"):
            await client.get("https://api.openai.com/v1/models")


def test_a_real_sync_request_fails_the_test() -> None:
    with httpx2.Client() as client, pytest.raises(RuntimeError, match="network"):
        client.get("https://api.anthropic.com/v1/models")


@pytest.mark.asyncio
async def test_a_fake_answers_and_records_the_request() -> None:
    with fake_httpx2(lambda request: httpx2.Response(200, json={"ok": True})) as seen:
        async with httpx2.AsyncClient() as client:
            response = await client.post("http://gb10:8000/v1/chat/completions", json={"a": 1})

    assert response.json() == {"ok": True}
    assert [str(request.url) for request in seen] == ["http://gb10:8000/v1/chat/completions"]
