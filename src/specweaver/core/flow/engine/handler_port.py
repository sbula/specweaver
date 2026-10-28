# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the engine needs from the step handlers: a lookup. The caller supplies the registry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
    from specweaver.core.flow.engine.state import StepResult
    from specweaver.core.flow.run_state.run_context import RunContext


class StepRunner(Protocol):
    """One step handler, as the engine calls it."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult: ...


class HandlerLookup(Protocol):
    """Finds the handler for a step's action and target; None when there is none."""

    def get(self, action: StepAction, target: StepTarget) -> StepRunner | None: ...
