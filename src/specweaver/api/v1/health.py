# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Health check endpoint."""

from __future__ import annotations

import logging
from importlib.metadata import version

from fastapi import APIRouter

from specweaver.api.v1.schemas import HealthResponse

logger = logging.getLogger(__name__)


router = APIRouter()


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    """Return service status and version."""
    try:
        ver = version("specweaver")
    except Exception:
        ver = "dev"
    return HealthResponse(status="ok", version=ver)
