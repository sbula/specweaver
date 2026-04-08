# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

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
    LINT_FIX = "lint_fix"
    DECOMPOSE = "decompose"
    PLAN = "plan"
    ENRICH = "enrich"
    DETECT = "detect"


class StepTarget(enum.StrEnum):
    """What to do it on — the noun of a pipeline step."""

    SPEC = "spec"
    CODE = "code"
    TESTS = "tests"
    FEATURE = "feature"
    STANDARDS = "standards"
    DRIFT = "drift"


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
        (StepAction.VALIDATE, StepTarget.TESTS),
        (StepAction.REVIEW, StepTarget.SPEC),
        (StepAction.REVIEW, StepTarget.CODE),
        (StepAction.GENERATE, StepTarget.CODE),
        (StepAction.GENERATE, StepTarget.TESTS),
        (StepAction.LINT_FIX, StepTarget.CODE),
        # Feature decomposition pipeline combos
        (StepAction.DRAFT, StepTarget.FEATURE),
        (StepAction.VALIDATE, StepTarget.FEATURE),
        (StepAction.DECOMPOSE, StepTarget.FEATURE),
        # Planning pipeline combos
        (StepAction.PLAN, StepTarget.SPEC),
        # Standards pipeline combos
        (StepAction.ENRICH, StepTarget.STANDARDS),
        # Validation drift combos
        (StepAction.DETECT, StepTarget.DRIFT),
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
    max_retries_hitl: int = Field(default=5, ge=0)


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
    max_total_loops: int = Field(default=20, ge=0)

    def get_step(self, name: str) -> PipelineStep | None:
        """Find a step by name, or None if not found."""
        for step in self.steps:
            if step.name == name:
                return step
        return None

    @classmethod
    def create_single_step(
        cls,
        name: str,
        action: StepAction,
        target: StepTarget,
        gate: GateDefinition | None = None,
        params: dict[str, Any] | None = None,
        description: str = "",
    ) -> PipelineDefinition:
        """Create an in-memory 1-step pipeline.

        Args:
            name: Unique identifier for the step.
            action: Primary action verb.
            target: Primary target noun.
            gate: Optional gate that controls flow after this step.
            params: Optional execution parameters.
            description: Human-readable context.
        """
        step = PipelineStep(
            name=name,
            action=action,
            target=target,
            params=params or {},
            gate=gate,
            description=description,
        )
        return cls(
            name=f"single_step_{name}",
            description=f"Auto-generated single-step pipeline for {name}",
            version="1.0",
            steps=[step],
        )

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
        seen: set[str] = set()
        for step in self.steps:
            if step.name in seen:
                errors.append(f"Duplicate step name: '{step.name}'")
            seen.add(step.name)

        # Build name→index map for loop_target validation
        name_to_index = {s.name: i for i, s in enumerate(self.steps)}

        for i, step in enumerate(self.steps):
            # Invalid action+target combination
            if (step.action, step.target) not in VALID_STEP_COMBINATIONS:
                errors.append(
                    f"Invalid action+target combination in step '{step.name}': "
                    f"{step.action}+{step.target}"
                )

            # Gate loop_back validation
            if step.gate is not None and step.gate.on_fail == OnFailAction.LOOP_BACK:
                errors.extend(_validate_loop_back(step.name, step.gate, name_to_index, i))

        return errors


def _validate_loop_back(
    step_name: str,
    gate: GateDefinition,
    name_to_index: dict[str, int],
    current_index: int,
) -> list[str]:
    """Validate a loop_back gate's target reference.

    Returns:
        List of error messages (empty if valid).
    """
    if gate.loop_target is None:
        return [f"Step '{step_name}' has on_fail=loop_back but no loop_target"]

    if gate.loop_target not in name_to_index:
        return [f"Step '{step_name}' has loop_target='{gate.loop_target}' which does not exist"]

    if name_to_index[gate.loop_target] > current_index:
        return [
            f"Step '{step_name}' has a forward loop to "
            f"'{gate.loop_target}' (loops must go backward)"
        ]

    return []
