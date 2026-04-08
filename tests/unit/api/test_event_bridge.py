# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

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

    # --- Gap #11: QueueFull backpressure ---

    @pytest.mark.asyncio
    async def test_broadcast_drops_event_when_queue_full(self) -> None:
        """_broadcast silently drops events when a subscriber queue is full."""
        bridge = EventBridge()
        queue = bridge.subscribe("r1")

        # Fill the queue to capacity (maxsize=100)
        for i in range(100):
            queue.put_nowait({"event": f"fill_{i}"})

        # Broadcast should not raise, just silently drop
        await bridge._broadcast("r1", {"event": "overflow"})
        assert queue.qsize() == 100  # still full, overflow dropped

    # --- Gap #12: Error path in background task ---

    @pytest.mark.asyncio
    async def test_wrapper_broadcasts_none_on_coroutine_failure(self) -> None:
        """Background task broadcasts None to subscribers even on exception."""
        bridge = EventBridge()
        queue = bridge.subscribe("r1")

        async def _failing() -> None:
            msg = "boom"
            raise RuntimeError(msg)

        bridge.start_run("r1", _failing())
        await asyncio.sleep(0.1)

        # Subscriber should receive None (completion signal despite error)
        msg = queue.get_nowait()
        assert msg is None

    # --- Gap #13: get_result returns result after completion ---

    @pytest.mark.asyncio
    async def test_get_result_returns_value_after_completion(self) -> None:
        """get_result returns the coroutine's return value after completion."""
        bridge = EventBridge()

        async def _returning() -> str:
            return "my_result"

        bridge.start_run("r1", _returning())
        await asyncio.sleep(0.1)

        assert bridge.get_result("r1") == "my_result"

    # --- Gap #14: get_result returns None for unknown ---

    def test_get_result_returns_none_for_unknown(self) -> None:
        """get_result returns None for an unknown run_id."""
        bridge = EventBridge()
        assert bridge.get_result("nonexistent") is None

    # --- Gap #15: Callback handles result kwarg ---

    @pytest.mark.asyncio
    async def test_callback_includes_result_fields(self) -> None:
        """make_event_callback serializes StepResult fields into event record."""
        from unittest.mock import MagicMock

        from specweaver.flow.state import StepStatus

        bridge = EventBridge()
        queue = bridge.subscribe("r1")
        cb = bridge.make_event_callback("r1")

        mock_result = MagicMock()
        mock_result.status = StepStatus.PASSED
        mock_result.error_message = None
        mock_result.output = {"key": "val"}

        cb("step_completed", result=mock_result)
        await asyncio.sleep(0.05)

        msg = queue.get_nowait()
        assert msg["event"] == "step_completed"
        assert msg["result"]["status"] == "passed"
        assert msg["result"]["output"] == {"key": "val"}

    # --- Gap #16: Callback handles run kwarg ---

    @pytest.mark.asyncio
    async def test_callback_includes_run_fields(self) -> None:
        """make_event_callback serializes PipelineRun fields into event record."""
        from unittest.mock import MagicMock

        from specweaver.flow.state import RunStatus

        bridge = EventBridge()
        queue = bridge.subscribe("r1")
        cb = bridge.make_event_callback("r1")

        mock_run = MagicMock()
        mock_run.run_id = "r1"
        mock_run.status = RunStatus.COMPLETED

        cb("run_completed", run=mock_run)
        await asyncio.sleep(0.05)

        msg = queue.get_nowait()
        assert msg["event"] == "run_completed"
        assert msg["run_id"] == "r1"
        assert msg["run_status"] == "completed"

    # --- Gap #17: unsubscribe no-op for unknown queue ---

    def test_unsubscribe_unknown_queue_is_noop(self) -> None:
        """unsubscribe with unknown queue does not raise."""
        bridge = EventBridge()
        bridge.subscribe("r1")
        fake_queue: asyncio.Queue[dict[str, object] | None] = asyncio.Queue()
        # Should not raise
        bridge.unsubscribe("r1", fake_queue)
        assert len(bridge._subscribers["r1"]) == 1  # original still there

    # --- Gap #18: unsubscribe no-op for unknown run_id ---

    def test_unsubscribe_unknown_run_id_is_noop(self) -> None:
        """unsubscribe with unknown run_id does not raise."""
        bridge = EventBridge()
        fake_queue: asyncio.Queue[dict[str, object] | None] = asyncio.Queue()
        # Should not raise
        bridge.unsubscribe("nonexistent", fake_queue)

    # --- Gap #19: active_count ignores done tasks ---

    @pytest.mark.asyncio
    async def test_active_count_ignores_done_tasks(self) -> None:
        """active_count only counts tasks that are not done."""
        bridge = EventBridge()

        async def _quick() -> str:
            return "ok"

        bridge.start_run("r1", _quick())
        await asyncio.sleep(0.1)

        # Task is done, active_count should be 0
        assert bridge.active_count == 0

    # --- Gap #20: Multiple subscribers fan-out ---

    @pytest.mark.asyncio
    async def test_multiple_subscribers_all_receive_events(self) -> None:
        """Multiple subscribers for the same run_id all receive events."""
        bridge = EventBridge()
        q1 = bridge.subscribe("r1")
        q2 = bridge.subscribe("r1")
        q3 = bridge.subscribe("r1")

        await bridge._broadcast("r1", {"event": "test"})

        assert q1.get_nowait() == {"event": "test"}
        assert q2.get_nowait() == {"event": "test"}
        assert q3.get_nowait() == {"event": "test"}

    # --- Gap #59: Callback no-loop fallback ---

    def test_callback_noop_when_no_event_loop(self) -> None:
        """make_event_callback silently does nothing when no event loop is running."""
        bridge = EventBridge()
        cb = bridge.make_event_callback("r1")
        # Call outside of async context — should not raise
        cb("step_started", step_idx=0, step_name="test", total_steps=1)

    # --- Gap #60: Callback handles verdict kwarg ---

    @pytest.mark.asyncio
    async def test_callback_includes_verdict(self) -> None:
        """make_event_callback includes verdict kwarg in event record."""
        bridge = EventBridge()
        queue = bridge.subscribe("r1")
        cb = bridge.make_event_callback("r1")

        cb("step_completed", verdict="pass")
        await asyncio.sleep(0.05)

        msg = queue.get_nowait()
        assert msg["event"] == "step_completed"
        assert msg["verdict"] == "pass"

    # --- Gap #61: Broadcast with no subscribers ---

    @pytest.mark.asyncio
    async def test_broadcast_no_subscribers_is_noop(self) -> None:
        """_broadcast with no subscribers for a run_id is a silent no-op."""
        bridge = EventBridge()
        # Should not raise
        await bridge._broadcast("no_such_run", {"event": "test"})
