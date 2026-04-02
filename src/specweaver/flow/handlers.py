# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

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
from specweaver.flow._base import (  # noqa: F401
    RunContext,
    StepHandler,
    _error_result,
    _now_iso,
)

# Re-export all handler implementations
from specweaver.flow._draft import DraftSpecHandler
from specweaver.flow._drift import DriftCheckHandler
from specweaver.flow._generation import (
    GenerateCodeHandler,
    GenerateTestsHandler,
    PlanSpecHandler,
)
from specweaver.flow._lint_fix import LintFixHandler
from specweaver.flow._review import ReviewCodeHandler, ReviewSpecHandler
from specweaver.flow._standards import EnrichStandardsHandler
from specweaver.flow._validation import (
    ValidateCodeHandler,
    ValidateSpecHandler,
    ValidateTestsHandler,
)
from specweaver.flow.models import StepAction, StepTarget

__all__ = [
    "DraftSpecHandler",
    "DriftCheckHandler",
    "EnrichStandardsHandler",
    "GenerateCodeHandler",
    "GenerateTestsHandler",
    "LintFixHandler",
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


class StepHandlerRegistry:
    """Maps (action, target) pairs to handler instances.

    Pre-populates with all valid step combinations.
    """

    def __init__(self) -> None:
        self._handlers: dict[tuple[StepAction, StepTarget], StepHandler] = {
            (StepAction.DRAFT, StepTarget.SPEC): DraftSpecHandler(),
            (StepAction.VALIDATE, StepTarget.SPEC): ValidateSpecHandler(),
            (StepAction.VALIDATE, StepTarget.CODE): ValidateCodeHandler(),
            (StepAction.VALIDATE, StepTarget.TESTS): ValidateTestsHandler(),
            (StepAction.REVIEW, StepTarget.SPEC): ReviewSpecHandler(),
            (StepAction.REVIEW, StepTarget.CODE): ReviewCodeHandler(),
            (StepAction.GENERATE, StepTarget.CODE): GenerateCodeHandler(),
            (StepAction.GENERATE, StepTarget.TESTS): GenerateTestsHandler(),
            (StepAction.LINT_FIX, StepTarget.CODE): LintFixHandler(),
            (StepAction.PLAN, StepTarget.SPEC): PlanSpecHandler(),
            (StepAction.ENRICH, StepTarget.STANDARDS): EnrichStandardsHandler(),
            (StepAction.DETECT, StepTarget.DRIFT): DriftCheckHandler(),
        }

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
