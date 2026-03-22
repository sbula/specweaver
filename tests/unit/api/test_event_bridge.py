# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Unit tests for EventBridge — background task registry."""

from __future__ import annotations

import asyncio

import pytest

from specweaver.api.event_bridge import EventBridge


class TestEventBridge:
    """Tests for the EventBridge class."""

    @pytest.mark.asyncio
    async def test_start_run_creates_task(self) -> None:
        """start_run creates a background task that runs the coroutine."""
        bridge = EventBridge()
        result_holder: list[str] = []

        async def _dummy() -> str:
            result_holder.append("done")
            return "ok"

        bridge.start_run("r1", _dummy())
        assert bridge.active_count == 1

        # Let the task complete
        await asyncio.sleep(0.1)
        assert result_holder == ["done"]

    @pytest.mark.asyncio
    async def test_max_concurrent_enforced(self) -> None:
        """start_run raises RuntimeError when at max concurrent."""
        bridge = EventBridge(max_concurrent=2)

        async def _slow() -> None:
            await asyncio.sleep(10)

        bridge.start_run("r1", _slow())
        bridge.start_run("r2", _slow())

        with pytest.raises(RuntimeError, match="Max concurrent"):
            bridge.start_run("r3", _slow())

        # Cleanup
        for task in bridge._tasks.values():
            task.cancel()

    @pytest.mark.asyncio
    async def test_subscribe_receives_events(self) -> None:
        """Subscribers receive broadcast events."""
        bridge = EventBridge()
        queue = bridge.subscribe("r1")

        await bridge._broadcast("r1", {"event": "step_started"})
        msg = queue.get_nowait()
        assert msg == {"event": "step_started"}

    @pytest.mark.asyncio
    async def test_subscribe_receives_none_on_completion(self) -> None:
        """Subscribers receive None when the run completes."""
        bridge = EventBridge()
        queue = bridge.subscribe("r1")

        async def _quick() -> str:
            return "done"

        bridge.start_run("r1", _quick())
        await asyncio.sleep(0.1)

        # Should have received None (completion signal)
        msg = queue.get_nowait()
        assert msg is None

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_queue(self) -> None:
        """unsubscribe removes the queue from subscribers."""
        bridge = EventBridge()
        queue = bridge.subscribe("r1")
        assert len(bridge._subscribers["r1"]) == 1

        bridge.unsubscribe("r1", queue)
        assert len(bridge._subscribers["r1"]) == 0

    @pytest.mark.asyncio
    async def test_make_event_callback(self) -> None:
        """make_event_callback returns a callable matching RunnerEventCallback."""
        bridge = EventBridge()
        queue = bridge.subscribe("r1")

        cb = bridge.make_event_callback("r1")
        # Call it like the runner would
        cb("step_started", step_idx=0, step_name="validate", total_steps=3)

        # Give the scheduled broadcast a chance to run
        await asyncio.sleep(0.05)
        msg = queue.get_nowait()
        assert msg["event"] == "step_started"
        assert msg["step_name"] == "validate"

    @pytest.mark.asyncio
    async def test_duplicate_run_id_raises(self) -> None:
        """start_run raises ValueError if run_id is already active."""
        bridge = EventBridge()

        async def _slow() -> None:
            await asyncio.sleep(10)

        bridge.start_run("r1", _slow())

        with pytest.raises(ValueError, match="already active"):
            bridge.start_run("r1", _slow())

        # Cleanup
        for task in bridge._tasks.values():
            task.cancel()

    @pytest.mark.asyncio
    async def test_cleanup_done_frees_slots(self) -> None:
        """Completed tasks are cleaned up, freeing concurrency slots."""
        bridge = EventBridge(max_concurrent=1)

        async def _quick() -> str:
            return "ok"

        bridge.start_run("r1", _quick())
        await asyncio.sleep(0.1)

        # r1 is done, we should be able to start another
        bridge.start_run("r2", _quick())
        assert bridge.active_count <= 1

    def test_is_active_false_when_no_run(self) -> None:
        """is_active returns False for unknown run_id."""
        bridge = EventBridge()
        assert bridge.is_active("nonexistent") is False

    def test_serialize_event(self) -> None:
        """serialize_event returns JSON string."""
        bridge = EventBridge()
        s = bridge.serialize_event({"event": "test", "data": 42})
        assert '"event": "test"' in s
