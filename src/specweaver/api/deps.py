# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""FastAPI dependency injection for DB and project context."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from specweaver.config.database import Database

# Module-level DB reference, set by create_app() at startup.
_db: Database | None = None


def set_db(db: Database) -> None:
    """Set the module-level DB instance (called during app lifespan)."""
    global _db
    _db = db


def get_db() -> Database:
    """FastAPI dependency: return the shared Database instance.

    Raises:
        RuntimeError: If the DB has not been set (app not started).
    """
    if _db is None:
        msg = "Database not initialized. Is the server running?"
        raise RuntimeError(msg)
    return _db
