# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Plan-context hydration — the bridge from a completed step's output into the RunContext.

INT-US-21 FR-2/AD-1. Two distinct plan concepts live on two distinct fields:

* ``decompose+feature`` -> ``context.plan_context.decomposition`` (DecompositionPlan, canonical JSON)
* ``plan+spec``         -> ``context.plan_context.plan`` (implementation PlanArtifact file content)

Both the live runner loop and the resume-time rehydration call into here, so the two paths
cannot drift apart.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from specweaver.commons import json
from specweaver.core.flow.engine.models import StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineDefinition, PipelineStep
    from specweaver.core.flow.engine.state import PipelineRun, StepResult
    from specweaver.core.flow.handlers.base import RunContext

logger = logging.getLogger(__name__)

#: The key `decompose+feature` nests its DecompositionPlan under in ``StepResult.output``.
#:
#: This is the AD-4-frozen seam between the writer (``handlers/decompose.py``) and the reader
#: (this module). It lived as the bare literal ``"plan"`` in both files until the CB-1 pre-commit
#: gate (2026-07-26) observed that two string literals which MUST agree, with nothing forcing them
#: to, is not a frozen seam. Both sides import this name; ``C-FLOW-12`` should too.
DECOMPOSITION_PLAN_KEY = "plan"


def hydrate_plan_context(
    step_def: PipelineStep,
    result: StepResult,
    context: RunContext,
) -> None:
    """Bridge a completed step's output into the RunContext plan fields (INT-US-21 FR-2).

    Two distinct concepts, two distinct fields (AD-1):

    * ``decompose+feature`` -> ``context.plan_context.decomposition`` (DecompositionPlan, canonical JSON)
    * ``plan+spec``         -> ``context.plan_context.plan`` (implementation PlanArtifact file content)

    Only ``PASSED`` results hydrate. This is the single hydration point: the runner calls it
    after a step advances, and ``resume()`` replays it over persisted step records, so the
    live path and the cross-session path cannot drift apart.

    Never raises — a malformed or missing artifact degrades to a WARNING and leaves the field
    untouched, so the consuming step fails with its own loud, specific message (NFR-2/NFR-4).
    """
    combo = (step_def.action, step_def.target)

    if result.status != StepStatus.PASSED:
        # A step that owns a plan field and *tried and failed* invalidates whatever it wrote on a
        # previous attempt. Scenario: decompose passes -> hydrates -> a later step loops back
        # -> decompose re-runs and fails. Retaining the superseded plan lets a downstream
        # orchestrate step consume stale data and silently "succeed". No plan (loud failure)
        # beats wrong plan (silent success). Only the field this combo owns is cleared.
        #
        # Restricted to FAILED/ERROR deliberately: SKIPPED and WAITING_FOR_INPUT mean the step
        # produced no new verdict at all (bypassed, or parked and due to re-run on resume), so
        # there is nothing to supersede and wiping a still-valid plan would be gratuitous.
        if result.status not in (StepStatus.FAILED, StepStatus.ERROR):
            return
        if (
            combo == (StepAction.DECOMPOSE, StepTarget.FEATURE)
            and context.plan_context.decomposition
        ):
            logger.warning(
                "[run_id=%s] Step '%s' did not pass (%s) — clearing the superseded "
                "context.plan_context.decomposition from a previous attempt",
                context.run.run_id,
                step_def.name,
                result.status.value,
            )
            context.plan_context = context.plan_context.model_copy(update={"decomposition": None})
        elif combo == (StepAction.PLAN, StepTarget.SPEC) and context.plan_context.plan:
            logger.warning(
                "[run_id=%s] Step '%s' did not pass (%s) — clearing the superseded "
                "context.plan_context.plan from a previous attempt",
                context.run.run_id,
                step_def.name,
                result.status.value,
            )
            context.plan_context = context.plan_context.model_copy(update={"plan": None})
        return

    if combo == (StepAction.DECOMPOSE, StepTarget.FEATURE):
        try:
            # `default=str` is NOT optional: StateStore persists step records with exactly
            # these semantics (store.py:132-133). Without it, an output carrying a Path/set/
            # custom object raises here on the LIVE path but hydrates fine on the RESUME path
            # (where the store already stringified it) — the same run would behave differently
            # depending on whether it was resumed. Sharing this function is only half the
            # guarantee; the serialization semantics must match too.
            # INT-US-21 SF-02: the handler nests the plan under "plan" so it can also report
            # `decomposition_path` without that key leaking into this field. AD-4 freezes
            # `context.plan_context.decomposition` as canonical DecompositionPlan JSON, and
            # OrchestrateComponentsHandler / C-FLOW-12 consume it as such. The `.get("plan", ...)`
            # fallback keeps records persisted before SF-02 (flat plan) rehydrating correctly.
            payload = result.output or {}
            nested = payload.get(DECOMPOSITION_PLAN_KEY)
            # Local first: `model_copy` erases the narrowing the log call below needs.
            serialized = json.dumps(nested if isinstance(nested, dict) else payload, default=str)
            context.plan_context = context.plan_context.model_copy(
                update={"decomposition": serialized}
            )
        except (TypeError, ValueError) as exc:
            logger.warning(
                "[run_id=%s] Step '%s': decomposition output is not JSON-serializable (%s) — "
                "context.plan_context.decomposition left unset",
                context.run.run_id,
                step_def.name,
                exc,
            )
            return
        logger.info(
            "[run_id=%s] Hydrated context.plan_context.decomposition from step '%s' (%d chars)",
            context.run.run_id,
            step_def.name,
            len(serialized),
        )
        return

    if combo == (StepAction.PLAN, StepTarget.SPEC):
        raw_path = (result.output or {}).get("plan_path")
        if not raw_path or not isinstance(raw_path, str):
            logger.warning(
                "[run_id=%s] Step '%s' passed but carries no usable 'plan_path' output — "
                "context.plan_context.plan left unset",
                context.run.run_id,
                step_def.name,
            )
            return
        try:
            context.plan_context = context.plan_context.model_copy(
                update={"plan": Path(raw_path).read_text(encoding="utf-8")}
            )
        except (OSError, UnicodeDecodeError) as exc:
            # UnicodeDecodeError is a ValueError, NOT an OSError — a corrupt or binary plan
            # artifact would otherwise escape this guard and blow up the runner loop *after*
            # the gate already decided to advance.
            logger.warning(
                "[run_id=%s] Step '%s': plan artifact '%s' could not be read (%s) — "
                "context.plan_context.plan left unset",
                context.run.run_id,
                step_def.name,
                raw_path,
                exc,
            )
            return
        logger.info(
            "[run_id=%s] Hydrated context.plan_context.plan from step '%s' (%s)",
            context.run.run_id,
            step_def.name,
            raw_path,
        )


