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
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from specweaver.infrastructure.llm.models import TaskType
from specweaver.sandbox.execution.core.atom import bash_param_errors

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
    ORCHESTRATE = "orchestrate"
    CONVERT = "convert"
    ARBITRATE = "arbitrate"
    BASH = "bash"


class StepTarget(enum.StrEnum):
    """What to do it on — the noun of a pipeline step."""

    SPEC = "spec"
    CODE = "code"
    TESTS = "tests"
    FEATURE = "feature"
    STANDARDS = "standards"
    DRIFT = "drift"
    COMPONENTS = "components"
    DUAL_PIPELINE = "dual_pipeline"
    CONTRACT = "contract"
    SCENARIO = "scenario"
    VERDICT = "verdict"
    SCRIPT = "script"


class GateType(enum.StrEnum):
    """How a gate evaluates: automatically or with human approval."""

    AUTO = "auto"
    HITL = "hitl"
    RESERVE = "reserve"
    JOIN = "join"


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


class RuleOperator(enum.StrEnum):
    """Operators for evaluating router rules."""

    EQ = "=="
    NEQ = "!="
    LT = "<"
    GT = ">"
    CONTAINS = "contains"
    IN = "in"
    IS_EMPTY = "is_empty"
    NOT_EMPTY = "not_empty"


# ---------------------------------------------------------------------------
# The step table
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepKind:
    """One kind of pipeline step: its pair, the model role it uses (None: no model), whether an
    agent may run it with write tools, and whether it runs side pipelines whose roles a run needs."""

    action: StepAction
    target: StepTarget
    role: TaskType | None
    agentic: bool = False
    runs_sides: bool = False


_A, _T, _R = StepAction, StepTarget, TaskType

#: Every step a pipeline may declare, once. The registry gives each row its handler.
STEPS: tuple[StepKind, ...] = (
    StepKind(_A.DRAFT, _T.SPEC, _R.DRAFT),
    StepKind(_A.VALIDATE, _T.SPEC, None),
    StepKind(_A.VALIDATE, _T.CODE, None),
    StepKind(_A.VALIDATE, _T.TESTS, None),
    StepKind(_A.REVIEW, _T.SPEC, _R.REVIEW),
    StepKind(_A.REVIEW, _T.CODE, _R.REVIEW),
    StepKind(_A.GENERATE, _T.CODE, _R.IMPLEMENT, agentic=True),
    StepKind(_A.GENERATE, _T.TESTS, _R.IMPLEMENT, agentic=True),
    StepKind(_A.LINT_FIX, _T.CODE, _R.CHECK),
    StepKind(_A.DRAFT, _T.FEATURE, _R.DRAFT),
    StepKind(_A.VALIDATE, _T.FEATURE, None),
    StepKind(_A.DECOMPOSE, _T.FEATURE, _R.PLAN),
    StepKind(_A.PLAN, _T.SPEC, _R.PLAN),
    StepKind(_A.ENRICH, _T.STANDARDS, _R.CHECK),
    StepKind(_A.DETECT, _T.DRIFT, _R.REVIEW),
    StepKind(_A.ORCHESTRATE, _T.COMPONENTS, None),
    StepKind(_A.ORCHESTRATE, _T.DUAL_PIPELINE, None, runs_sides=True),
    StepKind(_A.GENERATE, _T.CONTRACT, None),
    StepKind(_A.GENERATE, _T.SCENARIO, _R.SCENARIO),
    StepKind(_A.CONVERT, _T.SCENARIO, None),
    StepKind(_A.ARBITRATE, _T.VERDICT, _R.REVIEW),
    StepKind(_A.BASH, _T.SCRIPT, None),
)

VALID_STEP_COMBINATIONS: frozenset[tuple[StepAction, StepTarget]] = frozenset(
    (s.action, s.target) for s in STEPS
)

#: The steps an agent may run with write tools: code and tests generation only.
AGENTIC_STEPS: frozenset[tuple[StepAction, StepTarget]] = frozenset(
    (s.action, s.target) for s in STEPS if s.agentic
)

#: The role each model-calling step uses. A run resolves every role its steps need before the first
#: call, so an unset role refuses at the start, not halfway through a paid run.
ROLE_OF_STEP: dict[tuple[StepAction, StepTarget], TaskType] = {
    (s.action, s.target): s.role for s in STEPS if s.role is not None
}


#: The steps that run side pipelines; a run resolves the sides' roles too.
SIDE_RUNNING_STEPS: frozenset[tuple[StepAction, StepTarget]] = frozenset(
    (s.action, s.target) for s in STEPS if s.runs_sides
)


