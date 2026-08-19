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
from typing import Any

from specweaver.commons.enums.dal import DALLevel

logger = logging.getLogger(__name__)


class ExecutionMode(enum.StrEnum):
    """The dial's positions.

    Distinct from `SandboxSettings.execution_mode`, which chooses *where* QA runs (host or
    container). This chooses *how* the work is produced.
    """

    ONESHOT = "oneshot"
    AGENTIC = "agentic"


def _requested(step_def: Any, policy: Any) -> ExecutionMode:
    """The mode asked for, before criticality gets a say.

    An explicit per-step `mode` wins; `None` — or a missing attribute, for a step model that
    predates the dial — defers to the install's policy.
    """
    raw = getattr(step_def, "mode", None)
    if raw is None:
        raw = getattr(policy, "mode", None) or ExecutionMode.ONESHOT
    try:
        return ExecutionMode(raw)
    except ValueError as exc:
        raise ValueError(
            f"Unknown execution mode {raw!r}. Valid values: "
            f"{', '.join(m.value for m in ExecutionMode)}."
        ) from exc


def resolve_execution_mode(step_def: Any, context: Any) -> ExecutionMode:
    """The mode this step actually runs in.

    Criticality overrules the pipeline author, never the other way round: a DAL-A target is not a
    place to let an agent improvise, whatever the YAML asked for. A run whose DAL could not be
    resolved is treated as the strictest, so an unknown risk fails closed.
    """
    isolation = getattr(context, "isolation", None)
    policy = getattr(isolation, "autonomy", None)

    requested = _requested(step_def, policy)
    if requested is ExecutionMode.ONESHOT:
        return requested

    dal = getattr(isolation, "dal_level", None)
    if dal is None:
        logger.debug("Autonomy: DAL unresolved, refusing agentic mode")
        return ExecutionMode.ONESHOT

    ceiling = getattr(policy, "agentic_max_dal", DALLevel.DAL_D)
    if DALLevel(dal).rank > DALLevel(ceiling).rank:
        logger.info(
            "Autonomy: %s is stricter than the agentic ceiling %s — running oneshot",
            DALLevel(dal).value,
            DALLevel(ceiling).value,
        )
        return ExecutionMode.ONESHOT
    return ExecutionMode.AGENTIC