def rehydrate_from_records(
    pipeline: PipelineDefinition,
    run: PipelineRun,
    context: RunContext,
) -> None:
    """Rebuild the plan context from persisted step records (INT-US-21 FR-3).

    ``context.plan_context`` lives in memory and dies with the process, so a
    resumed run must reconstruct them before the loop starts. This replays
    :func:`hydrate_plan_context` over the stored records, so the live path and the cross-session
    path can never drift apart.

    Two things are load-bearing:

    * **Keys on the stored RESULT status, never the record status.** A gate-parked step's record
      status is ``WAITING_FOR_INPUT`` while its stored result is ``PASSED`` — keying on the record
      would skip exactly the step a resumed run needs (design R/B R2).
    * **Pairs records to step definitions by index AND name.** The pipeline YAML can be edited
      between sessions; a reordered file keeps the same length, so length alone would silently
      pair a stored result with the wrong action/target and hydrate the wrong field.

    Forward iteration means the highest matching index wins. Never raises.
    """
    # Cheap whole-run sanity check before the per-step ones: the caller chooses which
    # PipelineDefinition to resume with, and nothing guarantees it is the one that produced
    # these records (the REST resume path resolves it independently of the CLI path). A
    # mismatch here means every per-step name guard below is about to fire.
    if run.pipeline_name and run.pipeline_name != pipeline.name:
        logger.warning(
            "[run_id=%s] Resuming with pipeline '%s' but the run was recorded against '%s' — "
            "plan rehydration will skip any step whose name does not line up",
            run.run_id,
            pipeline.name,
            run.pipeline_name,
        )

    steps = pipeline.steps
    for idx, record in enumerate(run.step_records):
        if idx >= len(steps):
            logger.warning(
                "[run_id=%s] Stored step record '%s' (index %d) has no definition in the "
                "current pipeline (%d steps) — skipping rehydration for it",
                run.run_id,
                record.step_name,
                idx,
                len(steps),
            )
            continue

        step_def = steps[idx]
        if record.step_name != step_def.name:
            logger.warning(
                "[run_id=%s] Stored step record '%s' does not match pipeline step '%s' at "
                "index %d — the pipeline was edited between sessions; skipping rehydration "
                "for it",
                run.run_id,
                record.step_name,
                step_def.name,
                idx,
            )
            continue

        # A loop_back resets its target record to result=None; guard before touching .status.
        if record.result is None:
            continue

        hydrate_plan_context(step_def, record.result, context)
