# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""How rigidly a step executes, resolved from the pipeline's intent and the run's criticality.

Execution rigidity used to be an architectural constant: one LLM call per generation step, and a
hand-rolled reflection loop for fixes. That is too much ceremony for a throwaway script and too
little capability for work an agent could iterate on.

The zero-trust machinery already guarantees the result at the step boundary — session isolation,
the authorized merge, the gate battery — so the middle can be a dial without conceding a
guarantee. Nothing here softens a gate; it decides only how the work between two gates is done.
"""

from __future__ import annotations

import enum
import logging
from typing import Any, NamedTuple

from specweaver.commons.enums.dal import DALLevel

logger = logging.getLogger(__name__)


class ExecutionMode(enum.StrEnum):
    """The dial's positions.

    Distinct from `SandboxSettings.execution_mode`, which chooses *where* QA runs (host or
    container). This chooses *how* the work is produced.
    """

    ONESHOT = "oneshot"
    AGENTIC = "agentic"


class ModeDecision(NamedTuple):
    """The mode a step runs in and, when it asked for `agentic` and was refused, why."""

    mode: ExecutionMode
    reason: str | None


NO_CEILING = "set [autonomy] agentic_max_dal in specweaver.toml"


def requested_mode(step_def: Any, policy: Any) -> ExecutionMode:
    """The mode asked for, before criticality gets a say: the step's own, else — for a code or
    tests generation step — the project's, else `oneshot`."""
    from specweaver.core.flow.engine.models import AGENTIC_STEPS

    raw = getattr(step_def, "mode", None)
    if raw is None:
        agentic_kind = (getattr(step_def, "action", None), getattr(step_def, "target", None))
        raw = getattr(policy, "mode", None) if agentic_kind in AGENTIC_STEPS else None
    return ExecutionMode(raw or ExecutionMode.ONESHOT)


def resolve_execution_mode(step_def: Any, context: Any) -> ModeDecision:
    """The mode this step actually runs in, and why agentic was refused when it was.

    Criticality overrules the pipeline author, never the other way round. A run whose DAL is
    unknown is treated as the strictest, and a project that named no ceiling runs nothing agentic.
    """
    isolation = getattr(context, "isolation", None)
    policy = getattr(isolation, "autonomy", None)
    if requested_mode(step_def, policy) is ExecutionMode.ONESHOT:
        return ModeDecision(ExecutionMode.ONESHOT, None)
    ceiling = getattr(policy, "agentic_max_dal", None)
    if ceiling is None:
        return ModeDecision(ExecutionMode.ONESHOT, f"agentic refused: {NO_CEILING}")
    dal = getattr(isolation, "dal_level", None)
    if dal is None:
        return ModeDecision(ExecutionMode.ONESHOT, "agentic refused: the run's DAL is unknown")
    if DALLevel(dal).rank > DALLevel(ceiling).rank:
        reason = (
            f"agentic refused: {DALLevel(dal).value} is above the ceiling {DALLevel(ceiling).value}"
        )
        logger.info("Autonomy: %s", reason)
        return ModeDecision(ExecutionMode.ONESHOT, reason)
    return ModeDecision(ExecutionMode.AGENTIC, None)
