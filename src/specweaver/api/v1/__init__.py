# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""API v1 router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from specweaver.api.v1 import (
    constitution,
    health,
    implement,
    projects,
    review,
    standards,
    validation,
)

router = APIRouter(prefix="/api/v1")
router.include_router(projects.router, tags=["projects"])
router.include_router(health.router, tags=["health"])
router.include_router(validation.router, tags=["validation"])
router.include_router(review.router, tags=["review"])
router.include_router(implement.router, tags=["implement"])
router.include_router(standards.router, tags=["standards"])
router.include_router(constitution.router, tags=["constitution"])

