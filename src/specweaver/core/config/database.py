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
import sqlite3
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.types import String, TypeDecorator

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator



class StrictISODateTime(TypeDecorator[datetime]):
    """
    Forces SQLAlchemy to serialize/deserialize datetime objects exactly
    matching the legacy SpecWeaver format: `YYYY-MM-DDTHH:MM:SS.ffffff+00:00`.
    This prevents Zero Regression crashes when reading legacy SQLite files.
    """
    impl = String
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, datetime):
            raise TypeError("Value must be a datetime object")
        if value.tzinfo is None:
            raise ValueError("StrictISODateTime must be timezone-aware")
        return value.isoformat()

    def process_result_value(self, value: str | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        # datetime.fromisoformat natively supports strict ISO strings with timezones
        return datetime.fromisoformat(value)


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
            except asyncio.CancelledError:
                # If cancelled while processing, exit cleanly
                break
            except Exception as e:
                # Dead Letter Exchange: Catch everything else
                import logging
                from logging.handlers import RotatingFileHandler
                
                dlx_logger = logging.getLogger(f"dlx_worker_{id(self)}")
                if not dlx_logger.handlers:
                    try:
                        handler = RotatingFileHandler(self._dlx_path, maxBytes=10*1024*1024, backupCount=3)
                        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s: %(message)s"))
                        dlx_logger.addHandler(handler)
                    except Exception as dlx_setup_e:
                        logging.critical(f"Failed to setup DLX RotatingFileHandler: {dlx_setup_e}")
                
                try:
                    dlx_logger.error(f"Error: {e}")
                except Exception as dlx_e:
                    logging.critical(f"DLX write failed: {dlx_e}")
            finally:
                self._queue.task_done()


# Global semaphore to throttle concurrent database reads/writes, preventing OS file descriptor exhaustion.
_db_semaphore: asyncio.Semaphore | None = None

def get_db_semaphore(max_connections: int = 500) -> asyncio.Semaphore:
    """Get or create the asyncio Semaphore for the current event loop."""
    global _db_semaphore
    if _db_semaphore is None:
        _db_semaphore = asyncio.Semaphore(max_connections)
    return _db_semaphore


def create_async_engine(url: str, **kwargs: Any) -> AsyncEngine:
    """
    Create a new asynchronous SQLAlchemy engine.
    Mandates NullPool by default to prevent SQLite lock contention under massive parallelism.
    """
    from sqlalchemy.ext.asyncio import create_async_engine as sa_create_async_engine
    from sqlalchemy.pool import NullPool

    # Ensure we use NullPool by default if not overridden
    if "poolclass" not in kwargs:
        kwargs["poolclass"] = NullPool

    return sa_create_async_engine(url, **kwargs)


@asynccontextmanager
async def session_scope(engine: AsyncEngine, max_connections: int = 500) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a transactional scope around a series of operations.
    Enforces a strict concurrency limit using asyncio.Semaphore.
    """
    semaphore = get_db_semaphore(max_connections)

    async with semaphore, AsyncSession(engine, expire_on_commit=False) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Global CQRS write queue instance (managed per-event-loop for safe testing)
_global_write_queue: CQRSQueueManager | None = None
_global_write_queue_loop: asyncio.AbstractEventLoop | None = None

def get_global_write_queue() -> CQRSQueueManager:
    """Retrieve the global write queue for the current event loop."""
    global _global_write_queue, _global_write_queue_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
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


class Database:
    """Multi-project configuration database.

    This class owns the connection and schema lifecycle, managed via Alembic
    and SQLAlchemy Repositories.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug("Database initialized at %s", self._db_path)
        self._ensure_schema()

    def connect(self) -> sqlite3.Connection:
        """Return a new connection with WAL + foreign keys enabled."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @asynccontextmanager
    async def async_session_scope(self) -> AsyncGenerator[AsyncSession, None]:
        """Provide an AsyncSession scoped to this database for the new Domain Stores."""
        engine = create_async_engine(f"sqlite+aiosqlite:///{self._db_path}")
        async with session_scope(engine) as session:
            yield session

    # ------------------------------------------------------------------
    # Schema management
    # ------------------------------------------------------------------

    def _ensure_schema(self) -> None:
        """Create tables and apply migrations via Alembic. Idempotent."""
        import alembic.config
        import alembic.command
        import anyio
        from sqlalchemy import select
        from specweaver.infrastructure.llm.store import LlmProfile
        
        try:
            alembic_cfg = alembic.config.Config("alembic.ini")
            alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{self._db_path}")
            alembic.command.upgrade(alembic_cfg, "head")
        except Exception as exc:
            logger.warning("Alembic schema migration failed or skipped: %s", exc)
            # Fallback for tests or environments without alembic.ini
            import anyio
            from sqlalchemy.ext.asyncio import create_async_engine
            from specweaver.infrastructure.llm.store import Base as LlmBase
            from specweaver.workspace.store import Base as WorkspaceBase
            
            async def _create_all() -> None:
                engine = create_async_engine(f"sqlite+aiosqlite:///{self._db_path}")
                async with engine.begin() as conn:
                    await conn.run_sync(LlmBase.metadata.create_all)
                    await conn.run_sync(WorkspaceBase.metadata.create_all)
            anyio.run(_create_all)

        # Seed default LLM profiles if empty
        async def _seed_profiles() -> None:
            from specweaver.infrastructure.llm.store import LlmProfile
            async with self.async_session_scope() as session:
                result = await session.execute(select(LlmProfile).limit(1))
                if result.first() is None:
                    defaults = [
                        LlmProfile(name="system-default", is_global=1, provider="gemini", model="gemini-2.5-pro", temperature=0.7, max_output_tokens=8192, response_format="text"),
                        LlmProfile(name="implement", is_global=1, provider="gemini", model="gemini-2.5-flash", temperature=0.2, max_output_tokens=8192, response_format="text"),
                        LlmProfile(name="review", is_global=1, provider="gemini", model="gemini-2.5-flash", temperature=0.0, max_output_tokens=8192, response_format="text"),
                    ]
                    session.add_all(defaults)

        anyio.run(_seed_profiles)

    # ------------------------------------------------------------------
    # Project CRUD
    # ------------------------------------------------------------------

    def register_project(self, name: str, root_path: str) -> None:
        """Register a new project using WorkspaceRepository."""
        import anyio
        from sqlalchemy import select

        from specweaver.infrastructure.llm.store import LlmProfile, LlmRepository
        from specweaver.workspace.store import WorkspaceRepository

        async def _register() -> None:
            async with self.async_session_scope() as session:
                ws_repo = WorkspaceRepository(session)
                await ws_repo.register_project(name, root_path)

                llm_repo = LlmRepository(session)
                stmt = select(LlmProfile).where(LlmProfile.is_global == 1)
                globals_ = (await session.execute(stmt)).scalars().all()
                for profile in globals_:
                    await llm_repo.link_project_profile(name, profile.name, profile.id)

        anyio.run(_register)

    def get_project(self, name: str) -> dict[str, object] | None:
        """Get project info by name, or None if not found."""
        import anyio

        from specweaver.workspace.store import WorkspaceRepository

        async def _get() -> dict[str, object] | None:
            async with self.async_session_scope() as session:
                return await WorkspaceRepository(session).get_project(name)

        return anyio.run(_get)

    def list_projects(self) -> list[dict[str, object]]:
        """List all registered projects, ordered by last_used_at desc."""
        import anyio

        from specweaver.workspace.store import WorkspaceRepository

        async def _list() -> list[dict[str, object]]:
            async with self.async_session_scope() as session:
                return await WorkspaceRepository(session).list_projects()

        return anyio.run(_list)

    def remove_project(self, name: str) -> None:
        """Unregister a project and cascade-delete its links."""
        import anyio
        from sqlalchemy import delete

        from specweaver.infrastructure.llm.store import ProjectLlmLink
        from specweaver.workspace.store import WorkspaceRepository

        async def _remove() -> None:
            async with self.async_session_scope() as session:
                await WorkspaceRepository(session).remove_project(name)
                await session.execute(delete(ProjectLlmLink).where(ProjectLlmLink.project_name == name))

        anyio.run(_remove)

    def update_project_path(self, name: str, new_path: str) -> None:
        """Change a project's root_path."""
        import anyio

        from specweaver.workspace.store import WorkspaceRepository

        async def _update() -> None:
            async with self.async_session_scope() as session:
                await WorkspaceRepository(session).update_project_path(name, new_path)

        anyio.run(_update)

    # ------------------------------------------------------------------
    # Active project
    # ------------------------------------------------------------------

    def get_active_project(self) -> str | None:
        """Get the currently active project name, or None."""
        import anyio

        from specweaver.workspace.store import WorkspaceRepository

        async def _get() -> str | None:
            async with self.async_session_scope() as session:
                return await WorkspaceRepository(session).get_active_project()

        return anyio.run(_get)

    def set_active_project(self, name: str) -> None:
        """Set the active project. Updates last_used_at."""
        import anyio

        from specweaver.workspace.store import WorkspaceRepository

        async def _set() -> None:
            async with self.async_session_scope() as session:
                await WorkspaceRepository(session).set_active_project(name)

        anyio.run(_set)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
