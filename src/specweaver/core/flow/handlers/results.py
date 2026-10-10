# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Constructing a handler's StepResult for the failure path.

Small, but a *contract*: every handler that gives up reports it the same way.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

from specweaver.commons.timestamps import now_iso
from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.infrastructure.llm.budget import BudgetExceededError

if TYPE_CHECKING:
    import logging


def _error_result(message: str, started_at: str) -> StepResult:
    return StepResult(
        status=StepStatus.ERROR,
        error_message=message,
        started_at=started_at,
        completed_at=now_iso(),
    )


def log_step_failure(log: logging.Logger, message: str, *args: Any) -> None:
    """Log the exception being handled: a crash with its traceback, a brake stop as one quiet
    line, since the run reports the stop itself."""
    exc = sys.exc_info()[1]
    if isinstance(exc, BudgetExceededError):
        log.debug(message + ": %s", *args, exc)
    else:
        log.exception(message, *args)
