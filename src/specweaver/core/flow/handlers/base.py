# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The contract a pipeline step handler implements.

What a `base` should hold: one Protocol. The context model lives in `run_context.py` and the
helpers in `prompting.py` / `results.py`; all are re-exported below because well over a hundred
files import them from here.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol, runtime_checkable

# Re-exports, NOT definitions. ~30 files import them from here, so the old names keep resolving.
# New code should import from the module that owns them. `_now_iso` delegates to the L0 commons leaf
# rather than being a seventh place to change.
from specweaver.commons.timestamps import now_iso as _now_iso
from specweaver.core.flow.handlers.prompting import _build_base_prompt
from specweaver.core.flow.handlers.results import _error_result
from specweaver.core.flow.handlers.run_context import (
    AnalysisContext,
    GraphContext,
    GuidanceContent,
    IsolationPolicy,
    ModelAccess,
    PlanContext,
    RunContext,
    RunHandle,
)

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.engine.state import StepResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Handler protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class StepHandler(Protocol):
    """Protocol for step execution handlers."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult: ...


__all__ = [
    "AnalysisContext",
    "GraphContext",
    "GuidanceContent",
    "IsolationPolicy",
    "ModelAccess",
    "PlanContext",
    "RunContext",
    "RunHandle",
    "StepHandler",
    "_build_base_prompt",
    "_error_result",
    "_now_iso",
]
