# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Executing one step, and deciding what the loop does next.

The per-step body, kept out of `PipelineRunner._execute_loop`. Inlined there it is 365 lines —
around 60% of `runner.py` — in a single method at cognitive complexity 50 against a ceiling of 15,
which only a `# noqa: C901` makes tolerable. The file-size threshold is a proxy, but such a
suppression is a direct admission the method is past the project's own
bar.

The seams were already visible, because three modules had been carved out of this same loop before
(`hydration.py`, `approval.py`, `staleness.py`) — each time under pressure from a feature that
needed room. This split follows the same convention: free functions taking the runner first, so the
loop keeps `self._persist` / `_log` / `_emit` as its own concern.

**Strictly behaviour-preserving.** Every branch here was moved, not rewritten, and the module is
covered by the pre-existing suite — 44 branches, zero partial — which is what made the move safe to
attempt at all.

The one duplication that *was* collapsed is `fail_run`: four sites (missing handler, gate `stop`,
ungated failure, router error) each open-coded the identical persist → log → emit `step_failed` →
emit `run_failed` → return sequence. Collapsing them is why the extraction shrinks the loop rather
than merely relocating it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, cast

from specweaver.commons.timestamps import now_iso as _now_iso
from specweaver.core.flow.engine.approval import try_approve_parked_step
from specweaver.core.flow.engine.hydration import hydrate_plan_context
from specweaver.core.flow.engine.isolation import resolve_should_isolate
from specweaver.core.flow.engine.models import StepAction, StepTarget
from specweaver.core.flow.engine.routers import resolve_route_target
from specweaver.core.flow.engine.staleness import try_staleness_bypass
from specweaver.core.flow.engine.state import StepResult, StepStatus

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import GateDefinition, PipelineStep
    from specweaver.core.flow.engine.state import PipelineRun

logger = logging.getLogger(__name__)


@dataclass
class LoopState:
    """The bookkeeping `_execute_loop` carries across iterations.

    Bundled rather than passed as three parameters because two of them are *written* by the step
    body — `route_jumps` by the router bound, `approve_parked` by its one-shot consumption — and
    threading writes back through a tuple return was what made the old signature unreadable.

    `attempts` is per-step retry counts, and is also mutated by `GateEvaluator.evaluate`.
    """

    attempts: dict[int, int] = field(default_factory=dict)
    route_jumps: int = 0
    approve_parked: bool = False

    @classmethod
    def for_run(cls, run: PipelineRun, *, approve_parked: bool = False) -> LoopState:
        """Start the loop with the retry budget each step has **already** spent.

        `attempts` starting empty on every `_execute_loop` entry would hand each step a full fresh
        budget on every `sw resume`, since `resume()` re-enters that loop — making
        `max_retries: 3` a bound per session rather than per step.

        `StepRecord.attempt` already carried the durable count: it is written by the gate and it
        round-trips through the store. Only the read back was missing.

        The two counters are offset by one and that is not arbitrary — `attempt` is the 1-based
        number of the attempt about to be made (so a fresh record reads 1), while `attempts` counts
        retries already spent. A fresh run therefore seeds to an empty dict and behaves exactly as
        before; only a resumed one carries anything.
        """
        return cls(
            attempts={
                index: record.attempt - 1
                for index, record in enumerate(run.step_records)
                if record.attempt > 1
            },
            approve_parked=approve_parked,
        )


class LoopAction(Enum):
    """What `_execute_loop` should do once a step's outcome is known.

    Named rather than encoded as a bool pair because the loop has three distinct continuations and
    two of them are easy to confuse: `CONTINUE` re-enters **without** advancing `current_step`
    (retry and loop-back both rely on that), while `PROCEED` falls through to the advance/route
    block that does move it.
    """

    RETURN = "return"
    CONTINUE = "continue"
    PROCEED = "proceed"


def _step_event(
    runner: Any, event: str, step_def: PipelineStep, step_idx: int, total: int, **extra: Any
) -> None:
    """Emit a step-scoped event with the four fields every one of them carries."""
    runner._emit(
        event,
        step_idx=step_idx,
        step_name=step_def.name,
        step_def=step_def,
        total_steps=total,
        **extra,
    )


def fail_run(
    runner: Any,
    run: PipelineRun,
    step_def: PipelineStep,
    step_idx: int,
    total: int,
    result: StepResult,
) -> PipelineRun:
    """Terminate the run on a failed step: persist, log, emit both events, hand back the run.

    Four call sites open-coded this identically. They differ only in whether the caller has
    already recorded the failure on the run — so that stays the caller's job, and this owns the
    reporting that must be the same everywhere.
    """
    runner._persist(run)
    runner._log(run, "step_failed", step_def.name)
    _step_event(runner, "step_failed", step_def, step_idx, total, result=result)
    runner._emit("run_failed", run=run)
    return run


