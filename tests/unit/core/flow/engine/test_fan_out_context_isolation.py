# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Concurrent sub-runs must not observe each other's run identity (`TECH-014`).

`OrchestrateComponentsHandler` builds one `PipelineRunner` per DAG component and hands each of
them **the same `RunContext` object** (`handlers/decompose.py`, `context.run.pipeline_runner._context`),
then dispatches them as concurrent `asyncio` tasks. `PipelineRunner._execute_loop` rebinds
`self._context.run` on **every step** with that run's `run_id`, `pipeline_runner` and
`step_records`. Shared object plus per-step rebind plus real concurrency means a sub-run can read
another sub-run's identity, so lineage and telemetry events are attributed to the wrong sub-run.

**Why no existing test catches this.** Every fan-out test runs its sub-runs to completion one at a
time, or asserts on the aggregate result rather than on which run each observation belonged to.
The defect is invisible unless two runs are genuinely in flight *and* the assertion is per-run
attribution — which is what these tests do.

`TECH-006` SF-02 narrowed the failure mode without closing it: collapsing the three racing fields
into one frozen `RunHandle` made the rebind a single atomic swap, so a reader can no longer see a
*torn* handle with one run's id and another's records. It can still see the wrong handle entirely.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest

from specweaver.core.flow.engine.models import (
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.handlers.run_context import RunContext

if TYPE_CHECKING:
    from pathlib import Path


class RunIdObservingHandler:
    """Records which run identity it saw, and whether that identity held across an await.

    The `await` is the whole point and is not artificial: every real handler awaits something —
    an LLM call, a subprocess, a file read — and that is precisely where the event loop can hand
    control to a sibling sub-run whose runner then rebinds the shared context.
    """

    def __init__(self) -> None:
        # (label, run_id before the await, run_id after it)
        self.observations: list[tuple[str, str | None, str | None]] = []

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        label = step.params.get("component", "?")
        before = context.run.run_id
        await asyncio.sleep(0)
        after = context.run.run_id
        self.observations.append((label, before, after))
        return StepResult(
            status=StepStatus.PASSED,
            output={"run_id": after},
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:01Z",
        )


def _labelled_pipeline(label: str, step_count: int = 3) -> PipelineDefinition:
    """A pipeline whose every step carries the sub-run's name, the way fan-out builds them."""
    return PipelineDefinition(
        name=f"auto_{label}",
        steps=[
            PipelineStep(
                name=f"{label}_step_{i}",
                action=StepAction.VALIDATE,
                target=StepTarget.SPEC,
                params={"component": label},
            )
            for i in range(step_count)
        ],
    )


def _shared_context(tmp_path: Path) -> RunContext:
    return RunContext(project_path=tmp_path, spec_path=tmp_path / "specs" / "test.md")


async def _run_fan_out(
    tmp_path: Path, labels: list[str]
) -> tuple[RunIdObservingHandler, list[Any]]:
    """Reproduce the fan-out shape: N runners over ONE context, dispatched concurrently.

    `parent_run_id` is passed because every real fan-out site passes it — it is what marks a
    runner as a sub-run, and therefore what the fix keys on. A repro that omitted it would not be
    reproducing fan-out.
    """
    handler = RunIdObservingHandler()
    registry = StepHandlerRegistry()
    registry.register(StepAction.VALIDATE, StepTarget.SPEC, handler)

    context = _shared_context(tmp_path)
    runners = [
        PipelineRunner(_labelled_pipeline(label), context, registry=registry) for label in labels
    ]

    results = await asyncio.gather(*(r.run(parent_run_id="parent-run") for r in runners))
    return handler, list(results)


@pytest.mark.asyncio
async def test_a_sub_run_never_observes_another_sub_runs_run_id(tmp_path: Path) -> None:
    """Each component's steps must all report that component's own run — the core `TECH-014` claim.

    Concretely: group every observation by the component whose step produced it. Each group must
    contain exactly one distinct `run_id`, and the groups must not share one. Anything else means
    lineage for component A is being recorded against component B's run.
    """
    handler, results = await _run_fan_out(tmp_path, ["alpha", "beta", "gamma"])

    by_label: dict[str, set[str | None]] = {}
    for label, _before, after in handler.observations:
        by_label.setdefault(label, set()).add(after)

    muddled = {label: ids for label, ids in by_label.items() if len(ids) != 1}
    assert not muddled, (
        f"a component's steps observed more than one run_id: {muddled} — "
        "lineage and telemetry are attributed to the wrong sub-run"
    )

    observed = [next(iter(ids)) for ids in by_label.values()]
    assert len(set(observed)) == len(observed), (
        f"two components observed the SAME run_id: {observed} — they are sharing one identity"
    )

    actual = {r.run_id for r in results}
    assert set(observed) == actual, (
        f"observed run_ids {set(observed)} are not the runs that actually executed {actual}"
    )


@pytest.mark.asyncio
async def test_a_run_id_does_not_change_underneath_a_running_step(tmp_path: Path) -> None:
    """The identity a handler reads must still be true after it awaits.

    Narrower than the test above and worth pinning separately: it isolates the *mechanism* —
    a sibling rebinding the shared context mid-step — from the *consequence*. A fix that
    partitioned identity but still let it move under a live step would pass the first test and
    fail this one.
    """
    handler, _results = await _run_fan_out(tmp_path, ["alpha", "beta", "gamma"])

    shifted = [(lbl, b, a) for lbl, b, a in handler.observations if b != a]

    assert not shifted, (
        f"run_id changed while a step was executing: {shifted} — "
        "a sibling sub-run rebound the shared RunContext mid-step"
    )


@pytest.mark.asyncio
async def test_the_handler_actually_ran_for_every_component(tmp_path: Path) -> None:
    """Guards the two tests above against passing vacuously.

    Both assert over `handler.observations`; if the runner silently skipped the steps, or the
    registry lookup missed, those collections would be empty and the assertions would hold while
    proving nothing. This is `test-quality.md` pattern 8 — subject never located.
    """
    handler, results = await _run_fan_out(tmp_path, ["alpha", "beta", "gamma"])

    assert len(results) == 3
    assert len(handler.observations) == 9, "expected 3 components x 3 steps to have executed"
    assert {lbl for lbl, _b, _a in handler.observations} == {"alpha", "beta", "gamma"}


@pytest.mark.asyncio
async def test_a_top_level_run_still_writes_to_the_caller_s_own_context(tmp_path: Path) -> None:
    """The other half of the fix: a top-level run must NOT be given a copy.

    Isolation keys on `parent_run_id`, which is exactly "I am a sub-run" — all four fan-out sites
    pass it, no top-level caller does. Fifteen construction sites (the API and eight CLI
    entrypoints) hand the runner a context and then read their own reference back, so copying
    there would silently strip `seed_dal_level` / `setup_sandbox_caches` / plan hydration from
    under them. This pins that the discriminator is load-bearing in both directions.
    """
    handler = RunIdObservingHandler()
    registry = StepHandlerRegistry()
    registry.register(StepAction.VALIDATE, StepTarget.SPEC, handler)

    context = _shared_context(tmp_path)
    runner = PipelineRunner(_labelled_pipeline("solo", step_count=1), context, registry=registry)

    result = await runner.run()

    assert runner._context is context, (
        "a top-level run was given a copy — the caller's own context no longer sees the run"
    )
    assert context.run.run_id == result.run_id


# ---------------------------------------------------------------------------
# The one thing that must NOT be isolated
# ---------------------------------------------------------------------------


def test_the_gate_evaluator_keeps_the_context_it_was_built_with(tmp_path: Path) -> None:
    """`GateEvaluator` holds the context from `__init__`, and that is correct — do not "fix" it.

    It looks like a stale-reference bug: the runner may replace `self._context` — with a sub-run
    copy under `TECH-014`, or with the ephemeral-worktree context under `C-EXEC-06` — while the
    evaluator keeps pointing at the original. The obvious tidy-up is to re-point it at
    `runner._context`.

    **That tidy-up would silently break the RESERVE gate**, which is a *cross-pipeline mutex*
    keyed `pipeline:<name>`. It resolves its lock database as
    `context.project_path / ".specweaver" / "reservations.db"`, so contention exists only while
    every contender resolves the SAME path. `C-EXEC-06` rewrites `project_path` to a per-run
    worktree; an evaluator following that would hand each run a private database, every acquire
    would succeed, and the mutex would be gone — with no test failing and nothing logged.

    The companion test below demonstrates that failure mode rather than asserting it.
    """
    registry = StepHandlerRegistry()
    registry.register(StepAction.VALIDATE, StepTarget.SPEC, RunIdObservingHandler())

    context = _shared_context(tmp_path)
    runner = PipelineRunner(_labelled_pipeline("solo", step_count=1), context, registry=registry)

    # Exactly what `runner_utils` does for a C-EXEC-06 session: point the run at a worktree.
    worktree_context = context.model_copy()
    worktree_context.project_path = tmp_path / ".worktrees" / "wt-1"
    runner._context = worktree_context

    assert runner._gate_evaluator._context is context, (
        "the gate evaluator followed the runner's swapped context — RESERVE would resolve its "
        "lock database inside the per-run worktree and stop being a mutex"
    )
    assert runner._gate_evaluator._context.project_path == tmp_path


def test_a_per_run_lock_database_would_destroy_the_reserve_mutex(tmp_path: Path) -> None:
    """Why the test above matters, shown rather than claimed.

    Two contenders on one database: the second is refused. The same two contenders on separate
    databases — which is what a per-worktree `project_path` produces — both succeed. That second
    outcome is the silent failure the shared context prevents.
    """
    from specweaver.core.flow.engine.reservation import SQLiteReservationSystem

    shared = tmp_path / ".specweaver" / "reservations.db"

    assert SQLiteReservationSystem(shared).acquire("pipeline:build", "run-a") is True
    assert SQLiteReservationSystem(shared).acquire("pipeline:build", "run-b") is False, (
        "a shared reservation database must serialise contenders"
    )

    per_worktree_a = SQLiteReservationSystem(tmp_path / "wt-a" / ".specweaver" / "reservations.db")
    per_worktree_b = SQLiteReservationSystem(tmp_path / "wt-b" / ".specweaver" / "reservations.db")

    assert per_worktree_a.acquire("pipeline:build", "run-a") is True
    assert per_worktree_b.acquire("pipeline:build", "run-b") is True, (
        "sanity: separate databases do NOT contend — this is the failure mode, not the fix"
    )
