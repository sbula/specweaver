# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A value of the run's registered project, read from the workspace store."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


def registered(context: Any, read: Callable[[Any, Path], _T | None], what: str) -> _T | None:
    """`read(db, project folder)` for the run; None with no database, no folder, or a failed read.

    A failed read is logged, not raised: the callers fall back to a default that keeps the run going.
    """
    db = getattr(context, "db", None)
    root = getattr(context, "project_path", None)
    if db is None or root is None:
        return None
    try:
        return read(db, root)
    except Exception:  # expected: the registry is unreadable; the caller falls back
        logger.warning("Could not read the project's %s", what, exc_info=True)
        return None
