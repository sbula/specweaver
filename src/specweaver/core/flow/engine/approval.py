# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""HITL approve-on-resume.

``GateEvaluator`` parks HITL gates unconditionally, so a ``resume()`` that merely flips the run
status back to RUNNING re-executes the step and re-parks the gate, forever. Resuming a reviewed
gate-park *is* the approval.

The discriminator lives entirely in already-persisted state, so this needs no schema change and
no approval store:

===================== ================== ================== ============
park flavour          ``record.status``  ``result.status``  verdict
===================== ================== ================== ============
gate-park (HITL)      WAITING_FOR_INPUT  PASSED             **approve**
gate-park on failure  WAITING_FOR_INPUT  FAILED / ERROR     re-execute
handler-park          WAITING_FOR_INPUT  WAITING_FOR_INPUT  re-execute
RESERVE-park          WAITING_FOR_INPUT  PENDING            re-execute
===================== ================== ================== ============

Requiring ``PASSED`` explicitly makes misclassification structurally impossible: every other
flavour re-executes, which is the safe direction — a step that never produced a verdict must
never be skipped.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.core.flow.engine.hydration import hydrate_plan_context
from specweaver.core.flow.engine.models import GateType
from specweaver.core.flow.engine.state import StepStatus

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.engine.state import PipelineRun, StepRecord

logger = logging.getLogger(__name__)


def is_approvable_gate_park(record: StepRecord | None, step_def: PipelineStep) -> bool:
    """True when this parked step represents a human-reviewed, passing HITL gate.

    Pure predicate — no state is mutated, so the AD-2 decision table above can be tested
    exhaustively without driving a pipeline.
    """
    if record is None or record.status != StepStatus.WAITING_FOR_INPUT:
        return False
    if record.result is None or record.result.status != StepStatus.PASSED:
        return False
    # The pipeline YAML can be edited between sessions. If the step at this index is no longer
    # the one that produced the record, approving would skip a genuinely-unrun step on the
    # strength of a different step's result — the same hazard the rehydration name-guard closes.
    if record.step_name != step_def.name:
        logger.warning(
            "Not approving parked step: record '%s' does not match pipeline step '%s' at this "
            "index — the pipeline was edited between sessions, so the step will re-execute",
            record.step_name,
            step_def.name,
        )
        return False
    gate = step_def.gate
    return gate is not None and gate.type == GateType.HITL


def try_approve_parked_step(
    runner: Any,
    run: PipelineRun,
    step_def: PipelineStep,
    step_idx: int,
    total: int,
) -> bool:
    """Complete a reviewed HITL gate-park from its stored result, advancing the run.

    Returns True when the step was approved, in which case the caller MUST skip both handler
    execution and gate evaluation for it — the HITL gate parks unconditionally, so re-evaluating
    it would simply re-park and the defect would survive.

    Takes the runner rather than its collaborators, matching the existing
    ``session.execute_run(runner, ...)`` convention.
    """
    record = run.current_step_record()
    if not is_approvable_gate_park(record, step_def):
        return False
    assert record is not None and record.result is not None

    logger.info(
        "[run_id=%s] Step '%s' was parked at a HITL gate with a passing result and the human "
        "resumed — treating the resume as approval and advancing without re-execution",
        run.run_id,
        step_def.name,
    )
    hydrate_plan_context(step_def, record.result, runner._context)
    run.complete_current_step(record.result)
    runner._persist(run)
    runner._log(run, "gate_approved_on_resume", step_def.name)
    # NFR-7: a step completed with no handler execution is otherwise invisible in the CLI
    # display and unassertable in e2e, so mark it explicitly.
    runner._emit(
        "step_completed",
        step_idx=step_idx,
        step_name=step_def.name,
        step_def=step_def,
        total_steps=total,
        result=record.result,
        approved_on_resume=True,
    )
    return True
