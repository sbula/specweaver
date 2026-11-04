# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A pipeline step is declared once, in `STEPS`; the other step tables derive from it.

Proves: TECH-082 FR-9

| Bucket | Case |
|---|---|
| Happy | the step pairs, the agentic steps and the roles equal what `STEPS` says; each role is the one written out here |
| Boundary | a row with no role is absent from the roles; no two rows share a pair |
| Degradation | a registry built for a table row it has no handler for raises, naming the row |
| Hostile | `role_of` of an undeclared pair is None |
"""

from __future__ import annotations

import pytest

from specweaver.core.flow.engine import models
from specweaver.core.flow.engine.models import (
    AGENTIC_STEPS,
    ROLE_OF_STEP,
    SIDE_RUNNING_STEPS,
    STEPS,
    VALID_STEP_COMBINATIONS,
    StepAction,
    StepKind,
    StepTarget,
    role_of,
)
from specweaver.infrastructure.llm.models import TaskType

A, T = StepAction, StepTarget

#: The role of every model-calling step, written out by hand (not read from the table).
_ROLES = {
    (A.DRAFT, T.SPEC): TaskType.DRAFT,
    (A.DRAFT, T.FEATURE): TaskType.DRAFT,
    (A.REVIEW, T.SPEC): TaskType.REVIEW,
    (A.REVIEW, T.CODE): TaskType.REVIEW,
    (A.ARBITRATE, T.VERDICT): TaskType.REVIEW,
    (A.DETECT, T.DRIFT): TaskType.REVIEW,
    (A.GENERATE, T.CODE): TaskType.IMPLEMENT,
    (A.GENERATE, T.TESTS): TaskType.IMPLEMENT,
    (A.GENERATE, T.SCENARIO): TaskType.SCENARIO,
    (A.PLAN, T.SPEC): TaskType.PLAN,
    (A.DECOMPOSE, T.FEATURE): TaskType.PLAN,
    (A.LINT_FIX, T.CODE): TaskType.CHECK,
    (A.ENRICH, T.STANDARDS): TaskType.CHECK,
}


def test_the_derived_tables_say_what_steps_says() -> None:
    assert {(s.action, s.target) for s in STEPS} == VALID_STEP_COMBINATIONS
    assert {(s.action, s.target) for s in STEPS if s.agentic} == AGENTIC_STEPS
    assert {(s.action, s.target): s.role for s in STEPS if s.role is not None} == ROLE_OF_STEP


def test_each_step_has_the_role_it_had() -> None:
    assert ROLE_OF_STEP == _ROLES
    assert {(A.GENERATE, T.CODE), (A.GENERATE, T.TESTS)} == AGENTIC_STEPS


def test_a_step_with_no_role_has_none() -> None:
    assert role_of(A.VALIDATE, T.CODE) is None
    assert (A.VALIDATE, T.CODE) in VALID_STEP_COMBINATIONS
    assert (A.VALIDATE, T.CODE) not in ROLE_OF_STEP


def test_no_two_rows_share_a_pair() -> None:
    pairs = [(s.action, s.target) for s in STEPS]

    assert len(pairs) == len(set(pairs))


def test_a_registry_without_a_rows_handler_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from specweaver.core.flow.handlers import registry

    extra = StepKind(A.BASH, T.SPEC, role=None)
    monkeypatch.setattr(registry, "STEPS", (*models.STEPS, extra))

    with pytest.raises(LookupError, match="bash\\+spec"):
        registry.StepHandlerRegistry()


def test_an_undeclared_pair_has_no_role() -> None:
    assert role_of(A.BASH, T.SPEC) is None


def test_only_the_dual_step_runs_sides() -> None:
    """TECH-082 FR-10: the dual run's sides are found through the table, not a param."""
    assert {(s.action, s.target) for s in STEPS if s.runs_sides} == SIDE_RUNNING_STEPS
    assert {(A.ORCHESTRATE, T.DUAL_PIPELINE)} == SIDE_RUNNING_STEPS
