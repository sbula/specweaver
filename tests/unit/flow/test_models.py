# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for pipeline models — enums, Pydantic models, flow validation."""

from __future__ import annotations

import pytest

from specweaver.flow.models import (
    VALID_STEP_COMBINATIONS,
    GateCondition,
    GateDefinition,
    GateType,
    OnFailAction,
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)


# ---------------------------------------------------------------------------
# StepAction enum
# ---------------------------------------------------------------------------


class TestStepAction:
    """Tests for the StepAction enum."""

    def test_all_actions_exist(self) -> None:
        assert StepAction.DRAFT == "draft"
        assert StepAction.VALIDATE == "validate"
        assert StepAction.REVIEW == "review"
        assert StepAction.GENERATE == "generate"

    def test_action_count(self) -> None:
        assert len(StepAction) == 4


# ---------------------------------------------------------------------------
# StepTarget enum
# ---------------------------------------------------------------------------


class TestStepTarget:
    """Tests for the StepTarget enum."""

    def test_all_targets_exist(self) -> None:
        assert StepTarget.SPEC == "spec"
        assert StepTarget.CODE == "code"
        assert StepTarget.TESTS == "tests"

    def test_target_count(self) -> None:
        assert len(StepTarget) == 3


# ---------------------------------------------------------------------------
# VALID_STEP_COMBINATIONS
# ---------------------------------------------------------------------------


class TestValidStepCombinations:
    """Tests for valid action+target combinations."""

    def test_combination_count(self) -> None:
        assert len(VALID_STEP_COMBINATIONS) == 7

    @pytest.mark.parametrize(
        ("action", "target"),
        [
            (StepAction.DRAFT, StepTarget.SPEC),
            (StepAction.VALIDATE, StepTarget.SPEC),
            (StepAction.VALIDATE, StepTarget.CODE),
            (StepAction.REVIEW, StepTarget.SPEC),
            (StepAction.REVIEW, StepTarget.CODE),
            (StepAction.GENERATE, StepTarget.CODE),
            (StepAction.GENERATE, StepTarget.TESTS),
        ],
    )
    def test_valid_combination(
        self, action: StepAction, target: StepTarget
    ) -> None:
        assert (action, target) in VALID_STEP_COMBINATIONS

    @pytest.mark.parametrize(
        ("action", "target"),
        [
            (StepAction.DRAFT, StepTarget.CODE),
            (StepAction.DRAFT, StepTarget.TESTS),
            (StepAction.GENERATE, StepTarget.SPEC),
            (StepAction.REVIEW, StepTarget.TESTS),
            (StepAction.VALIDATE, StepTarget.TESTS),
        ],
    )
    def test_invalid_combination(
        self, action: StepAction, target: StepTarget
    ) -> None:
        assert (action, target) not in VALID_STEP_COMBINATIONS


# ---------------------------------------------------------------------------
# GateDefinition
# ---------------------------------------------------------------------------


class TestGateDefinition:
    """Tests for GateDefinition model."""

    def test_defaults(self) -> None:
        gate = GateDefinition()
        assert gate.type == GateType.AUTO
        assert gate.condition == GateCondition.COMPLETED
        assert gate.on_fail == OnFailAction.ABORT
        assert gate.loop_target is None
        assert gate.max_retries == 3

    def test_hitl_gate(self) -> None:
        gate = GateDefinition(type=GateType.HITL, condition=GateCondition.COMPLETED)
        assert gate.type == GateType.HITL

    def test_loop_back_gate(self) -> None:
        gate = GateDefinition(
            on_fail=OnFailAction.LOOP_BACK,
            loop_target="draft_spec",
            max_retries=5,
        )
        assert gate.on_fail == OnFailAction.LOOP_BACK
        assert gate.loop_target == "draft_spec"
        assert gate.max_retries == 5

    def test_all_gate_types(self) -> None:
        assert GateType.AUTO == "auto"
        assert GateType.HITL == "hitl"

    def test_all_conditions(self) -> None:
        assert GateCondition.ALL_PASSED == "all_passed"
        assert GateCondition.ACCEPTED == "accepted"
        assert GateCondition.COMPLETED == "completed"

    def test_all_on_fail_actions(self) -> None:
        assert OnFailAction.ABORT == "abort"
        assert OnFailAction.RETRY == "retry"
        assert OnFailAction.LOOP_BACK == "loop_back"
        assert OnFailAction.CONTINUE == "continue"


# ---------------------------------------------------------------------------
# PipelineStep
# ---------------------------------------------------------------------------


class TestPipelineStep:
    """Tests for PipelineStep model."""

    def test_minimal_step(self) -> None:
        step = PipelineStep(
            name="check_spec",
            action=StepAction.VALIDATE,
            target=StepTarget.SPEC,
        )
        assert step.name == "check_spec"
        assert step.action == StepAction.VALIDATE
        assert step.target == StepTarget.SPEC
        assert step.params == {}
        assert step.gate is None
        assert step.description == ""

    def test_step_with_params(self) -> None:
        step = PipelineStep(
            name="strict_check",
            action=StepAction.VALIDATE,
            target=StepTarget.SPEC,
            params={"strict": True, "include_llm": False},
        )
        assert step.params["strict"] is True
        assert step.params["include_llm"] is False

    def test_step_with_gate(self) -> None:
        gate = GateDefinition(
            condition=GateCondition.ALL_PASSED,
            on_fail=OnFailAction.ABORT,
        )
        step = PipelineStep(
            name="check_spec",
            action=StepAction.VALIDATE,
            target=StepTarget.SPEC,
            gate=gate,
        )
        assert step.gate is not None
        assert step.gate.condition == GateCondition.ALL_PASSED

    def test_step_with_description(self) -> None:
        step = PipelineStep(
            name="review_spec",
            action=StepAction.REVIEW,
            target=StepTarget.SPEC,
            description="LLM semantic review of the spec",
        )
        assert step.description == "LLM semantic review of the spec"


