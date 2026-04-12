# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Constitution API endpoints — show, init."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query

from specweaver.interfaces.api.deps import get_db
from specweaver.interfaces.api.v1.paths import resolve_project_root
from specweaver.interfaces.api.v1.schemas import ConstitutionInitRequest, ConstitutionResponse
from specweaver.core.config.database import Database  # noqa: TC001 -- runtime for FastAPI DI

logger = logging.getLogger(__name__)


router = APIRouter()

_db_dep = Depends(get_db)


@router.get("/constitution", response_model=ConstitutionResponse)
def get_constitution(
    project: str = Query(..., description="Project name."),
    db: Database = _db_dep,
) -> ConstitutionResponse:
    """Read the constitution file for a project."""
    from specweaver.interfaces.api.errors import SpecWeaverAPIError

    project_root = resolve_project_root(project, db)
    constitution_path = project_root / "CONSTITUTION.md"

    if not constitution_path.exists():
        raise SpecWeaverAPIError(
            detail=f"No constitution found for project '{project}'. Use POST /constitution/init.",
            error_code="CONSTITUTION_NOT_FOUND",
            status_code=404,
        )

    content = constitution_path.read_text(encoding="utf-8")
    return ConstitutionResponse(content=content, path=str(constitution_path))


@router.post("/constitution/init")
def init_constitution(
    body: ConstitutionInitRequest,
    db: Database = _db_dep,
) -> dict[str, str]:
    """Initialize a constitution file for a project."""
    from specweaver.workspace.project.scaffold import scaffold_project

    project_root = resolve_project_root(body.project, db)
    scaffold_project(project_root)

    constitution_path = project_root / "CONSTITUTION.md"
    return {
        "detail": f"Constitution initialized for project '{body.project}'.",
        "path": str(constitution_path),
    }
