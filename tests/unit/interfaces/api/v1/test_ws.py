# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for WebSocket pipeline streaming endpoint."""

from __future__ import annotations

import json

import pytest

from specweaver.core.config.database import Database
from specweaver.interfaces.api.app import create_app, set_event_bridge
from specweaver.interfaces.api.event_bridge import EventBridge


@pytest.fixture()
def _db(tmp_path):
    """Creates a temp database."""
    from specweaver.interfaces.cli._db_utils import bootstrap_database

    bootstrap_database(str(tmp_path / "test.db"))
    return Database(db_path=tmp_path / "test.db")


@pytest.fixture()
def bridge():
    """Fresh EventBridge for each test."""
    b = EventBridge()
    set_event_bridge(b)
    return b


@pytest.fixture()
def client(_db, bridge):
    """TestClient for the API."""
    from starlette.testclient import TestClient

    app = create_app(db=_db)
    return TestClient(app)


class TestWebSocket:
    """Tests for WS /api/v1/ws/pipeline/{run_id}."""

    def test_ws_connect_and_receive_event(self, client, bridge) -> None:
        """WebSocket connects and receives a broadcast event."""
        # Pre-subscribe a queue and push an event, then connect
        # We need to test via the TestClient WebSocket support
        with client.websocket_connect("/api/v1/ws/pipeline/test-run-1") as ws:
            # Push event via bridge (runs in the background)
            queue_list = bridge._subscribers.get("test-run-1", [])
            assert len(queue_list) == 1  # WS handler subscribed

            # Push an event directly to the queue
            queue_list[0].put_nowait({"event": "step_started", "step_name": "validate"})
            # Push completion
            queue_list[0].put_nowait(None)

            # Read events
            msg1 = ws.receive_text()
            data1 = json.loads(msg1)
            assert data1["event"] == "step_started"
            assert data1["step_name"] == "validate"

            msg2 = ws.receive_text()
            data2 = json.loads(msg2)
            assert data2["event"] == "done"

    def test_ws_done_event_on_completion(self, client, bridge) -> None:
        """WebSocket sends {"event": "done"} when run completes."""
        with client.websocket_connect("/api/v1/ws/pipeline/test-run-2") as ws:
            queue_list = bridge._subscribers.get("test-run-2", [])
            queue_list[0].put_nowait(None)

            msg = ws.receive_text()
            assert json.loads(msg)["event"] == "done"

    def test_ws_unsubscribes_on_close(self, client, bridge) -> None:
        """WebSocket unsubscribes when connection closes."""
        with client.websocket_connect("/api/v1/ws/pipeline/test-run-3") as ws:
            queue_list = bridge._subscribers.get("test-run-3", [])
            assert len(queue_list) == 1
            # Send completion to cleanly close
            queue_list[0].put_nowait(None)
            ws.receive_text()  # consume the "done" message

        # After close, subscriber should be removed
        assert len(bridge._subscribers.get("test-run-3", [])) == 0

    # --- Gap #46: Multiple events before done ---

    def test_ws_receives_multiple_events_before_done(self, client, bridge) -> None:
        """WebSocket receives multiple events in sequence before done signal."""
        with client.websocket_connect("/api/v1/ws/pipeline/test-run-4") as ws:
            queue_list = bridge._subscribers.get("test-run-4", [])

            # Push multiple events
            queue_list[0].put_nowait({"event": "step_started", "step_idx": 0})
            queue_list[0].put_nowait({"event": "step_completed", "step_idx": 0})
            queue_list[0].put_nowait({"event": "step_started", "step_idx": 1})
            queue_list[0].put_nowait(None)  # completion

            msgs = []
            for _ in range(4):
                msgs.append(json.loads(ws.receive_text()))

            assert msgs[0]["event"] == "step_started"
            assert msgs[1]["event"] == "step_completed"
            assert msgs[2]["event"] == "step_started"
            assert msgs[3]["event"] == "done"

    # --- Gap #47: Client disconnect ---

    def test_ws_handles_client_disconnect(self, client, bridge) -> None:
        """WebSocket handles early client disconnect gracefully."""
        with client.websocket_connect("/api/v1/ws/pipeline/test-run-5") as _ws:
            queue_list = bridge._subscribers.get("test-run-5", [])
            assert len(queue_list) == 1

        # After context manager exits (disconnect), subscriber should be cleaned
        assert len(bridge._subscribers.get("test-run-5", [])) == 0
