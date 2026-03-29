# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Event bridge — background pipeline task registry + WebSocket broadcast.

Manages async background pipeline runs with a configurable concurrency limit.
WebSocket subscribers receive real-time NDJSON events via asyncio queues.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

MAX_CONCURRENT_RUNS = 3


class EventBridge:
    """Central registry for background pipeline runs.

    Manages:
    - Task registry: ``dict[run_id, asyncio.Task]`` with max concurrent limit
    - Event queues: ``dict[run_id, list[asyncio.Queue]]`` for WebSocket subscribers
    - Auto-cleanup of completed tasks
    """

    def __init__(self, max_concurrent: int = MAX_CONCURRENT_RUNS) -> None:
        self._max_concurrent = max_concurrent
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any] | None]]] = {}
        self._results: dict[str, Any] = {}

    @property
    def active_count(self) -> int:
        """Number of currently running tasks."""
        return sum(1 for t in self._tasks.values() if not t.done())

    def start_run(
        self,
        run_id: str,
        coro: Any,
    ) -> None:
        """Start a pipeline run as a background task.

        Args:
            run_id: Unique run identifier.
            coro: The awaitable coroutine (e.g. ``runner.run()``).

        Raises:
            RuntimeError: If at max concurrent limit.
            ValueError: If run_id already active.
        """
        # Clean up finished tasks first
        self._cleanup_done()

        if self.active_count >= self._max_concurrent:
            msg = (
                f"Max concurrent runs reached ({self._max_concurrent}). Wait for a run to complete."
            )
            raise RuntimeError(msg)

        if run_id in self._tasks and not self._tasks[run_id].done():
            msg = f"Run '{run_id}' is already active."
            raise ValueError(msg)

        self._subscribers.setdefault(run_id, [])

        async def _wrapper() -> Any:
            try:
                result = await coro
                self._results[run_id] = result
                # Notify subscribers that the run is done
                await self._broadcast(run_id, None)
                return result
            except Exception:
                logger.exception("Background run %s failed", run_id)
                await self._broadcast(run_id, None)
                raise

        self._tasks[run_id] = asyncio.create_task(_wrapper())
        logger.info(
            "Started background run %s (%d/%d active)",
            run_id,
            self.active_count,
            self._max_concurrent,
        )

    def make_event_callback(self, run_id: str) -> Any:
        """Create an on_event callback that broadcasts to subscribers.

        Returns a callable matching the ``RunnerEventCallback`` protocol.
        """

        def _on_event(event: str, **kwargs: Any) -> None:
            record: dict[str, Any] = {"event": event}

            if "step_idx" in kwargs:
                record["step_idx"] = kwargs["step_idx"]
            if "step_name" in kwargs:
                record["step_name"] = kwargs["step_name"]
            if "total_steps" in kwargs:
                record["total_steps"] = kwargs["total_steps"]
            if "verdict" in kwargs:
                record["verdict"] = kwargs["verdict"]

            result = kwargs.get("result")
            if result is not None:
                record["result"] = {
                    "status": result.status.value,
                    "error_message": result.error_message or None,
                    "output": result.output,
                }

            run = kwargs.get("run")
            if run is not None:
                record["run_id"] = run.run_id
                record["run_status"] = run.status.value

            # Schedule broadcast (non-blocking from sync context)
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(self._broadcast(run_id, record))
                task.add_done_callback(lambda t: None)  # prevent GC
            except RuntimeError:
                pass  # No loop running (e.g. during tests)

        return _on_event

    async def _broadcast(
        self,
        run_id: str,
        message: dict[str, Any] | None,
    ) -> None:
        """Send a message to all subscribers of a run.

        Args:
            run_id: The run to broadcast for.
            message: The event dict, or None to signal completion.
        """
        for queue in self._subscribers.get(run_id, []):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("Queue full for run %s, dropping event", run_id)

    def subscribe(self, run_id: str) -> asyncio.Queue[dict[str, Any] | None]:
        """Subscribe to events for a run.

        Returns:
            An asyncio.Queue that receives event dicts (None = done).
        """
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=100)
        self._subscribers.setdefault(run_id, []).append(queue)
        logger.debug(
            "Subscriber added for run %s (total: %d)", run_id, len(self._subscribers[run_id])
        )
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue[dict[str, Any] | None]) -> None:
        """Remove a subscriber queue."""
        subs = self._subscribers.get(run_id, [])
        if queue in subs:
            subs.remove(queue)

    def get_result(self, run_id: str) -> Any:
        """Get the PipelineRun result for a completed run, or None."""
        return self._results.get(run_id)

    def is_active(self, run_id: str) -> bool:
        """Check if a run is currently active (not done)."""
        task = self._tasks.get(run_id)
        return task is not None and not task.done()

    def _cleanup_done(self) -> None:
        """Remove references to completed tasks."""
        done_ids = [rid for rid, t in self._tasks.items() if t.done()]
        for rid in done_ids:
            del self._tasks[rid]
            # Keep subscribers and results for a bit (for late joiners)

    def serialize_event(self, event: dict[str, Any]) -> str:
        """Serialize an event dict to a JSON string."""
        return json.dumps(event, default=str)
