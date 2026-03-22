# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Request and response schemas for the SpecWeaver API."""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Project schemas
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    """Request body for POST /projects."""

    name: str = Field(..., description="Project name (lowercase, hyphens, underscores only).")
    path: str = Field(..., description="Absolute path to the project directory.")
    scaffold: bool = Field(True, description="Create .specweaver/ scaffold files.")


class ProjectUpdate(BaseModel):
    """Request body for PUT /projects/{name}."""

    path: str = Field(..., description="New absolute path for the project.")


class ProjectResponse(BaseModel):
    """Response for a single project."""

    name: str
    path: str
    active: bool = False


# ---------------------------------------------------------------------------
# Health schemas
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Response for GET /healthz."""

    status: str = "ok"
    version: str
