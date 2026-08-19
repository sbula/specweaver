# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The install's autonomy policy reaches the run, at the one place ADR-002 puts such decisions.

Proves: C-FLOW-11 FR-2

`resolve_execution_mode` reads `context.isolation.autonomy`. If nothing ever puts the policy
there, every run resolves against `None`, silently falls back to the built-in ceiling, and the
setting is a comment. That is the failure this file exists to catch — and it is invisible to the
dial's own tests, which construct the policy by hand.

`apply_isolation_policy` is the composition root for exactly this kind of frozen-at-the-edge
decision, and it already serves both roots: `sw run`/`sw resume` and the API's run endpoints.
Seeding anywhere else would leave one of them unpolicied, which is the bug `TECH-013` closed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.commons.enums.dal import DALLevel
from specweaver.core.config.settings import (
    AutonomySettings,
    LLMSettings,
    SpecWeaverSettings,
)
from specweaver.core.flow.engine.isolation import apply_isolation_policy
from specweaver.core.flow.handlers.run_context import RunContext

if TYPE_CHECKING:
    from pathlib import Path

LOGGER = logging.getLogger(__name__)


def _settings(**autonomy: object) -> SpecWeaverSettings:
    return SpecWeaverSettings(llm=LLMSettings(model="m"), autonomy=AutonomySettings(**autonomy))


def _context(tmp_path: Path) -> RunContext:
    return RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")


def test_the_policy_reaches_the_context(tmp_path: Path) -> None:
    context = _context(tmp_path)

    apply_isolation_policy(context, _settings(mode="agentic"), LOGGER)

    assert context.isolation.autonomy is not None
    assert context.isolation.autonomy.mode == "agentic"


def test_the_configured_ceiling_reaches_the_context(tmp_path: Path) -> None:
    """The ceiling is the half that refuses. A default that silently replaced it would make a
    stricter configured ceiling do nothing."""
    context = _context(tmp_path)

    apply_isolation_policy(context, _settings(agentic_max_dal=DALLevel.DAL_E), LOGGER)

    assert DALLevel(context.isolation.autonomy.agentic_max_dal) is DALLevel.DAL_E


def test_a_default_install_still_seeds_a_policy(tmp_path: Path) -> None:
    """The control. `None` would work by accident — the dial falls back to oneshot either way —
    so this pins that the seeding happened rather than that the fallback did."""
    context = _context(tmp_path)

    apply_isolation_policy(context, _settings(), LOGGER)

    assert context.isolation.autonomy is not None
    assert context.isolation.autonomy.mode == "oneshot"


def test_the_run_resolves_a_step_against_the_seeded_policy(tmp_path: Path) -> None:
    """End to end through the two halves: policy seeded here, read by the dial there."""
    from specweaver.core.flow.engine.autonomy import ExecutionMode, resolve_execution_mode
    from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget

    context = _context(tmp_path)
    context.isolation = context.isolation.model_copy(update={"dal_level": DALLevel.DAL_E})
    apply_isolation_policy(context, _settings(mode="agentic"), LOGGER)

    step = PipelineStep(name="s", action=StepAction.GENERATE, target=StepTarget.CODE)

    assert resolve_execution_mode(step, context) is ExecutionMode.AGENTIC


def test_a_broken_settings_object_does_not_crash_the_run(tmp_path: Path) -> None:
    """Best-effort by contract: policy resolution must never take a run down with it."""
    context = _context(tmp_path)

    apply_isolation_policy(context, object(), LOGGER)

    assert context.isolation.autonomy is None
