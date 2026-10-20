# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""How rigid a step runs is policy, and criticality overrules the pipeline author.

Proves: C-FLOW-11 FR-1, C-FLOW-11 FR-2, C-FLOW-11 FR-7, C-FLOW-11 NFR-2

Execution rigidity was an architectural constant: every generation step is one LLM call and every
fix loop is hand-rolled. That over-delivers ceremony for a throwaway script and under-delivers for
an agent that could iterate with tools. The zero-trust machinery already guarantees the result at
the step boundary — session isolation, authorized merge, the gate battery — so the middle can be a
dial without giving anything up.

The dial is tri-state in the same shape as `use_worktree`, and for the same reason: a pipeline
author states an intent, and policy decides when the intent is allowed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from specweaver.commons.enums.dal import DALLevel
from specweaver.core.config.autonomy_policy import AutonomyPolicy
from specweaver.core.flow.engine.autonomy import ExecutionMode, ModeDecision, resolve_execution_mode
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.handlers.run_context import IsolationPolicy, RunContext

_GENERATE = {"action": StepAction.GENERATE, "target": StepTarget.CODE}


def _step(mode: str | None = None, **kind: Any) -> PipelineStep:
    return PipelineStep(name="s", mode=mode, **(kind or _GENERATE))


def _context(dal: DALLevel | None = None, **policy: Any) -> RunContext:
    isolation = IsolationPolicy(dal_level=dal, autonomy=AutonomyPolicy(**policy))
    return RunContext(project_path=Path("."), spec_path=Path("s.md"), isolation=isolation)


_OPEN = {"agentic_max_dal": DALLevel.DAL_D}


def test_a_step_with_no_opinion_runs_oneshot() -> None:
    """FR-1. Every shipped pipeline predates the dial and must keep running exactly as it did."""
    decision = resolve_execution_mode(_step(), _context(DALLevel.DAL_E, **_OPEN))

    assert decision == ModeDecision(ExecutionMode.ONESHOT, None)


def test_a_step_can_ask_for_agentic() -> None:
    decision = resolve_execution_mode(_step("agentic"), _context(DALLevel.DAL_E, **_OPEN))

    assert decision == ModeDecision(ExecutionMode.AGENTIC, None)


def test_criticality_overrules_the_pipeline_author_and_says_so() -> None:
    """FR-2: a riskier target runs one-shot, and the result names the DAL and the ceiling."""
    decision = resolve_execution_mode(_step("agentic"), _context(DALLevel.DAL_B, **_OPEN))

    assert decision.mode is ExecutionMode.ONESHOT
    assert decision.reason == "agentic refused: DAL_B is above the ceiling DAL_D"


def test_the_threshold_is_where_it_says_it_is() -> None:
    """The control for FR-2: at the ceiling itself, agentic stands."""
    context = _context(DALLevel.DAL_B, agentic_max_dal=DALLevel.DAL_B)

    assert resolve_execution_mode(_step("agentic"), context).mode is ExecutionMode.AGENTIC


def test_no_ceiling_refuses_agentic_naming_the_setting() -> None:
    decision = resolve_execution_mode(_step("agentic"), _context(DALLevel.DAL_E))

    assert decision.mode is ExecutionMode.ONESHOT
    assert "[autonomy] agentic_max_dal" in (decision.reason or "")


def test_an_unknown_dal_is_treated_as_the_strictest() -> None:
    """Failing closed: a run whose criticality is unknown does not improvise."""
    assert resolve_execution_mode(_step("agentic"), _context(None, **_OPEN)).mode is (
        ExecutionMode.ONESHOT
    )


def test_the_project_can_make_agentic_the_default() -> None:
    context = _context(DALLevel.DAL_E, mode="agentic", **_OPEN)

    assert resolve_execution_mode(_step(), context).mode is ExecutionMode.AGENTIC


@pytest.mark.parametrize(
    "kind",
    [
        {"action": StepAction.REVIEW, "target": StepTarget.CODE},
        {"action": StepAction.GENERATE, "target": StepTarget.CONTRACT},
    ],
)
def test_the_project_default_reaches_code_and_test_generation_only(kind: dict[str, Any]) -> None:
    """FR-7: a project-wide `agentic` never gives a reviewer or a contract step write tools."""
    context = _context(DALLevel.DAL_E, mode="agentic", **_OPEN)

    assert resolve_execution_mode(_step(**kind), context) == ModeDecision(
        ExecutionMode.ONESHOT, None
    )


def test_a_step_may_opt_out_of_an_agentic_default() -> None:
    context = _context(DALLevel.DAL_E, mode="agentic", **_OPEN)

    assert resolve_execution_mode(_step("oneshot"), context).mode is ExecutionMode.ONESHOT