# ---------------------------------------------------------------------------
# PipelineDefinition
# ---------------------------------------------------------------------------


class TestPipelineDefinition:
    """Tests for PipelineDefinition model."""

    def _make_pipeline(
        self,
        *,
        name: str = "test_pipeline",
        steps: list[PipelineStep] | None = None,
    ) -> PipelineDefinition:
        if steps is None:
            steps = [
                PipelineStep(
                    name="check_spec",
                    action=StepAction.VALIDATE,
                    target=StepTarget.SPEC,
                ),
                PipelineStep(
                    name="review_spec",
                    action=StepAction.REVIEW,
                    target=StepTarget.SPEC,
                ),
            ]
        return PipelineDefinition(name=name, steps=steps)

    def test_construction(self) -> None:
        p = self._make_pipeline()
        assert p.name == "test_pipeline"
        assert p.description == ""
        assert p.version == "1.0"
        assert len(p.steps) == 2

    def test_with_metadata(self) -> None:
        p = PipelineDefinition(
            name="my_flow",
            description="A test pipeline",
            version="2.0",
            steps=[
                PipelineStep(
                    name="s1",
                    action=StepAction.VALIDATE,
                    target=StepTarget.SPEC,
                ),
            ],
        )
        assert p.description == "A test pipeline"
        assert p.version == "2.0"

    def test_get_step_found(self) -> None:
        p = self._make_pipeline()
        step = p.get_step("review_spec")
        assert step is not None
        assert step.action == StepAction.REVIEW

    def test_get_step_not_found(self) -> None:
        p = self._make_pipeline()
        assert p.get_step("nonexistent") is None

    # -- validate_flow --

    def test_validate_flow_valid(self) -> None:
        p = self._make_pipeline()
        errors = p.validate_flow()
        assert errors == []

    def test_validate_flow_empty_steps(self) -> None:
        p = PipelineDefinition(name="empty", steps=[])
        errors = p.validate_flow()
        assert any("empty" in e.lower() or "no steps" in e.lower() for e in errors)

    def test_validate_flow_duplicate_names(self) -> None:
        steps = [
            PipelineStep(name="s1", action=StepAction.VALIDATE, target=StepTarget.SPEC),
            PipelineStep(name="s1", action=StepAction.REVIEW, target=StepTarget.SPEC),
        ]
        p = PipelineDefinition(name="dup", steps=steps)
        errors = p.validate_flow()
        assert any("duplicate" in e.lower() for e in errors)

    def test_validate_flow_invalid_combination(self) -> None:
        steps = [
            PipelineStep(name="bad", action=StepAction.DRAFT, target=StepTarget.CODE),
        ]
        p = PipelineDefinition(name="bad_combo", steps=steps)
        errors = p.validate_flow()
        assert any("invalid" in e.lower() or "combination" in e.lower() for e in errors)

    def test_validate_flow_loop_target_missing(self) -> None:
        steps = [
            PipelineStep(
                name="s1",
                action=StepAction.REVIEW,
                target=StepTarget.SPEC,
                gate=GateDefinition(
                    on_fail=OnFailAction.LOOP_BACK,
                    loop_target="nonexistent",
                ),
            ),
        ]
        p = PipelineDefinition(name="bad_loop", steps=steps)
        errors = p.validate_flow()
        assert any("loop_target" in e.lower() or "nonexistent" in e.lower() for e in errors)

    def test_validate_flow_loop_back_without_target(self) -> None:
        steps = [
            PipelineStep(
                name="s1",
                action=StepAction.REVIEW,
                target=StepTarget.SPEC,
                gate=GateDefinition(
                    on_fail=OnFailAction.LOOP_BACK,
                    # loop_target not set
                ),
            ),
        ]
        p = PipelineDefinition(name="no_target", steps=steps)
        errors = p.validate_flow()
        assert any("loop_target" in e.lower() for e in errors)

    def test_validate_flow_forward_loop(self) -> None:
        steps = [
            PipelineStep(
                name="s1",
                action=StepAction.VALIDATE,
                target=StepTarget.SPEC,
                gate=GateDefinition(
                    on_fail=OnFailAction.LOOP_BACK,
                    loop_target="s2",  # s2 is AFTER s1 — forward loop
                ),
            ),
            PipelineStep(
                name="s2",
                action=StepAction.REVIEW,
                target=StepTarget.SPEC,
            ),
        ]
        p = PipelineDefinition(name="forward", steps=steps)
        errors = p.validate_flow()
        assert any("forward" in e.lower() for e in errors)

    def test_validate_flow_loop_to_self_is_valid(self) -> None:
        """A step looping back to itself is a retry — should be valid."""
        steps = [
            PipelineStep(
                name="s1",
                action=StepAction.REVIEW,
                target=StepTarget.SPEC,
                gate=GateDefinition(
                    on_fail=OnFailAction.LOOP_BACK,
                    loop_target="s1",
                ),
            ),
        ]
        p = PipelineDefinition(name="self_loop", steps=steps)
        errors = p.validate_flow()
        assert errors == []

    def test_serialization_roundtrip(self) -> None:
        """Model can be serialized to dict and back."""
        p = self._make_pipeline()
        data = p.model_dump()
        p2 = PipelineDefinition.model_validate(data)
        assert p2.name == p.name
        assert len(p2.steps) == len(p.steps)
