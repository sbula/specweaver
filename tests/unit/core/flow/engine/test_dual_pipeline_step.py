# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The dual run is a step of its own, `orchestrate` + `dual_pipeline`, and `params.mode` is refused.

Proves: TECH-082 FR-10, TECH-082 FR-11

| Bucket | Case |
|---|---|
| Happy | a pipeline with `orchestrate`+`dual_pipeline` loads with no error |
| Boundary | `orchestrate`+`components` with no params still loads |
| Degradation | `roles_of` of a pipeline with the dual step includes its two sides' roles |
| Hostile | `orchestrate` with `params.mode` is refused at load, naming `target: dual_pipeline`, whatever the value |
"""

from __future__ import annotations

import pytest

from specweaver.core.flow.engine.models import PipelineDefinition
from specweaver.infrastructure.llm.models import TaskType


def _pipeline(step: dict) -> PipelineDefinition:
    return PipelineDefinition.model_validate({"name": "p", "steps": [{"name": "s", **step}]})


def test_the_dual_step_loads() -> None:
    pipeline = _pipeline({"action": "orchestrate", "target": "dual_pipeline"})

    assert pipeline.validate_flow() == []


def test_a_component_orchestration_still_loads() -> None:
    pipeline = _pipeline({"action": "orchestrate", "target": "components"})

    assert pipeline.validate_flow() == []


def test_the_dual_step_brings_its_sides_roles() -> None:
    from specweaver.core.flow.handlers._llm import roles_of

    roles = roles_of(_pipeline({"action": "orchestrate", "target": "dual_pipeline"}))

    assert {TaskType.IMPLEMENT, TaskType.SCENARIO} <= set(roles)


@pytest.mark.parametrize("mode", ["dual_pipeline", "Dual_Pipeline", "plan"])
@pytest.mark.parametrize("target", ["components", "dual_pipeline"])
def test_a_mode_on_orchestrate_is_refused(mode: str, target: str) -> None:
    pipeline = _pipeline({"action": "orchestrate", "target": target, "params": {"mode": mode}})

    errors = pipeline.validate_flow()

    assert len(errors) == 1
    assert "'s'" in errors[0]
    assert "target: dual_pipeline" in errors[0]


def test_a_mode_on_another_action_is_not_judged_here() -> None:
    pipeline = _pipeline(
        {"action": "bash", "target": "script", "params": {"script": "ls", "mode": "x"}}
    )

    assert not [e for e in pipeline.validate_flow() if "dual_pipeline" in e]
