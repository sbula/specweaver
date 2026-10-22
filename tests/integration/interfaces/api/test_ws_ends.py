# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A run's WebSocket never waits for nothing: an unknown or ended run ends the stream at once, and a
client that leaves ends its subscription.

Proves: D-UI-01 FR-2

The real app, settings, run registry and runner; for the leaving client the run is made to wait.

| Bucket | Case |
|---|---|
| Happy | a run that already finished answers `done` and closes |
| Boundary | a client that leaves a running run's stream is no longer subscribed |
| Degradation | not applicable — the stream has no outside dependency |
| Hostile | a run id nobody started answers `RUN_NOT_FOUND` and closes |
"""

from __future__ import annotations

import asyncio
import signal
import time
from typing import TYPE_CHECKING

import pytest
from starlette.testclient import TestClient

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.interfaces.api import event_bridge
from specweaver.interfaces.api.app import create_app
from tests.api_token import AUTH, TEST_TOKEN

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _fails_instead_of_hanging() -> Iterator[None]:
    """A stream that waits for nothing would hang the suite, and the nightly mutation run with it;
    after 10 s it fails instead (where the platform has SIGALRM)."""
    if not hasattr(signal, "SIGALRM"):
        yield
        return

    def _hung(_signum: int, _frame: object) -> None:
        raise TimeoutError("the WebSocket waited for nothing")

    previous = signal.signal(signal.SIGALRM, _hung)
    signal.alarm(10)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


_PIPELINE = """\
name: one_validate
version: "1.0"
steps:
  - name: validate_spec
    action: validate
    target: spec
"""


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    data = tmp_path / "data"
    data.mkdir()
    (data / "settings.toml").write_text("[serve]\nmax_runs = 2\n", encoding="utf-8")
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    monkeypatch.chdir(tmp_path)
    own = tmp_path / "proj" / ".specweaver" / "pipelines"
    own.mkdir(parents=True)
    (own / "one_validate.yaml").write_text(_PIPELINE, encoding="utf-8")
    path = data / "specweaver.db"
    bootstrap_database(str(path))
    project = tmp_path / "proj"
    (project / "specs").mkdir(parents=True)
    (project / "specs" / "a_spec.md").write_text("# A\n## 1. Purpose\nDoes A.\n")
    event_bridge.set_event_bridge(event_bridge.EventBridge())
    client = TestClient(create_app(token=TEST_TOKEN, db=Database(path)), headers=AUTH)
    client.post("/api/v1/projects", json={"name": "rest", "path": str(project), "scaffold": False})
    return client


def _start(client: TestClient) -> str:
    started = client.post(
        "/api/v1/pipelines/one_validate/run",
        json={"project": "rest", "spec": "specs/a_spec.md"},
    )
    assert started.status_code == 200, started.text
    return started.json()["run_id"]


def test_an_unknown_run_answers_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with (
        _client(tmp_path, monkeypatch) as client,
        client.websocket_connect("/api/v1/ws/pipeline/nobody") as socket,
    ):
        message = socket.receive_json()

    assert message == {"event": "error", "error_code": "RUN_NOT_FOUND"}


def test_a_finished_run_answers_done(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        run_id = _start(client)
        for _ in range(100):
            if not event_bridge.get_event_bridge().is_active(run_id):
                break
            time.sleep(0.05)
        with client.websocket_connect(f"/api/v1/ws/pipeline/{run_id}") as socket:
            message = socket.receive_json()

    assert message == {"event": "done"}


def test_a_client_that_leaves_is_unsubscribed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _waits(_self: PipelineRunner, *_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(30)

    monkeypatch.setattr(PipelineRunner, "run", _waits)
    with _client(tmp_path, monkeypatch) as client:
        run_id = _start(client)
        with client.websocket_connect(f"/api/v1/ws/pipeline/{run_id}"):
            pass
        bridge = event_bridge.get_event_bridge()
        for _ in range(100):
            if not bridge._subscribers.get(run_id):
                break
            time.sleep(0.05)

        assert bridge.is_active(run_id)
        assert bridge._subscribers.get(run_id) == []
