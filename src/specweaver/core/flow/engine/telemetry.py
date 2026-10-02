# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Flushing collected LLM telemetry at the end of a run."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.core.flow.handlers.run_context import RunContext

logger = logging.getLogger(__name__)


def flush_telemetry(context: RunContext, logger: logging.Logger) -> None:
    """Persist the usage records of every collector the run's calls went through.

    All of them, not one: every role's adapter is a collector, and a run's steps use several roles.
    """
    router = context.model.llm_router
    if router is None:
        return

    db = getattr(context, "db", None)
    if db is None:
        logger.warning("Cannot flush telemetry: no db on RunContext")
        return

    for collector in router.collectors():
        try:
            collector.flush(db)
        except Exception:
            logger.warning("Failed to flush telemetry", exc_info=True)