def fail_missing_handler(
    runner: Any, run: PipelineRun, step_def: PipelineStep, step_idx: int, total: int
) -> PipelineRun:
    """No handler is registered for this step's action+target — the run cannot continue."""
    error_msg = f"No handler registered for {step_def.action.value}+{step_def.target.value}"
    logger.error(
        "[run_id=%s] Step %d/%d '%s': %s", run.run_id, step_idx + 1, total, step_def.name, error_msg
    )
    result = StepResult(
        status=StepStatus.ERROR,
        error_message=error_msg,
        started_at=_now_iso(),
        completed_at=_now_iso(),
    )
    run.fail_current_step(result)
    return fail_run(runner, run, step_def, step_idx, total, result)


def announce_step_start(
    runner: Any,
    run: PipelineRun,
    step_def: PipelineStep,
    step_idx: int,
    total: int,
    handler: Any,
) -> None:
    """Mark the step running and tell everyone about it."""
    run.mark_step_running()
    runner._persist(run)
    runner._log(run, "step_started", step_def.name)
    logger.info(
        "[run_id=%s] Step %d/%d '%s' (%s+%s) — executing via %s",
        run.run_id,
        step_idx + 1,
        total,
        step_def.name,
        step_def.action.value,
        step_def.target.value,
        type(handler).__name__,
    )
    _step_event(runner, "step_started", step_def, step_idx, total)


async def execute_step(
    runner: Any, handler: Any, step_def: PipelineStep, run: PipelineRun
) -> StepResult:
    """Run the handler, in a sandbox when policy says so, converting any escape into an ERROR."""
    try:
        # Inject flow state for downstream tracking.
        runner._context.run = runner._context.run.model_copy(
            update={
                "run_id": run.run_id,
                "pipeline_runner": runner,
                "step_records": [r.model_dump() for r in run.step_records],
            }
        )

        # Tri-state isolation gate (see resolve_should_isolate).
        # Inside an active session, ALL steps already run in the one session worktree —
        # unconditionally bypass per-step isolation (even explicit use_worktree=True) so no nested
        # worktree is created.
        if not getattr(runner, "_session_active", False) and resolve_should_isolate(
            step_def, runner._context
        ):
            from specweaver.core.flow.engine.sandboxed_execution import execute_in_sandbox

            return await execute_in_sandbox(runner, handler, step_def, run, logger)
        return cast("StepResult", await handler.execute(step_def, runner._context))
    except Exception as exc:
        logger.exception(
            "[run_id=%s] Step '%s' raised unhandled exception", run.run_id, step_def.name
        )
        return StepResult(
            status=StepStatus.ERROR,
            error_message=str(exc),
            started_at=_now_iso(),
            completed_at=_now_iso(),
        )


def park_run(
    runner: Any,
    run: PipelineRun,
    step_def: PipelineStep,
    step_idx: int,
    total: int,
    result: StepResult,
) -> PipelineRun:
    """A step asked for human input — park the run where it stands."""
    logger.info(
        "[run_id=%s] Step '%s' waiting for user input — parking run", run.run_id, step_def.name
    )
    run.park_current_step(result)
    runner._persist(run)
    runner._log(run, "run_parked", step_def.name)
    _step_event(runner, "step_parked", step_def, step_idx, total, result=result)
    runner._emit("run_parked", run=run, step_name=step_def.name)
    return run


