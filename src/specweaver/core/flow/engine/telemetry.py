# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Flushing collected LLM telemetry at the end of a run.

Split out of `runner_utils.py` by `TECH-015`.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.core.flow.handlers.base import RunContext

logger = logging.getLogger(__name__)


def flush_telemetry(context: RunContext, logger: logging.Logger) -> None:
    """Flush telemetry if context.model.llm is a TelemetryCollector."""
    from specweaver.infrastructure.llm.collector import TelemetryCollector

    llm = context.model.llm
    if not isinstance(llm, TelemetryCollector):
        return

    db = getattr(context, "db", None)
    if db is None:
        logger.warning("Cannot flush telemetry: no db on RunContext")
        return

    try:
        llm.flush(db)
    except Exception:
        logger.warning("Failed to flush telemetry", exc_info=True)
