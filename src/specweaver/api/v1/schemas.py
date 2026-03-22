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


# ---------------------------------------------------------------------------
# Validation schemas
# ---------------------------------------------------------------------------


class CheckRequest(BaseModel):
    """Request body for POST /check."""

    file: str = Field(..., description="Relative path to the file to check.")
    level: str = Field("component", description="Validation level: feature, component, or code.")
    project: str = Field(..., description="Project name.")
    pipeline: str | None = Field(None, description="Optional pipeline name override.")
    strict: bool = Field(False, description="Treat warnings as failures.")


class FindingResponse(BaseModel):
    """A single finding from a validation rule."""

    message: str
    line: int | None = None
    severity: str = "error"
    suggestion: str | None = None


class RuleResultResponse(BaseModel):
    """Result of a single rule execution."""

    rule_id: str
    rule_name: str
    status: str
    findings: list[FindingResponse] = Field(default_factory=list)
    message: str = ""


class CheckResponse(BaseModel):
    """Wrapped response envelope for POST /check."""

    results: list[RuleResultResponse]
    overall: str
    total: int
    passed: int
    failed: int
    warned: int


class RuleInfo(BaseModel):
    """Info about a single validation rule."""

    id: str
    name: str
    level: str


# ---------------------------------------------------------------------------
# Review schemas
# ---------------------------------------------------------------------------


class ReviewRequest(BaseModel):
    """Request body for POST /review."""

    file: str = Field(..., description="Relative path to the spec file.")
    project: str = Field(..., description="Project name.")


# ---------------------------------------------------------------------------
# Implement schemas
# ---------------------------------------------------------------------------


class ImplementRequest(BaseModel):
    """Request body for POST /implement."""

    file: str = Field(..., description="Relative path to the spec file.")
    project: str = Field(..., description="Project name.")
    selector: str = Field("direct", description="Topology selector: direct, nhop, constraint.")


class ImplementResponse(BaseModel):
    """Response for POST /implement."""

    code_path: str
    test_path: str


# ---------------------------------------------------------------------------
# Standards schemas
# ---------------------------------------------------------------------------


class ScanRequest(BaseModel):
    """Request body for POST /standards/scan."""

    project: str = Field(..., description="Project name.")


class AcceptRequest(BaseModel):
    """Request body for POST /standards/accept."""

    project: str = Field(..., description="Project name.")
    standards: list[dict] = Field(..., description="Scanned standards to save.")


# ---------------------------------------------------------------------------
# Constitution schemas
# ---------------------------------------------------------------------------


class ConstitutionResponse(BaseModel):
    """Response for GET /constitution."""

    content: str
    path: str


class ConstitutionInitRequest(BaseModel):
    """Request body for POST /constitution/init."""

    project: str = Field(..., description="Project name.")


# ---------------------------------------------------------------------------
# Phase 3 — Pipeline Execution
# ---------------------------------------------------------------------------


class PipelineRunRequest(BaseModel):
    """Request body for POST /pipelines/{name}/run."""

    project: str = Field(..., description="Project name.")
    spec: str = Field(..., description="Spec file (relative to project root).")
    selector: str = Field(default="direct", description="Topology selector.")


class PipelineRunResponse(BaseModel):
    """Response for POST /pipelines/{name}/run (fire-and-forget)."""

    run_id: str
    detail: str


class GateDecisionRequest(BaseModel):
    """Request body for POST /runs/{run_id}/gate."""

    action: str = Field(
        ...,
        description="Gate decision: 'approve' or 'reject'.",
    )


