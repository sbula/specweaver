# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A pipeline that asks for `agentic` where it may not, or names no mode at all, does not load.

Proves: C-FLOW-11 FR-7
Proves: C-FLOW-11 NFR-2

| Bucket | Case |
|---|---|
| Happy | `agentic` on a code or a tests generation step loads |
| Boundary | `oneshot` loads on any step |
| Degradation | not applicable — the check reads the parsed pipeline only |
| Hostile | `agentic` on review, draft, bash, contract and scenario steps, and an unknown mode, are refused naming the step |
"""

from __future__ import annotations

import pytest

from specweaver.core.flow.engine.models import (
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)


def _errors(action: StepAction, target: StepTarget, mode: str) -> list[str]:
    step = PipelineStep(name="only", action=action, target=target, mode=mode)
    return PipelineDefinition(name="p", steps=[step]).validate_flow()


@pytest.mark.parametrize("target", [StepTarget.CODE, StepTarget.TESTS])
def test_agentic_generation_of_code_or_tests_loads(target: StepTarget) -> None:
    assert _errors(StepAction.GENERATE, target, "agentic") == []


def test_oneshot_loads_anywhere() -> None:
    assert _errors(StepAction.REVIEW, StepTarget.CODE, "oneshot") == []


@pytest.mark.parametrize(
    ("action", "target"),
    [
        (StepAction.REVIEW, StepTarget.CODE),
        (StepAction.DRAFT, StepTarget.SPEC),
        (StepAction.BASH, StepTarget.SCRIPT),
        (StepAction.GENERATE, StepTarget.CONTRACT),
        (StepAction.GENERATE, StepTarget.SCENARIO),
    ],
)
def test_agentic_elsewhere_is_refused_naming_the_step(
    action: StepAction, target: StepTarget
) -> None:
    errors = _errors(action, target, "agentic")

    assert any("only" in error and "agentic" in error for error in errors), errors


def test_an_unknown_mode_is_refused() -> None:
    errors = _errors(StepAction.GENERATE, StepTarget.CODE, "agentik")

    assert any("agentik" in error for error in errors), errors
