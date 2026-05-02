# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Shared path security helpers for API endpoints."""

from __future__ import annotations

import logging
from pathlib import Path, PurePosixPath

from specweaver.core.config.database import Database  # noqa: TC001 -- runtime
from specweaver.interfaces.api.errors import SpecWeaverAPIError

logger = logging.getLogger(__name__)


def validate_relative_path(file_path: str) -> None:
    """Reject absolute paths and directory traversals.

    Raises:
        SpecWeaverAPIError: If path is absolute or contains ``..``.
    """
    p = PurePosixPath(file_path)
    if p.is_absolute() or ".." in p.parts:
        raise SpecWeaverAPIError(
            detail=f"Path traversal not allowed: '{file_path}'",
            error_code="PATH_TRAVERSAL",
            status_code=400,
        )


async def resolve_project_root(project_name: str, db: Database) -> Path:
    """Resolve a project name to its root directory.

    Raises:
        SpecWeaverAPIError: If project not found.
    """
    from specweaver.workspace.store import WorkspaceRepository

    async with db.async_session_scope() as session:
        proj = await WorkspaceRepository(session).get_project(project_name)
    if not proj:
        raise SpecWeaverAPIError(
            detail=f"Project '{project_name}' not found.",
            error_code="PROJECT_NOT_FOUND",
            status_code=404,
        )
    return Path(str(proj["root_path"]))


async def resolve_file_in_project(
    file_path: str,
    project_name: str,
    db: Database,
) -> tuple[Path, Path]:
    """Validate and resolve a relative file path within a project.

    Returns:
        Tuple of (project_root, absolute_file_path).

    Raises:
        SpecWeaverAPIError: If path invalid or file not found.
    """
    validate_relative_path(file_path)
    project_root = await resolve_project_root(project_name, db)
    abs_path = project_root / file_path
    if not abs_path.exists():
        raise SpecWeaverAPIError(
            detail=f"File not found: '{file_path}' in project '{project_name}'",
            error_code="FILE_NOT_FOUND",
            status_code=404,
        )
    return project_root, abs_path
