# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Standards API endpoints — scan, accept, show, clear."""

from __future__ import annotations

import logging
from pathlib import Path  # noqa: TC003 -- runtime for rglob

from fastapi import APIRouter, Depends, Query

from specweaver.core.config.database import Database  # noqa: TC001 -- runtime for FastAPI DI
from specweaver.interfaces.api.deps import get_db
from specweaver.interfaces.api.v1.paths import resolve_project_root
from specweaver.interfaces.api.v1.schemas import (  # noqa: TC001 -- runtime for FastAPI
    AcceptRequest,
    ScanRequest,
)

logger = logging.getLogger(__name__)


router = APIRouter()

_db_dep = Depends(get_db)


@router.get("/standards")
async def get_standards(
    project: str = Query(..., description="Project name."),
    db: Database = _db_dep,
) -> list[dict[str, object]]:
    """List saved standards for a project."""
    from specweaver.workspace.store import WorkspaceRepository

    await resolve_project_root(project, db)
    async with db.async_session_scope() as session:
        repo = WorkspaceRepository(session)
        standards = await repo.get_standards(project)
    return [dict(s) for s in standards]


@router.delete("/standards")
async def clear_standards(
    project: str = Query(..., description="Project name."),
    db: Database = _db_dep,
) -> dict[str, str]:
    """Clear saved standards for a project."""
    from specweaver.workspace.store import WorkspaceRepository

    await resolve_project_root(project, db)
    async with db.async_session_scope() as session:
        repo = WorkspaceRepository(session)
        await repo.clear_standards(project)
    return {"detail": f"Standards cleared for project '{project}'."}


@router.post("/standards/scan")
async def scan_standards(
    body: ScanRequest,
    db: Database = _db_dep,
) -> list[dict[str, object]]:
    """Scan project directory for coding standards (returns without saving)."""
    from specweaver.assurance.standards.scanner import StandardsScanner

    project_root = await resolve_project_root(body.project, db)

    # Discover Python/JS/TS source files
    source_files: list[Path] = []
    for ext in ("*.py", "*.js", "*.ts", "*.jsx", "*.tsx"):
        source_files.extend(project_root.rglob(ext))

    # Filter out hidden dirs, node_modules, etc.
    source_files = [
        f
        for f in source_files
        if not any(p.startswith(".") or p == "node_modules" for p in f.parts)
    ]

    scanner = StandardsScanner()
    results = scanner.scan(source_files)

    from dataclasses import asdict

    return [asdict(r) for r in results]


@router.post("/standards/accept")
async def accept_standards(
    body: AcceptRequest,
    db: Database = _db_dep,
) -> dict[str, str]:
    """Save scanned standards to the project database."""
    from specweaver.workspace.store import WorkspaceRepository

    await resolve_project_root(body.project, db)

    async with db.async_session_scope() as session:
        repo = WorkspaceRepository(session)
        for standard in body.standards:
            dominant_raw = standard.get("dominant", {})
            dominant: dict[str, object] = dominant_raw if isinstance(dominant_raw, dict) else {}
            conf_raw = standard.get("confidence", 0.0)
            await repo.save_standard(
                body.project,
                scope=str(standard.get("scope", ".")),
                language=str(standard.get("language", "")),
                category=str(standard.get("category", "")),
                data=dominant,
                confidence=float(conf_raw) if isinstance(conf_raw, (int, float, str)) else 0.0,
            )

    return {"detail": f"Saved {len(body.standards)} standards for project '{body.project}'."}
