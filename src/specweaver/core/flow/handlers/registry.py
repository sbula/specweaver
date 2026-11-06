# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Step handlers — bridge between pipeline steps and existing modules.

Each handler adapts a ``(action, target)`` pair to the corresponding
SpecWeaver module (Drafter, Reviewer, Generator, validation runner).
Handlers are thin wrappers: they build the right arguments, call the
module, and translate the result into a ``StepResult``.

Sync modules (validation) are wrapped in ``asyncio.to_thread()`` to
avoid blocking the event loop.

This module re-exports all handler classes from sub-modules for
backward compatibility. All existing imports continue to work.
"""

# Re-export base types and helpers
import logging

from specweaver.core.flow.engine.models import STEPS, StepAction, StepTarget
from specweaver.core.flow.handlers.arbiter import ArbitrateVerdictHandler
from specweaver.core.flow.handlers.base import (  # noqa: F401
    StepHandler,
    _error_result,
    _now_iso,
)
from specweaver.core.flow.handlers.bash_action import BashActionHandler
from specweaver.core.flow.handlers.contract import GenerateContractHandler
from specweaver.core.flow.handlers.decompose import (
    DecomposeFeatureHandler,
    OrchestrateComponentsHandler,
)

# Re-export all handler implementations
from specweaver.core.flow.handlers.draft import DraftFeatureHandler, DraftSpecHandler
from specweaver.core.flow.handlers.drift import DriftCheckHandler
from specweaver.core.flow.handlers.dual_pipeline import ArbitrateDualPipelineHandler
from specweaver.core.flow.handlers.generation import GenerateCodeHandler, GenerateTestsHandler
from specweaver.core.flow.handlers.lint_fix import LintFixHandler
from specweaver.core.flow.handlers.plan_spec import PlanSpecHandler
from specweaver.core.flow.handlers.review import ReviewCodeHandler, ReviewSpecHandler
from specweaver.core.flow.handlers.scenario import (
    ConvertScenarioHandler,
    GenerateScenarioHandler,
)
from specweaver.core.flow.handlers.standards import EnrichStandardsHandler
from specweaver.core.flow.handlers.validation import (
    ValidateCodeHandler,
    ValidateSpecHandler,
    ValidateTestsHandler,
)
from specweaver.core.flow.run_state.run_context import RunContext

__all__ = [
    "ArbitrateDualPipelineHandler",
    "ArbitrateVerdictHandler",
    "BashActionHandler",
    "ConvertScenarioHandler",
    "DecomposeFeatureHandler",
    "DraftSpecHandler",
    "DriftCheckHandler",
    "EnrichStandardsHandler",
    "GenerateCodeHandler",
    "GenerateContractHandler",
    "GenerateScenarioHandler",
    "GenerateTestsHandler",
    "LintFixHandler",
    "OrchestrateComponentsHandler",
    "PlanSpecHandler",
    "ReviewCodeHandler",
    "ReviewSpecHandler",
    "RunContext",
    "StepAction",
    "StepHandler",
    "StepHandlerRegistry",
    "StepTarget",
    "ValidateCodeHandler",
    "ValidateSpecHandler",
    "ValidateTestsHandler",
]


logger = logging.getLogger(__name__)


#: The handler class of each row in the step table (`engine.models.STEPS`).
_HANDLER_OF: dict[tuple[StepAction, StepTarget], type[StepHandler]] = {
    (StepAction.DRAFT, StepTarget.SPEC): DraftSpecHandler,
    (StepAction.DRAFT, StepTarget.FEATURE): DraftFeatureHandler,
    (StepAction.VALIDATE, StepTarget.SPEC): ValidateSpecHandler,
    # ValidateSpecHandler routes kind=feature to the validation_spec_feature battery, so
    # the bundled feature_decomposition pipeline needs only this registry row.
    (StepAction.VALIDATE, StepTarget.FEATURE): ValidateSpecHandler,
    (StepAction.VALIDATE, StepTarget.CODE): ValidateCodeHandler,
    (StepAction.VALIDATE, StepTarget.TESTS): ValidateTestsHandler,
    (StepAction.REVIEW, StepTarget.SPEC): ReviewSpecHandler,
    (StepAction.REVIEW, StepTarget.CODE): ReviewCodeHandler,
    (StepAction.GENERATE, StepTarget.CODE): GenerateCodeHandler,
    (StepAction.GENERATE, StepTarget.TESTS): GenerateTestsHandler,
    (StepAction.LINT_FIX, StepTarget.CODE): LintFixHandler,
    (StepAction.PLAN, StepTarget.SPEC): PlanSpecHandler,
    (StepAction.ENRICH, StepTarget.STANDARDS): EnrichStandardsHandler,
    (StepAction.DETECT, StepTarget.DRIFT): DriftCheckHandler,
    (StepAction.DECOMPOSE, StepTarget.FEATURE): DecomposeFeatureHandler,
    (StepAction.ORCHESTRATE, StepTarget.COMPONENTS): OrchestrateComponentsHandler,
    (StepAction.ORCHESTRATE, StepTarget.DUAL_PIPELINE): ArbitrateDualPipelineHandler,
    (StepAction.GENERATE, StepTarget.CONTRACT): GenerateContractHandler,
    (StepAction.GENERATE, StepTarget.SCENARIO): GenerateScenarioHandler,
    (StepAction.CONVERT, StepTarget.SCENARIO): ConvertScenarioHandler,
    (StepAction.ARBITRATE, StepTarget.VERDICT): ArbitrateVerdictHandler,
    (StepAction.BASH, StepTarget.SCRIPT): BashActionHandler,
}


class StepHandlerRegistry:
    """Maps (action, target) pairs to handler instances.

    One row per step in the step table; a table row with no handler class raises here.
    """

    def __init__(self) -> None:
        self._handlers: dict[tuple[StepAction, StepTarget], StepHandler] = {}
        for step in STEPS:
            key = (step.action, step.target)
            if key not in _HANDLER_OF:
                msg = f"step {step.action}+{step.target} is in the step table but has no handler"
                raise LookupError(msg)
            self._handlers[key] = _HANDLER_OF[key]()

    def get(
        self,
        action: StepAction,
        target: StepTarget,
    ) -> StepHandler | None:
        """Get the handler for a given action+target, or None."""
        return self._handlers.get((action, target))

    def register(
        self,
        action: StepAction,
        target: StepTarget,
        handler: StepHandler,
    ) -> None:
        """Register a custom handler (for testing or extensions)."""
        self._handlers[(action, target)] = handler
