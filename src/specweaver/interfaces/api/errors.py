# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""SpecWeaver API error types and exception handlers."""

from __future__ import annotations

import logging
import sqlite3

import sqlalchemy.exc
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


#: The errors a locked file raises: through SQLAlchemy, and through `sqlite3` directly.
DATABASE_ERRORS = (sqlalchemy.exc.OperationalError, sqlite3.OperationalError)


def _is_locked(cause: BaseException) -> bool:
    """SQLite's own code when it gave one (`SQLITE_BUSY`, `SQLITE_LOCKED`), else its message."""
    code = getattr(cause, "sqlite_errorcode", None)
    if code is not None:
        return code & 0xFF in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
    message = str(cause).lower()
    return "locked" in message or "busy" in message


async def database_busy_handler(request: Request, exc: Exception) -> JSONResponse:
    """A file still locked after the lock wait → `503`, retry in a second; anything else stays `500`.

    The driver's error decides, never the SQL; the body carries neither.
    """
    cause = getattr(exc, "orig", None) or exc
    if not _is_locked(cause):
        raise exc
    logger.warning("A request found the database locked: %s", cause)
    return JSONResponse(
        status_code=503,
        content={"detail": "The database is busy. Retry.", "error_code": "DATABASE_BUSY"},
        headers={"Retry-After": "1"},
    )
