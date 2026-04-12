import pytest
from pydantic import ValidationError

from specweaver.core.flow.models import (
    PipelineDefinition,
    PipelineStep,
    RouterDefinition,
    RouterRule,
    RuleOperator,
    StepAction,
    StepTarget,
)


def test_rule_operator_enum():
    """Test standard operators are available."""
    assert RuleOperator.EQ.value == "=="
    assert RuleOperator.NEQ.value == "!="
    assert RuleOperator.LT.value == "<"
    assert RuleOperator.GT.value == ">"
    assert RuleOperator.CONTAINS.value == "contains"
    assert RuleOperator.IN.value == "in"
    assert RuleOperator.IS_EMPTY.value == "is_empty"
    assert RuleOperator.NOT_EMPTY.value == "not_empty"


def test_router_rule_validation():
    """Test valid and invalid fields for a RouterRule."""
    # Valid
    rule = RouterRule(field="output.complexity", operator=RuleOperator.EQ, value="low", target="fast_track")
    assert rule.field == "output.complexity"
    assert rule.operator == RuleOperator.EQ
    assert rule.value == "low"
    assert rule.target == "fast_track"

    # Missing fields
    with pytest.raises(ValidationError):
        RouterRule(field="foo")


def test_router_definition_validation():
    """Test valid RouterDefinition."""
    router = RouterDefinition(
        rules=[
            RouterRule(field="a", operator=RuleOperator.IS_EMPTY, value=None, target="b")
        ],
        default_target="c",
    )
    assert len(router.rules) == 1
    assert router.default_target == "c"


def test_pipeline_step_with_router():
    """Test PipelineStep can take a router configuration."""
    step = PipelineStep(
        name="plan",
        action=StepAction.PLAN,
        target=StepTarget.SPEC,
        router=RouterDefinition(
            rules=[
                RouterRule(field="complex", operator=RuleOperator.EQ, value=True, target="heavy_planning")
            ],
            default_target="generate",
        ),
    )
    assert step.router is not None
    assert step.router.default_target == "generate"
    assert step.router.rules[0].field == "complex"


def test_pipeline_definition_get_step_index():
    """Test correctly resolving the integer index of a step by its string name."""
    pipe = PipelineDefinition(
        name="test",
        steps=[
            PipelineStep(name="step_a", action=StepAction.DRAFT, target=StepTarget.SPEC),
            PipelineStep(name="step_b", action=StepAction.VALIDATE, target=StepTarget.SPEC),
        ]
    )
    assert pipe.get_step_index("step_a") == 0
    assert pipe.get_step_index("step_b") == 1
    assert pipe.get_step_index("missing") is None


def test_pipeline_definition_validate_flow_router():
    """Test that pipeline validates all router targets explicitly."""
    # Valid targets
    pipe = PipelineDefinition(
        name="test_valid",
        steps=[
            PipelineStep(
                name="step_a",
                action=StepAction.DRAFT,
                target=StepTarget.SPEC,
                router=RouterDefinition(
                    rules=[RouterRule(field="complex", operator=RuleOperator.EQ, value=True, target="step_b")],
                    default_target="step_b"
                )
            ),
            PipelineStep(name="step_b", action=StepAction.VALIDATE, target=StepTarget.SPEC),
        ]
    )
    assert not pipe.validate_flow()  # No errors

    # Invalid targets
    pipe_invalid = PipelineDefinition(
        name="test_invalid",
        steps=[
            PipelineStep(
                name="step_a",
                action=StepAction.DRAFT,
                target=StepTarget.SPEC,
                router=RouterDefinition(
                    rules=[RouterRule(field="complex", operator=RuleOperator.EQ, value=True, target="missing")],
                    default_target="missing_default"
                )
            ),
            PipelineStep(name="step_b", action=StepAction.VALIDATE, target=StepTarget.SPEC),
        ]
    )
    errors = pipe_invalid.validate_flow()
    assert len(errors) == 2
    assert any("router rule target 'missing' which does not exist" in err for err in errors)
    assert any("router default_target 'missing_default' which does not exist" in err for err in errors)

