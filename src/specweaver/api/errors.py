# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""SpecWeaver API error types and exception handlers."""

from __future__ import annotations

import logging

from fastapi import Request  # noqa: TC002 -- used at runtime by FastAPI
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class SpecWeaverAPIError(Exception):
    """Base API error with structured error_code field."""

    def __init__(
        self,
        detail: str,
        error_code: str,
        status_code: int = 400,
    ) -> None:
        self.detail = detail
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(detail)


async def specweaver_error_handler(
    request: Request,
    exc: SpecWeaverAPIError,
) -> JSONResponse:
    """Handle SpecWeaverAPIError → structured JSON response."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": exc.error_code},
    )
