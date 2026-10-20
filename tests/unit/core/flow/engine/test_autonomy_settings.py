# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The dial is configuration and pipeline syntax, not a constant in Python.

Proves: C-FLOW-11 FR-1, C-FLOW-11 FR-2, C-FLOW-11 NFR-1

A dial nothing can turn is an architectural constant with extra steps. Two surfaces have to exist
for the capability to be real: a pipeline step can name its mode, and a project can set the
policy without editing any pipeline.
"""

from __future__ import annotations

from specweaver.commons.enums.dal import DALLevel
from specweaver.core.config.autonomy_policy import AutonomyPolicy
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget


def test_a_pipeline_step_can_declare_its_mode() -> None:
    step = PipelineStep(
        name="s", action=StepAction.GENERATE, target=StepTarget.CODE, mode="agentic"
    )

    assert step.mode == "agentic"


def test_a_step_without_a_mode_defers_rather_than_defaulting_in_the_model() -> None:
    """Tri-state. `None` means *policy decides*, which is not the same as `oneshot`."""
    step = PipelineStep(name="s", action=StepAction.GENERATE, target=StepTarget.CODE)

    assert step.mode is None


def test_the_empty_policy_is_oneshot() -> None:
    """Zero regression. Every pipeline in the repo predates the dial."""
    assert AutonomyPolicy().mode == "oneshot"


def test_the_empty_policy_names_no_ceiling() -> None:
    """No number nobody chose: agentic waits until a project names its ceiling (FR-2)."""
    assert AutonomyPolicy().agentic_max_dal is None


def test_the_policy_is_configurable() -> None:
    policy = AutonomyPolicy(mode="agentic", agentic_max_dal=DALLevel.DAL_B)

    assert (policy.mode, policy.agentic_max_dal) == ("agentic", DALLevel.DAL_B)