def apply_gate(
    runner: Any,
    run: PipelineRun,
    gate: GateDefinition,
    step_def: PipelineStep,
    step_idx: int,
    total: int,
    result: StepResult,
    attempts: dict[int, int],
) -> LoopAction:
    """Evaluate this step's gate and turn the verdict into the loop's next move.

    The gate is a parameter rather than re-read from `step_def`, so "there IS a gate" is stated in
    the signature instead of left as an unwritten obligation on the caller.
    """
    logger.debug(
        "[run_id=%s] Evaluating gate on step '%s' (type=%s, condition=%s)",
        run.run_id,
        step_def.name,
        gate.type.value,
        gate.condition.value,
    )
    verdict = runner._gate_evaluator.evaluate(gate, result, step_def, run, attempts)
    logger.info(
        "[run_id=%s] Gate verdict for step '%s': %s (result_status=%s)",
        run.run_id,
        step_def.name,
        verdict,
        result.status.value,
    )
    _step_event(runner, "gate_result", step_def, step_idx, total, result=result, verdict=verdict)

    if verdict == "park":
        logger.info(
            "[run_id=%s] HITL gate on '%s' — parking for human review", run.run_id, step_def.name
        )
        runner._persist(run)
        runner._log(run, "gate_hitl_park", step_def.name)
        runner._emit("run_parked", run=run, step_name=step_def.name)
        return LoopAction.RETURN

    if verdict == "stop":
        logger.error(
            "[run_id=%s] Gate on '%s' failed — stopping pipeline", run.run_id, step_def.name
        )
        fail_run(runner, run, step_def, step_idx, total, result)
        return LoopAction.RETURN

    if verdict == "retry":
        logger.info(
            "[run_id=%s] Retrying step '%s' (attempt %d)",
            run.run_id,
            step_def.name,
            attempts.get(run.current_step, 0),
        )
        runner._persist(run)
        runner._log(run, "step_retry", step_def.name)
        return LoopAction.CONTINUE  # re-execute same step

    if verdict == "loop_back":
        logger.info(
            "[run_id=%s] Looping back from '%s' to '%s'",
            run.run_id,
            step_def.name,
            gate.loop_target or "?",
        )
        runner._gate_evaluator.inject_feedback(
            runner._context, step_def.name, gate.loop_target or "", result
        )
        runner._persist(run)
        runner._log(run, "step_loop_back", step_def.name)
        return LoopAction.CONTINUE  # current_step was moved

    runner._log(run, "gate_passed", step_def.name)
    return LoopAction.PROCEED


def failed_without_a_gate(
    runner: Any,
    run: PipelineRun,
    step_def: PipelineStep,
    step_idx: int,
    total: int,
    result: StepResult,
) -> bool:
    """Backwards compatibility: with no gate, a failed or errored step stops the run."""
    if result.status not in (StepStatus.FAILED, StepStatus.ERROR):
        return False

    logger.error(
        "[run_id=%s] Step '%s' %s: %s",
        run.run_id,
        step_def.name,
        result.status.value,
        result.error_message or "no error message",
    )
    run.fail_current_step(result)
    fail_run(runner, run, step_def, step_idx, total, result)
    return True


def advance_step(
    runner: Any,
    run: PipelineRun,
    step_def: PipelineStep,
    step_idx: int,
    total: int,
    result: StepResult,
    route_jumps: int,
) -> tuple[LoopAction, int]:
    """Record the step as done — routing to a target when the step declares a router.

    Returns the loop's next move alongside the running jump count, which the router bounds.
    """
    router = step_def.router
    if router is not None:
        target_idx, route_error, route_jumps = resolve_route_target(
            runner._router_evaluator,
            router,
            result.output,
            runner._pipeline,
            run.current_step,
            route_jumps,
        )
        if route_error is not None or target_idx is None:
            error_msg = route_error or "Router resolution failed"
            logger.error("[run_id=%s] %s", run.run_id, error_msg)
            run.fail_current_step(
                StepResult(
                    status=StepStatus.ERROR,
                    error_message=error_msg,
                    started_at=_now_iso(),
                    completed_at=_now_iso(),
                )
            )
            runner._persist(run)
            runner._emit("run_failed", run=run)
            return LoopAction.RETURN, route_jumps

        target_step_name = runner._pipeline.steps[target_idx].name
        logger.info(
            "[run_id=%s] Router resolved target '%s' (index %d). Routing.",
            run.run_id,
            target_step_name,
            target_idx,
        )
        runner._emit(
            "step_routed",
            step_idx=step_idx,
            step_name=step_def.name,
            target_step=target_step_name,
            target_idx=target_idx,
            run=run,
        )
        runner._log(run, "step_routed", step_def.name)
        run.route_to_step(result, target_idx)
    else:
        run.complete_current_step(result)

    run.updated_at = _now_iso()
    runner._persist(run)
    if router is None:
        runner._log(run, "step_completed", step_def.name)
    _step_event(runner, "step_completed", step_def, step_idx, total, result=result)
    return LoopAction.PROCEED, route_jumps


#: `validate` targets whose payload is rule results. `StepTarget.TESTS` is `run_tests`, whose
#: exports are `passed`/`failed`/`total` with no `rule_id` — persisting it would make
#: `flow_validation_results` mean two different things (plan D-5).
_RULE_RESULT_TARGETS = (StepTarget.SPEC, StepTarget.CODE)


