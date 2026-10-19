# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Only the holder of the server's token is served: a web page, another program or user is not.

Proves: D-UI-01 FR-6, NFR-1

The real app over a real database, through `TestClient`; every kind of route is asked once without
the token and once with it.

| Bucket | Case |
|---|---|
| Happy | the header, the browser cookie and the WebSocket's query each let a request through |
| Boundary | the health check answers without a token; a first visit with `?token=` sets the cookie and drops the token from the address |
| Degradation | a wrong token is refused like none, with the API's error shape |
| Hostile | an API call, a dashboard page, a cross-site form post and the WebSocket without the token are refused, also from a rebinding page's `Host`; the token is in no answer |
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.interfaces.api.app import create_app

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_TOKEN = "test-token-0123456789abcdef"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    path = tmp_path / "specweaver.db"
    bootstrap_database(str(path))
    return TestClient(create_app(db=Database(path), token=_TOKEN))


@pytest.mark.parametrize(
    ("method", "url", "kwargs"),
    [
        ("get", "/api/v1/projects", {}),
        ("get", "/dashboard", {}),
        ("post", "/dashboard/runs/r1/gate", {"data": {"action": "approve"}}),
        ("post", "/api/v1/projects/demo/use", {}),
    ],
    ids=["api", "dashboard", "cross-site-form", "simple-post"],
)
def test_no_token_no_answer(client: TestClient, method: str, url: str, kwargs: dict) -> None:
    response = getattr(client, method)(url, follow_redirects=False, **kwargs)

    assert response.status_code == 401
    assert response.json() == {"detail": "a token is required", "error_code": "UNAUTHORIZED"}


def test_a_rebinding_page_is_refused(client: TestClient) -> None:
    response = client.get("/api/v1/projects", headers={"Host": "evil.example:8000"})

    assert response.status_code == 401


def test_a_wrong_token_is_refused(client: TestClient) -> None:
    response = client.get("/api/v1/projects", headers={"Authorization": "Bearer wrong"})

    assert response.status_code == 401


def test_the_header_lets_a_program_through(client: TestClient) -> None:
    response = client.get("/api/v1/projects", headers={"Authorization": f"Bearer {_TOKEN}"})

    assert response.status_code == 200


def test_the_health_check_needs_no_token(client: TestClient) -> None:
    assert client.get("/healthz").status_code == 200


def test_a_first_visit_sets_the_cookie_and_drops_the_token(client: TestClient) -> None:
    first = client.get(f"/dashboard?token={_TOKEN}", follow_redirects=False)

    assert first.status_code == 303
    assert first.headers["location"] == "/dashboard"
    cookie = first.headers["set-cookie"]
    assert f"sw_token={_TOKEN}" in cookie
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/" in cookie
    assert client.get("/dashboard").status_code == 200


def test_the_websocket_needs_the_token(client: TestClient) -> None:
    with (
        pytest.raises(WebSocketDisconnect) as refused,
        client.websocket_connect("/api/v1/ws/pipeline/r1"),
    ):
        pass

    assert refused.value.code == 1008


class _OneEventBridge:
    """A run that sends one event and ends, so the socket closes by itself."""

    def subscribe(self, _run_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        queue.put_nowait({"event": "step_started"})
        queue.put_nowait(None)
        return queue

    def unsubscribe(self, _run_id: str, _queue: asyncio.Queue) -> None:
        pass


def test_the_websocket_takes_the_token_in_its_query(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from specweaver.interfaces.api import event_bridge

    monkeypatch.setattr(event_bridge, "get_event_bridge", _OneEventBridge)

    with client.websocket_connect(f"/api/v1/ws/pipeline/r1?token={_TOKEN}") as socket:
        events = [socket.receive_json(), socket.receive_json()]

    assert events == [{"event": "step_started"}, {"event": "done"}]


def test_the_token_is_in_no_answer(client: TestClient) -> None:
    refused = client.get("/api/v1/projects")
    served = client.get("/api/v1/projects", headers={"Authorization": f"Bearer {_TOKEN}"})

    assert _TOKEN not in refused.text and _TOKEN not in served.text
