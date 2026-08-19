# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""How rigid a step runs is policy, and criticality overrules the pipeline author.

Proves: C-FLOW-11 FR-1, C-FLOW-11 FR-2, C-FLOW-11 NFR-2

Execution rigidity was an architectural constant: every generation step is one LLM call and every
fix loop is hand-rolled. That over-delivers ceremony for a throwaway script and under-delivers for
an agent that could iterate with tools. The zero-trust machinery already guarantees the result at
the step boundary — session isolation, authorized merge, the gate battery — so the middle can be a
dial without giving anything up.

The dial is tri-state in the same shape as `use_worktree`, and for the same reason: a pipeline
author states an intent, and policy decides when the intent is allowed.
"""

from __future__ import annotations

from typing import Any

import pytest

from specweaver.commons.enums.dal import DALLevel
from specweaver.core.flow.engine.autonomy import ExecutionMode, resolve_execution_mode


class _Isolation:
    def __init__(self, dal: DALLevel | None, policy: Any) -> None:
        self.dal_level = dal
        self.autonomy = policy


class _Context:
    def __init__(self, dal: DALLevel | None = None, policy: Any = None) -> None:
        self.isolation = _Isolation(dal, policy)


class _Step:
    def __init__(self, mode: str | None = None) -> None:
        self.mode = mode


class _Policy:
    """Stands in for `AutonomySettings` without dragging config into a dial test."""

    def __init__(self, mode: str = "oneshot", agentic_max_dal: DALLevel = DALLevel.DAL_D) -> None:
        self.mode = mode
        self.agentic_max_dal = agentic_max_dal


def test_a_step_with_no_opinion_runs_oneshot() -> None:
    """FR-1. Zero regression is the whole licence for this capability: every shipped pipeline
    predates the dial and must keep running exactly as it did."""
    assert resolve_execution_mode(_Step(), _Context()) is ExecutionMode.ONESHOT


def test_a_missing_attribute_is_not_a_crash() -> None:
    """The runner must survive a step model from an older pipeline that has no `mode` at all."""

    class _Bare:
        pass

    assert resolve_execution_mode(_Bare(), _Context()) is ExecutionMode.ONESHOT


def test_a_step_can_ask_for_agentic() -> None:
    context = _Context(DALLevel.DAL_E, _Policy())

    assert resolve_execution_mode(_Step("agentic"), context) is ExecutionMode.AGENTIC


def test_criticality_overrules_the_pipeline_author() -> None:
    """FR-2. This is the requirement that makes the dial *assurance* policy rather than a
    convenience flag. A DAL-A target is not a place to let an agent improvise, whatever the YAML
    asked for."""
    context = _Context(DALLevel.DAL_A, _Policy())

    assert resolve_execution_mode(_Step("agentic"), context) is ExecutionMode.ONESHOT


def test_the_threshold_is_where_it_says_it_is() -> None:
    """The control for FR-2. A downgrade that fired at every DAL would make agentic unreachable
    and the whole capability inert."""
    permissive = _Policy(agentic_max_dal=DALLevel.DAL_B)
    context = _Context(DALLevel.DAL_B, permissive)

    assert resolve_execution_mode(_Step("agentic"), context) is ExecutionMode.AGENTIC


def test_an_unknown_dal_is_treated_as_the_strictest() -> None:
    """Failing closed: if the run could not resolve criticality, it does not get to improvise."""
    context = _Context(None, _Policy())

    assert resolve_execution_mode(_Step("agentic"), context) is ExecutionMode.ONESHOT


def test_policy_can_make_agentic_the_default_without_editing_pipelines() -> None:
    """FR-2 from the other side: the dial is settable for a whole install, not per YAML file."""
    context = _Context(DALLevel.DAL_E, _Policy(mode="agentic"))

    assert resolve_execution_mode(_Step(), context) is ExecutionMode.AGENTIC


def test_a_step_may_opt_out_of_an_agentic_default() -> None:
    """Tri-state, both directions. A deterministic step stays deterministic under any policy."""
    context = _Context(DALLevel.DAL_E, _Policy(mode="agentic"))

    assert resolve_execution_mode(_Step("oneshot"), context) is ExecutionMode.ONESHOT


def test_an_unreadable_mode_is_refused_rather_than_guessed() -> None:
    """A typo in a pipeline must not silently pick a rigidity nobody chose."""
    with pytest.raises(ValueError, match="mode"):
        resolve_execution_mode(_Step("agentik"), _Context(DALLevel.DAL_E, _Policy()))
