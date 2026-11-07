# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""FastAPI application factory."""

from __future__ import annotations

import logging
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from specweaver.interfaces.api import deps
from specweaver.interfaces.api.auth import TokenGuard
from specweaver.interfaces.api.errors import (
    DATABASE_ERRORS,
    SpecWeaverAPIError,
    database_busy_handler,
    specweaver_error_handler,
)

# Re-exported, not defined: the singleton lives beside the class it hands out, so the route modules
# do not import the application object back. Resolved here too, for callers that reach
# `app.get_event_bridge`.
from specweaver.interfaces.api.event_bridge import get_event_bridge as get_event_bridge
from specweaver.interfaces.api.event_bridge import set_event_bridge as set_event_bridge
from specweaver.interfaces.api.ui import htmx as ui_htmx
from specweaver.interfaces.api.ui import routes as ui_routes
from specweaver.interfaces.api.v1 import health
from specweaver.interfaces.api.v1.router import router

logger = logging.getLogger(__name__)

#: The API's log folder name; project names start with a letter or digit, so none can take it.
_API_LOG = "_api"

if TYPE_CHECKING:
    from specweaver.infrastructure.database import Database


def create_app(
    *,
    token: str,
    db: Database | None = None,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """Create and configure the SpecWeaver FastAPI application.

    Args:
        token: The secret every request must carry (`auth.TokenGuard`); no app is built open.
        db: Optional Database instance. If None, creates a default one.
        cors_origins: Allowed CORS origins. Defaults to localhost.

    Returns:
        Configured FastAPI app instance.
    """
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.paths import config_db_path, state_db_path
    from specweaver.core.flow.engine.store import StateStore
    from specweaver.infrastructure.database import Database as _Database
    from specweaver.infrastructure.database import set_lock_wait
    from specweaver.telemetry_logger import setup_logging

    # The server's own process settings and files, before anything is served: a request waits 5 s
    # for a lock, the log is the API's own file, and a file that cannot be brought up to date
    # stops the start (SchemaError).
    set_lock_wait(5)
    setup_logging(project_name=_API_LOG)
    logger.info("Initializing create_app")
    if db is None:
        db = _Database(config_db_path())
    bootstrap_database(str(db.path))
    StateStore(state_db_path())
    try:
        ver = version("specweaver")
    except Exception:  # expected: not installed as a package, so 'dev'
        ver = "dev"

    app = FastAPI(
        title="SpecWeaver API",
        description="Spec-first development toolkit",
        version=ver,
    )

    # --- CORS Middleware ---
    import os

    all_origins: list[str] = list(cors_origins or [])
    cors_env = os.environ.get("CORS_ORIGINS", "")
    if cors_env:
        all_origins.extend(o.strip() for o in cors_env.split(",") if o.strip())

    app.add_middleware(
        CORSMiddleware,
        allow_origins=all_origins,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Added last, so it runs first: nothing, CORS answers included, is served without the token.
    app.add_middleware(TokenGuard, token=token)

    # --- Error Handlers ---
    app.add_exception_handler(SpecWeaverAPIError, specweaver_error_handler)  # type: ignore[arg-type]
    for error in DATABASE_ERRORS:
        app.add_exception_handler(error, database_busy_handler)

    deps.set_db(db)

    # --- Routers ---
    # Mount health check at root (not under /api/v1)
    app.include_router(health.router)
    # Mount v1 REST router
    app.include_router(router)

    # --- Web Dashboard (UI) ---
    from fastapi.responses import RedirectResponse
    from fastapi.staticfiles import StaticFiles

    # Mount static assets
    ui_dir = Path(__file__).parent / "ui"
    static_dir = ui_dir / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Mount the UI routers
    app.include_router(ui_routes.router)
    app.include_router(ui_htmx.router)

    @app.get("/", include_in_schema=False)
    def redirect_to_dashboard() -> RedirectResponse:
        """Redirect root to the UI dashboard."""
        return RedirectResponse(url="/dashboard")

    return app
