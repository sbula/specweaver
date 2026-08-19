# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The dial is configuration and pipeline syntax, not a constant in Python.

Proves: C-FLOW-11 FR-1, C-FLOW-11 FR-2

A dial nothing can turn is an architectural constant with extra steps. Two surfaces have to exist
for the capability to be real: a pipeline step can name its mode, and an install can set the
policy without editing any pipeline.
"""

from __future__ import annotations

from specweaver.commons.enums.dal import DALLevel
from specweaver.core.config.settings import AutonomySettings
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


def test_the_shipped_policy_is_oneshot() -> None:
    """Zero regression. Every pipeline in the repo predates the dial."""
    assert AutonomySettings().mode == "oneshot"


def test_the_shipped_agentic_ceiling_excludes_the_critical_levels() -> None:
    """DAL-A and DAL-B are catastrophic and severe. Neither is a place to improvise."""
    ceiling = DALLevel(AutonomySettings().agentic_max_dal)

    assert ceiling.rank < DALLevel.DAL_B.rank


def test_the_turn_ceiling_ships_finite() -> None:
    assert AutonomySettings().max_turns >= 1


def test_the_policy_is_configurable() -> None:
    settings = AutonomySettings(mode="agentic", agentic_max_dal=DALLevel.DAL_B, max_turns=3)

    assert settings.mode == "agentic"
    assert settings.max_turns == 3
