# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The dial resolves against a policy read from a real `specweaver.toml`, not a hand-built one.

Proves: C-FLOW-11 FR-2
Proves: C-FLOW-11 FR-6

`FR-2` is a seam requirement: the policy starts in the project's file, is read by
`core.config.bootstrap`, rides on the run's isolation policy, and is read by
`core.flow.engine.autonomy`. Three modules have to agree on one attribute name and one enum.

The unit tests for the dial build the policy object by hand, so they would stay green if the
composition root stopped seeding it, if the field were renamed, or if `DALLevel` arrived as a bare
string that `.rank` cannot be taken from. Those are exactly the ways a two-module contract breaks,
and only a test that runs the real chain end to end sees them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.commons.enums.dal import DALLevel
from specweaver.core.config.bootstrap.autonomy_loader import load_autonomy
from specweaver.core.flow.engine.autonomy import ExecutionMode, resolve_execution_mode
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.handlers.run_context import IsolationPolicy, RunContext

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

AGENTIC_STEP = PipelineStep(
    name="generate", action=StepAction.GENERATE, target=StepTarget.CODE, mode="agentic"
)


def _run(tmp_path: Path, dal: DALLevel, **autonomy: str) -> RunContext:
    """A context carrying a resolved DAL and the policy the project's file says."""
    lines = "".join(f'{key} = "{value}"\n' for key, value in autonomy.items())
    (tmp_path / "specweaver.toml").write_text(f"[autonomy]\n{lines}", encoding="utf-8")
    isolation = IsolationPolicy(autonomy=load_autonomy(tmp_path), dal_level=dal)
    return RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", isolation=isolation)


def test_a_low_risk_run_reaches_agentic_through_the_real_chain(tmp_path: Path) -> None:
    context = _run(tmp_path, DALLevel.DAL_E, agentic_max_dal="DAL_D")

    assert resolve_execution_mode(AGENTIC_STEP, context) is ExecutionMode.AGENTIC


def test_a_critical_run_is_refused_through_the_real_chain(tmp_path: Path) -> None:
    """The guarantee. Settings loaded from a real model, ceiling applied to a real DAL."""
    context = _run(tmp_path, DALLevel.DAL_A, agentic_max_dal="DAL_D")

    assert resolve_execution_mode(AGENTIC_STEP, context) is ExecutionMode.ONESHOT


def test_a_configured_ceiling_travels_the_whole_way(tmp_path: Path) -> None:
    """Renaming the field or dropping it from the seed would leave the dial on its built-in
    default and this is the only test that would notice."""
    context = _run(tmp_path, DALLevel.DAL_B, agentic_max_dal="DAL_B")

    assert resolve_execution_mode(AGENTIC_STEP, context) is ExecutionMode.AGENTIC


def test_the_ceiling_still_refuses_one_level_up(tmp_path: Path) -> None:
    """The control: a ceiling that permitted everything would also pass the test above."""
    context = _run(tmp_path, DALLevel.DAL_A, agentic_max_dal="DAL_B")

    assert resolve_execution_mode(AGENTIC_STEP, context) is ExecutionMode.ONESHOT


def test_an_install_wide_default_reaches_a_step_that_asked_for_nothing(tmp_path: Path) -> None:
    """The policy path, not the step path — the half a hand-built policy cannot exercise."""
    plain = PipelineStep(name="g", action=StepAction.GENERATE, target=StepTarget.CODE)
    context = _run(tmp_path, DALLevel.DAL_E, mode="agentic", agentic_max_dal="DAL_E")

    assert resolve_execution_mode(plain, context) is ExecutionMode.AGENTIC
