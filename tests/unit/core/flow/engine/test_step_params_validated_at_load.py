# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A pipeline author's typo fails at load, not three HITL gates later.

Proves: TECH-011 FR-1, TECH-011 FR-2

`PipelineStep.params` was opaque to `validate_flow()`: no step type's params were checked at load,
and each handler validated its own only when the step actually ran — potentially much later in a
long, gated pipeline.

Pydantic's default `extra="ignore"` made it worse. Measured before the fix, the ticket's own opening
example:

```python
{"name": "s", "action": "bash", "target": "script", "script": "echo hi"}
# -> params == {}, validate_flow() == []
```

`script` at step level instead of under `params` was **silently dropped** and the pipeline validated
clean. The author then met a handler error about a missing script, in a run that had already spent
its earlier steps.

Both halves are fixed and both are needed: rejecting the unknown key catches the typo, and requiring
the param catches an author who omitted it entirely.
"""

from __future__ import annotations

from specweaver.core.flow.engine.models import PipelineDefinition, PipelineStep


def _pipeline(step: dict) -> PipelineDefinition:
    return PipelineDefinition.model_validate({"name": "p", "steps": [step]})


def test_a_key_meant_for_params_is_reported_at_the_step_level() -> None:
    """The ticket's opening example. It used to parse clean and drop the value.

    Reported by `validate_flow`, not refused by the model. `extra="forbid"` would refuse it and would
    also break this repo's stated forward-compatibility contract — `test_load_with_extra_fields_
    ignored` requires that an unknown field from a future version still loads. `allow` keeps the key
    visible so the error can name where it belongs.
    """
    errors = _pipeline(
        {"name": "s", "action": "bash", "target": "script", "script": "echo hi"}
    ).validate_flow()

    assert errors, "the misplaced key validated clean"
    assert "belongs under 'params:'" in errors[0], errors


def test_an_unknown_future_field_still_loads() -> None:
    """The forward-compatibility contract this must not break."""
    pipeline = _pipeline(
        {
            "name": "s",
            "action": "bash",
            "target": "script",
            "params": {"script": "x"},
            "unknown_future_field": "ignored",
        }
    )

    assert pipeline.validate_flow() == []


def test_the_same_key_under_params_is_accepted() -> None:
    """The control. Forbidding extras must not forbid the correct spelling."""
    pipeline = _pipeline(
        {"name": "s", "action": "bash", "target": "script", "params": {"script": "echo hi"}}
    )

    assert pipeline.steps[0].params == {"script": "echo hi"}
    assert pipeline.validate_flow() == []


def test_a_bash_step_without_its_script_fails_validation() -> None:
    """The other half: no typo, just an omission, and nothing caught it until the step ran."""
    pipeline = _pipeline({"name": "s", "action": "bash", "target": "script", "params": {}})

    errors = pipeline.validate_flow()

    assert errors, "a bash step with no script validated clean"
    assert "script" in errors[0]


def test_the_error_names_the_step_it_came_from() -> None:
    """A load-time error over a twenty-step pipeline is only useful if it says which step."""
    pipeline = _pipeline(
        {"name": "publish_docs", "action": "bash", "target": "script", "params": {}}
    )

    assert "publish_docs" in pipeline.validate_flow()[0]


def test_a_step_type_with_no_declared_requirements_is_left_alone() -> None:
    """Uniform mechanism, not a uniform demand: only actions that declare requirements are checked.

    The ticket rejected special-casing bash. What is uniform here is that every action is LOOKED UP;
    an action that declares nothing passes, which keeps existing pipelines loading.
    """
    pipeline = _pipeline({"name": "s", "action": "validate", "target": "spec", "params": {}})

    assert pipeline.validate_flow() == []


def test_params_still_accepts_arbitrary_extra_keys() -> None:
    """`params` is a free-form dict by design — handlers own their own shapes."""
    step = PipelineStep.model_validate(
        {"name": "s", "action": "bash", "target": "script", "params": {"script": "x", "env": {}}}
    )

    assert step.params["env"] == {}
