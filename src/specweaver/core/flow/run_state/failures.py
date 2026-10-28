# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""How a step that gives up logs it: one rule the engine and every handler share."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

from specweaver.infrastructure.llm.budget import BudgetExceededError

if TYPE_CHECKING:
    import logging


def log_step_failure(log: logging.Logger, message: str, *args: Any) -> None:
    """Log the exception being handled: a crash with its traceback, a brake stop as one quiet
    line, since the run reports the stop itself."""
    exc = sys.exc_info()[1]
    if isinstance(exc, BudgetExceededError):
        log.debug("%s: %s", message % args, exc)
    else:
        log.exception(message, *args)
