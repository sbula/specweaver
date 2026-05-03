# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Project management API endpoints."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends

from specweaver.core.config.database import Database  # noqa: TC001 -- runtime for FastAPI DI
from specweaver.interfaces.api.deps import get_db
from specweaver.interfaces.api.errors import SpecWeaverAPIError
from specweaver.interfaces.api.v1.schemas import ProjectCreate, ProjectResponse, ProjectUpdate

logger = logging.getLogger(__name__)


router = APIRouter()

_db_dep = Depends(get_db)


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(db: Database = _db_dep) -> list[ProjectResponse]:
    """List all registered projects."""
    from specweaver.workspace.store import WorkspaceRepository

    async with db.async_session_scope() as session:
        repo = WorkspaceRepository(session)
        all_projects = await repo.list_projects()
        active = await repo.get_active_project()

    return [
        ProjectResponse(
            name=str(p["name"]),
            path=str(p["root_path"]),
            active=(str(p["name"]) == active),
        )
        for p in all_projects
    ]


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    db: Database = _db_dep,
) -> ProjectResponse:
    """Register a new project with optional scaffolding."""
    from specweaver.workspace.store import WorkspaceRepository

    project_path = Path(body.path)
    if not project_path.exists():
        raise SpecWeaverAPIError(
            detail=f"Path does not exist: {body.path}",
            error_code="PATH_NOT_FOUND",
            status_code=400,
        )

    try:
        async with db.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            await repo.register_project(body.name, str(project_path))
            await repo.set_active_project(body.name)
    except ValueError as exc:
        raise SpecWeaverAPIError(
            detail=str(exc),
            error_code="PROJECT_ALREADY_EXISTS",
            status_code=409,
        ) from exc

    if body.scaffold:
        from specweaver.workspace.project.scaffold import scaffold_project

        scaffold_project(project_path)

    return ProjectResponse(
        name=body.name,
        path=str(project_path),
        active=True,
    )


@router.delete("/projects/{name}", status_code=200)
async def delete_project(
    name: str,
    db: Database = _db_dep,
) -> dict[str, str]:
    """Unregister a project."""
    from specweaver.workspace.store import WorkspaceRepository

    async with db.async_session_scope() as session:
        repo = WorkspaceRepository(session)
        proj = await repo.get_project(name)
        if not proj:
            raise SpecWeaverAPIError(
                detail=f"Project '{name}' not found.",
                error_code="PROJECT_NOT_FOUND",
                status_code=404,
            )
        await repo.remove_project(name)
    return {"detail": f"Project '{name}' removed."}


@router.put("/projects/{name}", response_model=ProjectResponse)
async def update_project(
    name: str,
    body: ProjectUpdate,
    db: Database = _db_dep,
) -> ProjectResponse:
    """Update a project setting (currently: path only)."""
    from specweaver.workspace.store import WorkspaceRepository

    try:
        async with db.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            proj = await repo.get_project(name)
            if not proj:
                raise SpecWeaverAPIError(
                    detail=f"Project '{name}' not found.",
                    error_code="PROJECT_NOT_FOUND",
                    status_code=404,
                )
            await repo.update_project_path(name, body.path)
            active = await repo.get_active_project()
    except ValueError as exc:
        raise SpecWeaverAPIError(
            detail=str(exc),
            error_code="INVALID_PATH",
            status_code=400,
        ) from exc
    return ProjectResponse(name=name, path=body.path, active=(name == active))


@router.post("/projects/{name}/use")
async def use_project(
    name: str,
    db: Database = _db_dep,
) -> dict[str, str]:
    """Set a project as the active project."""
    from specweaver.workspace.store import WorkspaceRepository

    async with db.async_session_scope() as session:
        repo = WorkspaceRepository(session)
        proj = await repo.get_project(name)
        if not proj:
            raise SpecWeaverAPIError(
                detail=f"Project '{name}' not found.",
                error_code="PROJECT_NOT_FOUND",
                status_code=404,
            )
        await repo.set_active_project(name)
    return {"active": name}
