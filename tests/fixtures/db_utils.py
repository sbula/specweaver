"""Database utilities for tests to replace monolithic Database methods."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import anyio
import nest_asyncio
from sqlalchemy import delete, select

from specweaver.infrastructure.llm.store import LlmProfile, LlmRepository, ProjectLlmLink
from specweaver.workspace.store import WorkspaceRepository

if TYPE_CHECKING:
    from specweaver.core.config.database import Database


def _sync_or_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        nest_asyncio.apply(loop)
        return loop.run_until_complete(coro)
    return anyio.run(lambda: coro)


def register_test_project(db: Database, name: str, root_path: str) -> None:
    """Register a new project synchronously for tests."""

    async def _register() -> None:
        async with db.async_session_scope() as session:
            ws_repo = WorkspaceRepository(session)
            await ws_repo.register_project(name, root_path)

            llm_repo = LlmRepository(session)
            stmt = select(LlmProfile).where(LlmProfile.is_global == 1)
            globals_ = (await session.execute(stmt)).scalars().all()
            for profile in globals_:
                await llm_repo.link_project_profile(name, profile.name, profile.id)

    _sync_or_async(_register())


def get_test_project(db: Database, name: str) -> dict[str, object] | None:
    """Get project info by name, or None if not found."""

    async def _get() -> dict[str, object] | None:
        async with db.async_session_scope() as session:
            return await WorkspaceRepository(session).get_project(name)

    return _sync_or_async(_get())


def list_test_projects(db: Database) -> list[dict[str, object]]:
    """List all registered projects."""

    async def _list() -> list[dict[str, object]]:
        async with db.async_session_scope() as session:
            return await WorkspaceRepository(session).list_projects()

    return _sync_or_async(_list())


def remove_test_project(db: Database, name: str) -> None:
    """Unregister a project and cascade-delete its links."""

    async def _remove() -> None:
        async with db.async_session_scope() as session:
            await WorkspaceRepository(session).remove_project(name)
            await session.execute(delete(ProjectLlmLink).where(ProjectLlmLink.project_name == name))

    _sync_or_async(_remove())


def update_test_project_path(db: Database, name: str, new_path: str) -> None:
    """Change a project's root_path."""

    async def _update() -> None:
        async with db.async_session_scope() as session:
            await WorkspaceRepository(session).update_project_path(name, new_path)

    _sync_or_async(_update())


def get_test_active_project(db: Database) -> str | None:
    """Get the currently active project name, or None."""

    async def _get() -> str | None:
        async with db.async_session_scope() as session:
            return await WorkspaceRepository(session).get_active_project()

    return _sync_or_async(_get())


def set_test_active_project(db: Database, name: str) -> None:
    """Set the active project."""

    async def _set() -> None:
        async with db.async_session_scope() as session:
            await WorkspaceRepository(session).set_active_project(name)

    _sync_or_async(_set())
