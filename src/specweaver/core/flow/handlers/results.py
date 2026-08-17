# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Constructing a handler's StepResult for the failure path.

Small, but a *contract*: every handler that gives up reports it the same way.
"""

from __future__ import annotations

from specweaver.commons.timestamps import now_iso
from specweaver.core.flow.engine.state import StepResult, StepStatus


def _error_result(message: str, started_at: str) -> StepResult:
    return StepResult(
        status=StepStatus.ERROR,
        error_message=message,
        started_at=started_at,
        completed_at=now_iso(),
    )
