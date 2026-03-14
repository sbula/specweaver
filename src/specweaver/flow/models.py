# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Pipeline data models — the blueprint for what a pipeline IS.

This module defines the pure data model for pipelines. It contains no
execution logic, no state tracking, and no persistence. Those concerns
belong to the runner (Step 11) and state manager.

A pipeline is a sequence of steps. Each step combines an **action**
(what to do) with a **target** (what to do it on). Steps can have
optional gates that control flow (proceed, retry, loop back, abort).
"""

from __future__ import annotations

import enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StepAction(enum.StrEnum):
    """What to do — the verb of a pipeline step."""

    DRAFT = "draft"
    VALIDATE = "validate"
    REVIEW = "review"
    GENERATE = "generate"


class StepTarget(enum.StrEnum):
    """What to do it on — the noun of a pipeline step."""

    SPEC = "spec"
    CODE = "code"
    TESTS = "tests"
    # Future: UI = "ui"


class GateType(enum.StrEnum):
    """How a gate evaluates: automatically or with human approval."""

    AUTO = "auto"
    HITL = "hitl"


class GateCondition(enum.StrEnum):
    """What the gate checks to decide pass/fail."""

    ALL_PASSED = "all_passed"  # all validation rules pass
    ACCEPTED = "accepted"  # review verdict == ACCEPTED
    COMPLETED = "completed"  # step finished without error


class OnFailAction(enum.StrEnum):
    """What to do when a gate fails."""

    ABORT = "abort"
    RETRY = "retry"
    LOOP_BACK = "loop_back"
    CONTINUE = "continue"


# ---------------------------------------------------------------------------
# Valid combinations
# ---------------------------------------------------------------------------

VALID_STEP_COMBINATIONS: frozenset[tuple[StepAction, StepTarget]] = frozenset(
    {
        (StepAction.DRAFT, StepTarget.SPEC),
        (StepAction.VALIDATE, StepTarget.SPEC),
        (StepAction.VALIDATE, StepTarget.CODE),
        (StepAction.REVIEW, StepTarget.SPEC),
        (StepAction.REVIEW, StepTarget.CODE),
        (StepAction.GENERATE, StepTarget.CODE),
        (StepAction.GENERATE, StepTarget.TESTS),
    }
)


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


class GateDefinition(BaseModel):
    """A gate sits after a step and decides whether to proceed.

    Attributes:
        type: How the gate evaluates (auto or hitl).
        condition: What to check (all_passed, accepted, completed).
        on_fail: What to do when the condition is not met.
        loop_target: Step name to loop back to (required if on_fail == loop_back).
        max_retries: Maximum retry/loop count before escalating.
    """

    type: GateType = GateType.AUTO
    condition: GateCondition = GateCondition.COMPLETED
    on_fail: OnFailAction = OnFailAction.ABORT
    loop_target: str | None = None
    max_retries: int = Field(default=3, ge=0)


# ---------------------------------------------------------------------------
# Step
# ---------------------------------------------------------------------------


class PipelineStep(BaseModel):
    """A single step in a pipeline — action + target + optional gate.

    Attributes:
        name: Unique identifier within the pipeline.
        action: What to do (draft, validate, review, generate).
        target: What to do it on (spec, code, tests).
        params: Free-form parameters passed to the module at runtime.
        gate: Optional gate that controls flow after this step.
        description: Human-readable description.
    """

    name: str
    action: StepAction
    target: StepTarget
    params: dict[str, Any] = Field(default_factory=dict)
    gate: GateDefinition | None = None
    description: str = ""


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class PipelineDefinition(BaseModel):
    """The blueprint for a pipeline — a named sequence of steps.

    This is a pure data model. It defines the structure but does not
    execute anything. The runner (Step 11) consumes this model.

    Attributes:
        name: Pipeline identifier (e.g. "new_feature").
        description: Human-readable description.
        version: Schema version for future compatibility.
        steps: Ordered list of pipeline steps.
    """

    name: str
    description: str = ""
    version: str = "1.0"
    steps: list[PipelineStep]

    def get_step(self, name: str) -> PipelineStep | None:
        """Find a step by name, or None if not found."""
        for step in self.steps:
            if step.name == name:
                return step
        return None

    def validate_flow(self) -> list[str]:
        """Validate pipeline integrity.

        Checks:
        - Steps list is not empty
        - Step names are unique
        - Each action+target combination is valid
        - loop_back gates have a valid, non-forward loop_target
        - loop_back on_fail requires a loop_target

        Returns:
            List of error messages. Empty list means valid.
        """
        errors: list[str] = []

        # Empty steps
        if not self.steps:
            errors.append("Pipeline has no steps")
            return errors

        # Duplicate names
        names = [s.name for s in self.steps]
        seen: set[str] = set()
        for name in names:
            if name in seen:
                errors.append(f"Duplicate step name: '{name}'")
            seen.add(name)

        # Build name→index map for loop_target validation
        name_to_index = {s.name: i for i, s in enumerate(self.steps)}

        for i, step in enumerate(self.steps):
            # Invalid action+target combination
            if (step.action, step.target) not in VALID_STEP_COMBINATIONS:
                errors.append(
                    f"Invalid action+target combination in step '{step.name}': "
                    f"{step.action}+{step.target}"
                )

            # Gate validation
            if step.gate is not None and step.gate.on_fail == OnFailAction.LOOP_BACK:
                if step.gate.loop_target is None:
                    errors.append(
                        f"Step '{step.name}' has on_fail=loop_back but no loop_target"
                    )
                elif step.gate.loop_target not in name_to_index:
                    errors.append(
                        f"Step '{step.name}' has loop_target='{step.gate.loop_target}' "
                        f"which does not exist"
                    )
                elif name_to_index[step.gate.loop_target] > i:
                    errors.append(
                        f"Step '{step.name}' has a forward loop to "
                        f"'{step.gate.loop_target}' (loops must go backward)"
                    )

        return errors