def persist_validation_results(
    runner: Any,
    run: PipelineRun,
    step_def: PipelineStep,
    step_idx: int,
    result: StepResult,
) -> None:
    """Append a validate step's rule results to the state DB.

    **Called before `resolve_outcome`, deliberately.** The obvious home is the advance join point
    beside `hydrate_plan_context`, but that line is reached only on
    `PROCEED`. A validate step that fails and loops back returns `CONTINUE`; one that fails gateless
    or parks returns `RETURN`. Writing there would persist passing runs and drop every failure,
    which is the half that matters: those findings trigger the loop-back and are what `FR-3`
    replays. Hydration *should* only run on advance — a failed step has no plan to hydrate — so the
    symmetry was misleading.

    Never raises (plan D-7). A pipeline must not die because an audit row could not be written;
    the failure is logged with the run id and the run continues.
    """
    if runner._store is None:
        return
    if step_def.action != StepAction.VALIDATE or step_def.target not in _RULE_RESULT_TARGETS:
        return

    results = (result.output or {}).get("results")
    if not isinstance(results, list):
        return

    # The DURABLE attempt, not the in-memory counter: the retry budget lives on the step record
    # precisely because the live one restarts at zero on resume.
    record = run.step_records[step_idx] if step_idx < len(run.step_records) else None
    attempt = getattr(record, "attempt", 1) or 1

    try:
        runner._store.save_validation_results(
            run.run_id, step_def.name, attempt=attempt, results=results
        )
    except Exception:
        logger.warning(
            "[run_id=%s] Could not persist validation results for step '%s' — the run continues",
            run.run_id,
            step_def.name,
            exc_info=True,
        )


def resolve_outcome(
    runner: Any,
    run: PipelineRun,
    state: LoopState,
    step_def: PipelineStep,
    step_idx: int,
    total: int,
    result: StepResult,
) -> LoopAction:
    """Turn a finished step's result into the loop's next move, gate or no gate."""
    if result.status == StepStatus.WAITING_FOR_INPUT:
        park_run(runner, run, step_def, step_idx, total, result)
        return LoopAction.RETURN

    gate = step_def.gate
    if gate is not None:
        return apply_gate(runner, run, gate, step_def, step_idx, total, result, state.attempts)

    if failed_without_a_gate(runner, run, step_def, step_idx, total, result):
        return LoopAction.RETURN

    return LoopAction.PROCEED


async def run_one_step(
    runner: Any,
    run: PipelineRun,
    state: LoopState,
    step_def: PipelineStep,
    step_idx: int,
    total: int,
) -> LoopAction:
    """One full iteration of the pipeline loop: approve, dispatch, execute, judge, advance.

    The per-step body as a collaborator, leaving `_execute_loop` as iteration and bookkeeping.
    `CONTINUE` and `PROCEED` both mean "next iteration" to the caller;
    the distinction is real only in here, where it decides whether `current_step` moves.
    """
    # MUST stay at the very top. Two later blocks would otherwise destroy the evidence this
    # decision reads:
    #   * the staleness bypass below can complete the step as SKIPPED and continue, discarding the
    #     human's approval and the stored result;
    #   * mark_step_running() overwrites record.status WAITING_FOR_INPUT -> RUNNING.
    # One-shot: consumed on the first iteration whether or not it approves, so a stale
    # WAITING_FOR_INPUT record further down the pipeline can never be auto-approved.
    if state.approve_parked:
        state.approve_parked = False
        if try_approve_parked_step(runner, run, step_def, step_idx, total):
            return LoopAction.CONTINUE

    handler = runner._registry.get(step_def.action, step_def.target)
    if handler is None:
        fail_missing_handler(runner, run, step_def, step_idx, total)
        return LoopAction.RETURN

    if try_staleness_bypass(runner, run, step_def, step_idx, total):
        return LoopAction.CONTINUE

    announce_step_start(runner, run, step_def, step_idx, total, handler)
    result = await execute_step(runner, handler, step_def, run)

    # BEFORE resolve_outcome, so a failing validate step's findings are
    # persisted too — resolve_outcome sends loop-backs and gateless failures down paths that never
    # reach the advance join point below.
    persist_validation_results(runner, run, step_def, step_idx, result)

    action = resolve_outcome(runner, run, state, step_def, step_idx, total, result)
    if action is not LoopAction.PROCEED:
        return action

    # The join point BOTH advance paths reach — the gate's "advance" fall-through
    # and the no-gate branch. Hydrating inside the gate block would silently skip every gateless
    # plan/decompose step.
    hydrate_plan_context(step_def, result, runner._context)
    logger.debug(
        "[run_id=%s] Step '%s' completed with status=%s",
        run.run_id,
        step_def.name,
        result.status.value,
    )

    action, state.route_jumps = advance_step(
        runner, run, step_def, step_idx, total, result, state.route_jumps
    )
    return action
