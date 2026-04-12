# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""API v1 router aggregation."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from specweaver.interfaces.api.v1 import (
    constitution,
    health,
    implement,
    pipelines,
    projects,
    review,
    standards,
    validation,
    ws,
)

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1")
router.include_router(projects.router, tags=["projects"])
router.include_router(health.router, tags=["health"])
router.include_router(validation.router, tags=["validation"])
router.include_router(review.router, tags=["review"])
router.include_router(implement.router, tags=["implement"])
router.include_router(standards.router, tags=["standards"])
router.include_router(constitution.router, tags=["constitution"])
router.include_router(pipelines.router, tags=["pipelines"])
router.include_router(ws.router, tags=["websocket"])
