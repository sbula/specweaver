# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Where a registered project's scenario store is: a leaf, so any handler can ask."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.handlers.run_context import RunContext

logger = logging.getLogger(__name__)


def scenario_store(context: RunContext) -> Path | None:
    """The scenario store of the run's registered project; None when it is not registered."""
    from specweaver.core.config.paths import scenario_store_for
    from specweaver.workspace.store import project_name_at

    db = getattr(context, "db", None)
    if db is None:
        return None
    try:
        name = project_name_at(db, context.project_path)
    except Exception:
        logger.warning("scenario_store: could not read the project registry", exc_info=True)
        return None
    return scenario_store_for(name) if name else None
