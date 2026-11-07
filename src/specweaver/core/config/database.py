# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""SQLite database for SpecWeaver multi-project configuration.

The database lives at ~/.specweaver/specweaver.db — outside any project
directory, so agents cannot modify their own guardrails.

Tables:
- projects              — registered projects (name, root_path, timestamps)
- llm_profiles          — global and project-specific LLM configurations
- project_llm_links     — links projects to LLM profiles by role
- validation_overrides  — (Removed in v14)
- active_state          — singleton key-value (currently active project)
- schema_version        — for future DB migrations
"""

from __future__ import annotations

import asyncio
import logging
import re
import weakref
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import event

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncEngine


class CQRSQueueManager:
    """
    Manages an asynchronous queue for CQRS write operations.
    Runs a background Write Worker task that consumes the queue.
    Features a Dead Letter Exchange (DLX) to survive poison payloads.
    """

    def __init__(self, maxsize: int = 1000, dlx_path: str | Path | None = None):
        # We lazy-init the queue to ensure it binds to the correct event loop
        self._maxsize = maxsize
        self._queue: asyncio.Queue[Any] | None = None
        self._worker_task: asyncio.Task[Any] | None = None
        self._dlx_path = Path(dlx_path) if dlx_path else Path(".dead_letter.log")

    async def start(self) -> None:
        """Start the background Write Worker."""
        if self._queue is None:
            self._queue = asyncio.Queue(maxsize=self._maxsize)
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        """Stop the background Write Worker."""
        if self._worker_task:
            self._worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._worker_task
            self._worker_task = None

    async def enqueue(self, callback: Any) -> None:
        """Enqueue a write payload asynchronously."""
        if self._queue is None:
            self._queue = asyncio.Queue(maxsize=self._maxsize)
        await self._queue.put(callback)

    def enqueue_nowait(self, callback: Any) -> None:
        """Enqueue a write payload immediately."""
        if self._queue is None:
            self._queue = asyncio.Queue(maxsize=self._maxsize)
        self._queue.put_nowait(callback)

    async def flush(self) -> None:
        """Wait for the queue to empty."""
        if self._queue is not None:
            await self._queue.join()

    def _dlx_logger(self) -> logging.Logger:
        """A rotating-file logger for writes that failed, created once per manager.

        Set up lazily and defensively: a manager whose DLX path is unwritable must still drain its
        queue, so a handler that cannot be created is reported and then done without.
        """
        from logging.handlers import RotatingFileHandler

        dlx_logger = logging.getLogger(f"{__name__}.dlx.{id(self)}")
        if dlx_logger.handlers:
            return dlx_logger
        dlx_logger.propagate = False  # its own file only, as before
        try:
            handler = RotatingFileHandler(self._dlx_path, maxBytes=10 * 1024 * 1024, backupCount=3)
            handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s: %(message)s"))
            dlx_logger.addHandler(handler)
        except Exception as setup_error:
            logger.critical("Failed to set up the DLX file handler: %s", setup_error)
        return dlx_logger

    def _record_to_dlx(self, error: Exception) -> None:
        """Record a failed write to the dead-letter exchange, never raising."""
        try:
            self._dlx_logger().error("Error: %s", error)
        except Exception as dlx_error:
            logger.critical("DLX write failed: %s", dlx_error)

    async def _worker_loop(self) -> None:
        """Background worker loop that processes writes."""
        if self._queue is None:
            return
        while True:
            callback = await self._queue.get()
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except asyncio.CancelledError:  # expected: the queue is stopped
                break
            except Exception as e:
                self._record_to_dlx(e)

            finally:
                self._queue.task_done()


# One semaphore per event loop, throttling concurrent database access so the OS runs out of file
# descriptors first nowhere. Per loop, not global: a semaphore binds to the first loop that waits on
# it, and the CLI starts a fresh loop for every command.
_db_semaphores: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = (
    weakref.WeakKeyDictionary()
)


def get_db_semaphore(max_connections: int = 500) -> asyncio.Semaphore:
    """The semaphore for the running event loop, created on first use."""
    loop = asyncio.get_running_loop()
    semaphore = _db_semaphores.get(loop)
    if semaphore is None:
        semaphore = asyncio.Semaphore(max_connections)
        _db_semaphores[loop] = semaphore
    return semaphore


def create_async_engine(url: str, **kwargs: Any) -> AsyncEngine:
    """
    Create a new asynchronous SQLAlchemy engine, with foreign keys enforced on every connection.
    Mandates NullPool by default to prevent SQLite lock contention under massive parallelism.
    """
    from sqlalchemy.ext.asyncio import create_async_engine as sa_create_async_engine
    from sqlalchemy.pool import NullPool

    # Ensure we use NullPool by default if not overridden
    if "poolclass" not in kwargs:
        kwargs["poolclass"] = NullPool

    engine = sa_create_async_engine(url, **kwargs)
    register_fk_pragma_listener(engine.sync_engine)
    return engine


# Global CQRS write queue instance (managed per-event-loop for safe testing)
_global_write_queue: CQRSQueueManager | None = None
_global_write_queue_loop: asyncio.AbstractEventLoop | None = None


def get_global_write_queue() -> CQRSQueueManager:
    """Retrieve the global write queue for the current event loop."""
    global _global_write_queue, _global_write_queue_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:  # expected: no event loop runs in this thread
        current_loop = None

    if _global_write_queue is None or _global_write_queue_loop is not current_loop:
        _global_write_queue = CQRSQueueManager()
        _global_write_queue_loop = current_loop
    return _global_write_queue


@asynccontextmanager
async def cqrs_context() -> AsyncGenerator[CQRSQueueManager, None]:
    """
    Context manager that starts the global CQRS write queue,
    yields it, and guarantees that all pending writes are flushed
    and the worker is gracefully stopped upon exit.
    """
    q = get_global_write_queue()
    await q.start()
    try:
        yield q
    finally:
        await q.flush()
        await q.stop()


logger = logging.getLogger(__name__)

_PROJECT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _validate_project_name(name: str) -> None:
    if not name or not _PROJECT_NAME_RE.match(name):
        msg = (
            f"Invalid project name '{name}'. Must match ^[a-z0-9][a-z0-9_-]*$ "
            "(lowercase letters, digits, hyphens, underscores; "
            "must start with letter or digit)."
        )
        raise ValueError(msg)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def register_fk_pragma_listener(engine_or_sync_engine) -> None:  # type: ignore[no-untyped-def]
    """Register a 'connect' event listener that enables PRAGMA foreign_keys=ON.

    For AsyncEngine, pass engine.sync_engine.
    For sync Engine, pass the engine directly.
    This ensures all CASCADE rules are enforced on every new connection.
    """

    @event.listens_for(engine_or_sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
