# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Shared path security helpers for API endpoints."""

from __future__ import annotations

import logging
from pathlib import Path, PurePosixPath

from specweaver.api.errors import SpecWeaverAPIError
from specweaver.config.database import Database  # noqa: TC001 -- runtime

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


def resolve_project_root(project_name: str, db: Database) -> Path:
    """Resolve a project name to its root directory.

    Raises:
        SpecWeaverAPIError: If project not found.
    """
    proj = db.get_project(project_name)
    if not proj:
        raise SpecWeaverAPIError(
            detail=f"Project '{project_name}' not found.",
            error_code="PROJECT_NOT_FOUND",
            status_code=404,
        )
    return Path(str(proj["root_path"]))


def resolve_file_in_project(
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
    project_root = resolve_project_root(project_name, db)
    abs_path = project_root / file_path
    if not abs_path.exists():
        raise SpecWeaverAPIError(
            detail=f"File not found: '{file_path}' in project '{project_name}'",
            error_code="FILE_NOT_FOUND",
            status_code=404,
        )
    return project_root, abs_path
