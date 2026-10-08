# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Flushing collected LLM telemetry at the end of a run."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.core.flow.engine.state import StepStatus
from specweaver.infrastructure.llm.store import record_step_outcomes

if TYPE_CHECKING:
    from specweaver.core.flow.engine.state import PipelineRun
    from specweaver.core.flow.handlers.run_context import RunContext

logger = logging.getLogger(__name__)


def flush_telemetry(
    context: RunContext, logger: logging.Logger, run: PipelineRun | None = None
) -> None:
    """Persist the usage records of every collector the run's calls went through, then how the
    run's steps ended.

    All collectors, not one: every role's adapter is a collector, and a run's steps use several roles.
    """
    db = getattr(context, "db", None)
    router = context.model.llm_router
    if db is None:
        if router is not None:
            logger.warning("Cannot flush telemetry: no db on RunContext")
        return

    for collector in router.collectors() if router is not None else ():
        try:
            collector.flush(db)
        except Exception:
            logger.warning("Failed to flush telemetry", exc_info=True)
    if run is not None:
        try:
            record_step_outcomes(db, run.run_id, step_outcomes(run))
        except Exception:
            logger.warning("Failed to record step outcomes", exc_info=True)


def step_outcomes(run: PipelineRun) -> dict[str, str]:
    """`passed` or `failed` for each step that ended; a step still waiting or not run has none."""
    ended = {StepStatus.PASSED: "passed", StepStatus.FAILED: "failed", StepStatus.ERROR: "failed"}
    return {r.step_name: ended[r.status] for r in run.step_records if r.status in ended}