def role_of(action: StepAction, target: StepTarget) -> TaskType | None:
    """The model role of a step; None when it calls no model or is not declared."""
    return ROLE_OF_STEP.get((action, target))


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
        on_exhausted: What a loop-back gate does once its rounds are spent: `stop` fails the run,
            `park` waits for the person and gives a resume a fresh set of rounds.
    """

    type: GateType = GateType.AUTO
    condition: GateCondition = GateCondition.COMPLETED
    on_fail: OnFailAction = OnFailAction.ABORT
    loop_target: str | None = None
    max_retries: int = Field(default=3, ge=0)
    max_retries_hitl: int = Field(default=5, ge=0)
    on_exhausted: Literal["stop", "park"] = "stop"


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class RouterRule(BaseModel):
    """A conditional rule for pipeline branching.

    Attributes:
        field: Dot-notation path to the value in StepResult.output.
        operator: Comparison operator.
        value: Static value to compare against.
        target: Step name to route to if this rule matches.
    """

    field: str
    operator: RuleOperator
    value: Any = None
    target: str


class RouterDefinition(BaseModel):
    """A router configuration for a pipeline step.

    Attributes:
        rules: List of rules evaluated in sequence. First match wins.
        default_target: Fallback step name if no rules match.
    """

    rules: list[RouterRule] = Field(default_factory=list)
    default_target: str


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

    `extra="allow"`, deliberately, and it is neither of the two obvious choices. The default
    `ignore` DROPPED an undeclared key silently: `script:` written beside `action:` instead of under
    `params:` produced `params == {}` and a pipeline that validated clean, so the mistake surfaced as
    a handler error much later in a long, gated run. `forbid` would reject it — and would also break
    the forward-compatibility contract this repo states outright in
    `test_load_with_extra_fields_ignored`, that an unknown field from a future version must load.

    `allow` keeps both: an unknown field loads, and it is still THERE for `validate_flow` to look at,
    which is how a misplaced param can be named without forbidding fields nobody has invented yet.
    """

    model_config = ConfigDict(extra="allow")

    #: A validation-rule id, for the validation pipelines that reuse this model. Declared rather than
    #: absorbed by `extra="ignore"`: it is the only undeclared key any shipped pipeline uses, and
    #: leaving it undeclared was what made the model unable to tell a real field from a typo.
    rule: str | None = None

    name: str
    action: StepAction
    target: StepTarget
    params: dict[str, Any] = Field(default_factory=dict)
    gate: GateDefinition | None = None
    router: RouterDefinition | None = None
    description: str = ""
    # Tri-state — None = defer to the run-wide isolation policy
    # (context.isolation.enforce_isolation); True = force isolation on; False = force opt-out.
    use_worktree: bool | None = None
    # Tri-state, same shape — None = defer to the install's autonomy policy; "oneshot"/"agentic"
    # state the step's own intent. The run's DAL can still refuse agentic; it never forces it.
    mode: str | None = None


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
    cache_dirs: list[str] = Field(default_factory=list)

    def get_step(self, name: str) -> PipelineStep | None:
        """Find a step by name, or None if not found."""
        for step in self.steps:
            if step.name == name:
                return step
        return None

    def get_step_index(self, name: str) -> int | None:
        """Find the index of a step by name, or None if not found."""
        for i, step in enumerate(self.steps):
            if step.name == name:
                return i
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
        - each step declares the params its action requires

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

            # Router validation
            if step.router is not None:
                errors.extend(_validate_router(step.name, step.router, name_to_index))

            # Required params, at load rather than when the step finally runs
            errors.extend(_validate_params(step))
            errors.extend(_validate_mode(step))
            errors.extend(_validate_orchestrate(step))

        return errors


#: Params each action REQUIRES, checked when the pipeline is loaded rather than when the step runs.
#:
#: Uniform mechanism, not a uniform demand: every action is looked up, and one that declares nothing
#: passes. Bash is the only action with a requirement because it is the only one that names one —
#: this is not a bash special case, and adding another action is one entry that applies at load for
#: free.
_REQUIRED_PARAMS: dict[StepAction, tuple[str, ...]] = {
    StepAction.BASH: ("script",),
}


def _validate_orchestrate(step: PipelineStep) -> list[str]:
    """`params.mode` on `orchestrate` once chose the dual run; it is refused, never translated."""
    if step.action is not StepAction.ORCHESTRATE or "mode" not in step.params:
        return []
    return [
        f"Step '{step.name}': `params.mode` is no longer read on orchestrate steps; "
        "for a dual run use `target: dual_pipeline`"
    ]


def _validate_mode(step: PipelineStep) -> list[str]:
    """A step's `mode` is `oneshot` or `agentic`, and `agentic` only where an agent may write."""
    if step.mode is None or step.mode == "oneshot":
        return []
    if step.mode != "agentic":
        return [f"Step '{step.name}' has mode {step.mode!r}; a step's mode is oneshot or agentic"]
    if (step.action, step.target) not in AGENTIC_STEPS:
        return [
            f"Step '{step.name}' ({step.action.value} {step.target.value}) asks for agentic; "
            "only code and tests generation steps may run agentic"
        ]
    return []


def _validate_params(step: PipelineStep) -> list[str]:
    """Required params a step declares nothing for, and ones written in the wrong place.

    The second half is the footgun this exists for. An author who writes `script:` beside `action:`
    rather than under `params:` gets a step whose params are empty and whose extras hold exactly the
    value they meant — which is enough to say so precisely, instead of reporting a missing param and
    leaving them to find a key that is right there.
    """
    errors: list[str] = []
    if step.action is StepAction.BASH:
        errors.extend(f"Step '{step.name}': {error}" for error in bash_param_errors(step.params))
    required = _REQUIRED_PARAMS.get(step.action, ())
    extras = step.model_extra or {}
    for key in required:
        if step.params.get(key):
            continue
        if key in extras:
            errors.append(
                f"Step '{step.name}' ({step.action.value}) has '{key}' at the step level; "
                f"it belongs under 'params:'"
            )
        else:
            errors.append(
                f"Step '{step.name}' ({step.action.value}) is missing required param '{key}'"
            )
    return errors


def _validate_router(
    step_name: str,
    router: RouterDefinition,
    name_to_index: dict[str, int],
) -> list[str]:
    """Validate a router's target references.

    Returns:
        List of error messages (empty if valid).
    """
    errors = []
    if router.default_target not in name_to_index:
        errors.append(
            f"Step '{step_name}' has router default_target "
            f"'{router.default_target}' which does not exist"
        )
    for rule in router.rules:
        if rule.target not in name_to_index:
            errors.append(
                f"Step '{step_name}' has router rule target '{rule.target}' which does not exist"
            )
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
