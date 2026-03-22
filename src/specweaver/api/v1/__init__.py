# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""API v1 router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from specweaver.api.v1 import health, projects

router = APIRouter(prefix="/api/v1")
router.include_router(projects.router, tags=["projects"])
router.include_router(health.router, tags=["health"])
