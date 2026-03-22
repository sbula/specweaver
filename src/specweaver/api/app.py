# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""FastAPI application factory."""

from __future__ import annotations

from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from specweaver.api import deps
from specweaver.api.errors import SpecWeaverAPIError, specweaver_error_handler
from specweaver.api.v1 import health, router

if TYPE_CHECKING:
    from specweaver.api.event_bridge import EventBridge
    from specweaver.config.database import Database

# Module-level singleton for the event bridge
_event_bridge: EventBridge | None = None


def get_event_bridge() -> EventBridge:
    """Get the shared EventBridge instance (lazy init)."""
    global _event_bridge
    if _event_bridge is None:
        from specweaver.api.event_bridge import EventBridge

        _event_bridge = EventBridge()
    return _event_bridge


def set_event_bridge(bridge: EventBridge) -> None:
    """Override the EventBridge (for testing)."""
    global _event_bridge
    _event_bridge = bridge


def create_app(
    *,
    db: Database | None = None,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """Create and configure the SpecWeaver FastAPI application.

    Args:
        db: Optional Database instance. If None, creates a default one.
        cors_origins: Allowed CORS origins. Defaults to localhost.

    Returns:
        Configured FastAPI app instance.
    """
    try:
        ver = version("specweaver")
    except Exception:
        ver = "dev"

    app = FastAPI(
        title="SpecWeaver API",
        description="Spec-first development toolkit",
        version=ver,
    )

    # --- CORS Middleware ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or [],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Error Handlers ---
    app.add_exception_handler(SpecWeaverAPIError, specweaver_error_handler)  # type: ignore[arg-type]

    # --- Database ---
    if db is None:
        from specweaver.config.database import Database as _Database

        db = _Database(Path.home() / ".specweaver" / "specweaver.db")
    deps.set_db(db)

    # --- Routers ---
    # Mount health check at root (not under /api/v1)
    app.include_router(health.router)
    # Mount v1 router
    app.include_router(router)

    return app

