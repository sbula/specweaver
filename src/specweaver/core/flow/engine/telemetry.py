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
    """Record how the run's steps ended, so its calls join the cost history.

    The calls themselves are already in the ledger: each collector writes its own row as the call
    happens. Each failed write logs its own warning; the run's total is logged here, for the log file.
    """
    _log_missing_calls(context, logger, run)
    db = getattr(context, "db", None)
    if db is None:
        return
    if run is not None:
        try:
            record_step_outcomes(db, run.run_id, step_outcomes(run))
        except Exception:
            logger.warning("Failed to record step outcomes", exc_info=True)


def _log_missing_calls(
    context: RunContext, logger: logging.Logger, run: PipelineRun | None
) -> None:
    router = getattr(getattr(context, "model", None), "llm_router", None)
    try:
        missing = router.unwritten() if router is not None else 0
    except Exception:
        return
    if missing:
        run_id = run.run_id if run is not None else "?"
        logger.info("Run %s: %d calls are missing from the cost ledger", run_id, missing)


def step_outcomes(run: PipelineRun) -> dict[str, str]:
    """`passed` or `failed` for each step that ended; a step still waiting or not run has none.

    A review that returned its verdict did its work, so a denied one counts as passed.
    """
    ended = {StepStatus.PASSED: "passed", StepStatus.FAILED: "failed", StepStatus.ERROR: "failed"}
    outcomes = {}
    for record in run.step_records:
        if record.status not in ended:
            continue
        verdict = (record.result.output or {}).get("verdict") if record.result else None
        reviewed = record.status is StepStatus.FAILED and verdict == "denied"
        outcomes[record.step_name] = "passed" if reviewed else ended[record.status]
    return outcomes
