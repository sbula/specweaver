# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Synchronous lookups of a registered project, for callers outside an async session."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from specweaver.commons.enums.dal import DALLevel

logger = logging.getLogger(__name__)


def _project_row_at(db: Any, root: Path) -> Any:
    """The row of the project registered at `root`, the path compared resolved; None when none is."""
    target = root.resolve()
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT name, root_path, default_dal, domain_profile FROM workspace_projects"
        ).fetchall()
    return next((row for row in rows if Path(row["root_path"]).resolve() == target), None)


def default_dal_at(db: Any, root: Path) -> DALLevel | None:
    """The default DAL of the project registered at `root`; None when no project is."""
    row = _project_row_at(db, root)
    if row is None:
        return None
    try:
        return DALLevel(row["default_dal"])
    except ValueError:
        logger.warning(
            "The project's stored DAL %r is not a DAL, so it is ignored", row["default_dal"]
        )
        return None


def project_name_at(db: Any, root: Path) -> str | None:
    """The name of the project registered at `root`; None when no project is."""
    row = _project_row_at(db, root)
    return None if row is None else str(row["name"])


def domain_profile_at(db: Any, root: Path) -> str | None:
    """The domain profile of the project registered at `root`; None when none is set or registered."""
    row = _project_row_at(db, root)
    return None if row is None else row["domain_profile"]


def active_project(db: Any) -> str | None:
    """The active project's name; None when no project is active."""
    with db.connect() as conn:
        row = conn.execute(
            "SELECT value FROM workspace_active_state WHERE key = 'active_project'"
        ).fetchone()
    return str(row["value"]) if row else None


def project_root_of(db: Any, name: str) -> Path | None:
    """The registered root of project `name`; None when no project has that name."""
    with db.connect() as conn:
        row = conn.execute(
            "SELECT root_path FROM workspace_projects WHERE name = ?", (name,)
        ).fetchone()
    return Path(row["root_path"]) if row else None
