# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Incremental pipeline bypassing — skip steps whose target is unchanged (Feature 3.32 SF-4).

When the runner is given a set of stale nodes (a topology crawl of what actually changed), a step
whose declared target is *not* in that set has nothing to do, and is completed as SKIPPED without
invoking its handler. Global sweeps (``.``, ``src``, ``tests``) are never bypassed — downstream
tools rewrite those targets from the RunContext instead.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.commons.timestamps import now_iso as _now_iso
from specweaver.core.flow.engine.state import StepResult, StepStatus

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineStep

logger = logging.getLogger(__name__)


def try_staleness_bypass(
    runner: Any,
    run: Any,
    step_def: PipelineStep,
    step_idx: int,
    total: int,
) -> bool:
    """Feature 3.32 SF-4: skip a step whose target is pristine (not in ``stale_nodes``).

    Returns True when the step was bypassed and completed as SKIPPED, in which case the caller
    must move to the next step. Global sweeps (``.``, ``src``, ``tests``) are never bypassed —
    downstream tools rewrite those targets from the RunContext instead.

    Extracted from ``PipelineRunner._execute_loop`` alongside the approve-on-resume branch: both
    are step short-circuits that complete the current step and advance without executing a
    handler, and keeping them inline pushed runner.py past its file-size budget.
    """
    context = runner._context
    if context.graph.stale_nodes is None:
        return False

    step_target = step_def.params.get("target") or step_def.params.get("target_path")
    is_global = not step_target or step_target in {".", "src", "src/", "tests", "tests/"}
    if not step_target or is_global or step_target in context.graph.stale_nodes:
        return False

    logger.info(
        "[run_id=%s] Bypassing step '%s': Target '%s' is pristine (not in stale_nodes).",
        run.run_id,
        step_def.name,
        step_target,
    )
    bypass_res = StepResult(
        status=StepStatus.SKIPPED,
        output={"bypassed": True, "reason": "Node is pristine"},
        started_at=_now_iso(),
        completed_at=_now_iso(),
    )
    run.mark_step_running()
    run.complete_current_step(bypass_res)
    runner._persist(run)
    runner._log(run, "step_completed", step_def.name)
    runner._emit(
        "step_completed",
        step_idx=step_idx,
        step_name=step_def.name,
        step_def=step_def,
        total_steps=total,
        result=bypass_res,
    )
    return True
