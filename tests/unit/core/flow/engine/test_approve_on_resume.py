# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for HITL approve-on-resume — INT-US-21 SF-01 CB-4 (FR-4, AD-2).

`GateEvaluator` parks HITL gates unconditionally and `resume()` only flipped the status back to
RUNNING, so the loop re-executed the step and the gate re-parked — forever. Resuming a
gate-parked step now *is* the approval.

The discriminator is entirely in persisted state (AD-2), and the negative cases matter more
than the happy one — approving the wrong park flavour would skip a step that never ran:

| flavour              | record.status      | result.status      | verdict     |
|----------------------|--------------------|--------------------|-------------|
| gate-park (HITL)     | WAITING_FOR_INPUT  | PASSED             | **APPROVE** |
| gate-park on failure | WAITING_FOR_INPUT  | FAILED / ERROR     | re-execute  |
| handler-park         | WAITING_FOR_INPUT  | WAITING_FOR_INPUT  | re-execute  |
| RESERVE-park         | WAITING_FOR_INPUT  | PENDING            | re-execute  |
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest

from specweaver.core.flow.engine.models import (
    GateCondition,
    GateDefinition,
    GateType,
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus, StepResult, StepStatus
from specweaver.core.flow.engine.store import StateStore
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.registry import StepHandlerRegistry

if TYPE_CHECKING:
    from pathlib import Path


class _Counting:
    """Records how many times it executed and returns a fixed status."""

    def __init__(self, status: StepStatus = StepStatus.PASSED, **output: Any) -> None:
        self.calls = 0
        self._status = status
        self._output = output

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        self.calls += 1
        return StepResult(
            status=self._status,
            output=dict(self._output),
            started_at="1",
            completed_at="2",
        )


def _step(
    action: StepAction,
    target: StepTarget,
    name: str,
    gate: GateDefinition | None = None,
    **params: Any,
) -> PipelineStep:
    step = PipelineStep(name=name, action=action, target=target, params=params)
    step.gate = gate
    return step


def _hitl() -> GateDefinition:
    return GateDefinition(type=GateType.HITL, condition=GateCondition.COMPLETED)


def _auto() -> GateDefinition:
    return GateDefinition(type=GateType.AUTO, condition=GateCondition.ALL_PASSED)


def _stale_target_step() -> PipelineStep:
    """A HITL-gated step whose params carry a `target`, so the staleness bypass can consider it."""
    step = PipelineStep(
        name="decompose",
        action=StepAction.DECOMPOSE,
        target=StepTarget.FEATURE,
        params={"target": "src/auth.py"},
    )
    step.gate = _hitl()
    return step


def _ctx(tmp_path: Path) -> RunContext:
    return RunContext(project_path=tmp_path, spec_path=tmp_path / "x_feature_spec.md")


def _registry(**by_action: Any) -> StepHandlerRegistry:
    reg = StepHandlerRegistry()
    for key, handler in by_action.items():
        action, target = key.split("__")
        reg.register(StepAction(action), StepTarget(target), handler)
    return reg


def _park_then_resume(
    tmp_path: Path,
    pipeline: PipelineDefinition,
    first: _Counting,
    second: _Counting,
    *,
    action: str = "decompose",
    target: str = "feature",
    events: list[tuple[str, dict]] | None = None,
) -> tuple[Any, Any]:
    """Session 1 with `first`, session 2 (resume) with `second`. Returns (run1, run2)."""
    store = StateStore(tmp_path / "state.db")
    key = f"{action}__{target}"

    run1 = asyncio.run(
        PipelineRunner(
            pipeline, _ctx(tmp_path), registry=_registry(**{key: first}), store=store
        ).run()
    )

    def on_event(event: str, **kwargs: Any) -> None:
        if events is not None:
            events.append((event, kwargs))

    run2 = asyncio.run(
        PipelineRunner(
            pipeline,
            _ctx(tmp_path),
            registry=_registry(**{key: second}),
            store=store,
            on_event=on_event,
        ).resume(run1.run_id)
    )
    return run1, run2


# ---------------------------------------------------------------------------
# Happy path — the defect this closes
# ---------------------------------------------------------------------------


class TestApproveOnResume:
    def test_resuming_a_gate_park_advances_without_re_executing(self, tmp_path: Path) -> None:
        """The whole point: resume = approval. The handler must NOT run again."""
        pipeline = PipelineDefinition(
            name="p",
            steps=[_step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose", _hitl())],
        )
        first, second = _Counting(components=[]), _Counting(components=[])

        run1, run2 = _park_then_resume(tmp_path, pipeline, first, second)

        assert run1.status == RunStatus.PARKED
        assert first.calls == 1
        assert second.calls == 0, "the approved step was re-executed instead of approved"
        assert run2.status == RunStatus.COMPLETED
        assert run2.current_step == 1

    def test_the_stored_result_is_what_completes_the_step(self, tmp_path: Path) -> None:
        pipeline = PipelineDefinition(
            name="p",
            steps=[_step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose", _hitl())],
        )
        first = _Counting(components=[{"name": "auth"}])
        _, run2 = _park_then_resume(tmp_path, pipeline, first, _Counting())

        record = run2.step_records[0]
        assert record.status == StepStatus.PASSED
        assert record.result.output == {"components": [{"name": "auth"}]}

    def test_approval_logs_an_audit_event(self, tmp_path: Path) -> None:
        pipeline = PipelineDefinition(
            name="p",
            steps=[_step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose", _hitl())],
        )
        store = StateStore(tmp_path / "state.db")
        run1 = asyncio.run(
            PipelineRunner(
                pipeline,
                _ctx(tmp_path),
                registry=_registry(decompose__feature=_Counting(components=[])),
                store=store,
            ).run()
        )
        asyncio.run(
            PipelineRunner(
                pipeline,
                _ctx(tmp_path),
                registry=_registry(decompose__feature=_Counting()),
                store=store,
            ).resume(run1.run_id)
        )

        events = [e["event"] for e in store.get_audit_log(run1.run_id)]
        assert "gate_approved_on_resume" in events

    def test_approval_emits_step_completed_with_a_marker(self, tmp_path: Path) -> None:
        """NFR-7: a step completed with no handler execution must still be observable."""
        pipeline = PipelineDefinition(
            name="p",
            steps=[_step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose", _hitl())],
        )
        events: list[tuple[str, dict]] = []

        _park_then_resume(tmp_path, pipeline, _Counting(components=[]), _Counting(), events=events)

        completed = [kw for name, kw in events if name == "step_completed"]
        assert completed, "no step_completed emitted for the approved step"
        assert any(kw.get("approved_on_resume") for kw in completed)

    def test_approval_hydrates_the_plan_context(self, tmp_path: Path) -> None:
        """FR-2 must fire on the approval path too — it never executes a handler."""
        pipeline = PipelineDefinition(
            name="p",
            steps=[
                _step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose", _hitl()),
                _step(StepAction.VALIDATE, StepTarget.SPEC, "downstream"),
            ],
        )
        store = StateStore(tmp_path / "state.db")
        run1 = asyncio.run(
            PipelineRunner(
                pipeline,
                _ctx(tmp_path),
                registry=_registry(decompose__feature=_Counting(components=[{"name": "auth"}])),
                store=store,
            ).run()
        )

        seen: dict[str, Any] = {}

        class _Observe:
            async def execute(self, step, context):
                seen["decomposition"] = context.plan_context.decomposition
                return StepResult(
                    status=StepStatus.PASSED, output={}, started_at="1", completed_at="2"
                )

        reg = StepHandlerRegistry()
        reg.register(StepAction.DECOMPOSE, StepTarget.FEATURE, _Counting())
        reg.register(StepAction.VALIDATE, StepTarget.SPEC, _Observe())
        asyncio.run(
            PipelineRunner(pipeline, _ctx(tmp_path), registry=reg, store=store).resume(run1.run_id)
        )

        assert seen["decomposition"] is not None

    def test_approval_at_the_last_step_completes_the_run(self, tmp_path: Path) -> None:
        pipeline = PipelineDefinition(
            name="p",
            steps=[_step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose", _hitl())],
        )
        _, run2 = _park_then_resume(tmp_path, pipeline, _Counting(components=[]), _Counting())

        assert run2.status == RunStatus.COMPLETED


# ---------------------------------------------------------------------------
# Hostile — the park flavours that must NOT be approved
# ---------------------------------------------------------------------------


class TestApprovalNegatives:
    def test_handler_park_re_executes(self, tmp_path: Path) -> None:
        """Stored result WAITING_FOR_INPUT: the step never produced a verdict."""
        pipeline = PipelineDefinition(
            name="p",
            steps=[_step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose", _hitl())],
        )
        first = _Counting(StepStatus.WAITING_FOR_INPUT)
        second = _Counting(StepStatus.PASSED, components=[])

        run1, _ = _park_then_resume(tmp_path, pipeline, first, second)

        assert run1.step_records[0].result.status == StepStatus.WAITING_FOR_INPUT
        assert second.calls == 1, "a handler-park was wrongly treated as an approval"

    def test_hitl_gate_on_a_failed_result_re_executes(self, tmp_path: Path) -> None:
        """The human resumed a failed step — that is a retry, not an approval."""
        pipeline = PipelineDefinition(
            name="p",
            steps=[_step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose", _hitl())],
        )
        first = _Counting(StepStatus.FAILED)
        second = _Counting(StepStatus.PASSED, components=[])

        run1, _ = _park_then_resume(tmp_path, pipeline, first, second)

        assert run1.status == RunStatus.PARKED  # HITL parks regardless of result
        assert run1.step_records[0].result.status == StepStatus.FAILED
        assert second.calls == 1, "a failed gate-park was wrongly approved"

    def test_reserve_park_re_executes(self, tmp_path: Path) -> None:
        """RESERVE collision overwrites the result to PENDING before parking."""
        pipeline = PipelineDefinition(
            name="p",
            steps=[
                _step(
                    StepAction.DECOMPOSE,
                    StepTarget.FEATURE,
                    "decompose",
                    GateDefinition(type=GateType.RESERVE, condition=GateCondition.COMPLETED),
                )
            ],
        )
        store = StateStore(tmp_path / "state.db")
        # Pre-acquire the reservation so the gate collides and parks.
        from specweaver.core.flow.engine.reservation import SQLiteReservationSystem

        db = tmp_path / ".specweaver" / "reservations.db"
        db.parent.mkdir(parents=True, exist_ok=True)
        SQLiteReservationSystem(db).acquire(
            resource_id="pipeline:default_pipeline", run_id="someone-else", timeout_seconds=3600
        )

        run1 = asyncio.run(
            PipelineRunner(
                pipeline,
                _ctx(tmp_path),
                registry=_registry(decompose__feature=_Counting(components=[])),
                store=store,
            ).run()
        )
        if run1.status != RunStatus.PARKED:
            pytest.skip("reservation did not collide in this environment")
        assert run1.step_records[0].result.status == StepStatus.PENDING

        second = _Counting(components=[])
        asyncio.run(
            PipelineRunner(
                pipeline, _ctx(tmp_path), registry=_registry(decompose__feature=second), store=store
            ).resume(run1.run_id)
        )
        assert second.calls == 1, "a RESERVE-park was wrongly approved"

    def test_auto_gate_park_is_not_approvable(self, tmp_path: Path) -> None:
        """Only HITL gates carry the 'a human looked at this' meaning."""
        pipeline = PipelineDefinition(
            name="p",
            steps=[
                _step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose", _auto()),
                _step(StepAction.VALIDATE, StepTarget.SPEC, "second"),
            ],
        )
        store = StateStore(tmp_path / "state.db")
        first = _Counting(StepStatus.WAITING_FOR_INPUT)
        run1 = asyncio.run(
            PipelineRunner(
                pipeline, _ctx(tmp_path), registry=_registry(decompose__feature=first), store=store
            ).run()
        )
        assert run1.status == RunStatus.PARKED

        second = _Counting(components=[])
        reg = StepHandlerRegistry()
        reg.register(StepAction.DECOMPOSE, StepTarget.FEATURE, second)
        reg.register(StepAction.VALIDATE, StepTarget.SPEC, _Counting())
        asyncio.run(
            PipelineRunner(pipeline, _ctx(tmp_path), registry=reg, store=store).resume(run1.run_id)
        )
        assert second.calls == 1

    def test_run_never_auto_approves(self, tmp_path: Path) -> None:
        """A fresh run() must never consume an approval, even on approvable-looking records."""
        pipeline = PipelineDefinition(
            name="p",
            steps=[_step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose", _hitl())],
        )
        store = StateStore(tmp_path / "state.db")
        handler = _Counting(components=[])
        asyncio.run(
            PipelineRunner(
                pipeline,
                _ctx(tmp_path),
                registry=_registry(decompose__feature=handler),
                store=store,
            ).run()
        )
        # A second fresh run() starts a NEW run — the handler must execute again.
        asyncio.run(
            PipelineRunner(
                pipeline,
                _ctx(tmp_path),
                registry=_registry(decompose__feature=handler),
                store=store,
            ).run()
        )
        assert handler.calls == 2

    def test_approval_is_consumed_once_per_resume(self, tmp_path: Path) -> None:
        """Two HITL gates => two resumes. One resume must not clear both."""
        pipeline = PipelineDefinition(
            name="p",
            steps=[
                _step(StepAction.DECOMPOSE, StepTarget.FEATURE, "first", _hitl()),
                _step(StepAction.DECOMPOSE, StepTarget.FEATURE, "second", _hitl()),
            ],
        )
        store = StateStore(tmp_path / "state.db")
        h1 = _Counting(components=[])
        run1 = asyncio.run(
            PipelineRunner(
                pipeline, _ctx(tmp_path), registry=_registry(decompose__feature=h1), store=store
            ).run()
        )
        assert run1.status == RunStatus.PARKED
        assert run1.current_step == 0

        # Resume 1: approves step 0, step 1 then executes and parks at its own gate.
        h2 = _Counting(components=[])
        run2 = asyncio.run(
            PipelineRunner(
                pipeline, _ctx(tmp_path), registry=_registry(decompose__feature=h2), store=store
            ).resume(run1.run_id)
        )
        assert run2.status == RunStatus.PARKED
        assert run2.current_step == 1
        assert h2.calls == 1, "step 1 should have executed, not been auto-approved"

        # Resume 2: approves step 1 and completes.
        h3 = _Counting(components=[])
        run3 = asyncio.run(
            PipelineRunner(
                pipeline, _ctx(tmp_path), registry=_registry(decompose__feature=h3), store=store
            ).resume(run2.run_id)
        )
        assert run3.status == RunStatus.COMPLETED
        assert h3.calls == 0

    def test_renamed_step_is_not_approvable(self, tmp_path: Path) -> None:
        """A YAML edited between sessions must not let one step's result approve another.

        Same index, same gate, different step — approving would skip a genuinely-unrun step on
        the strength of the old step's result.
        """
        store = StateStore(tmp_path / "state.db")
        original = PipelineDefinition(
            name="p",
            steps=[_step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose", _hitl())],
        )
        run1 = asyncio.run(
            PipelineRunner(
                original,
                _ctx(tmp_path),
                registry=_registry(decompose__feature=_Counting(components=[])),
                store=store,
            ).run()
        )
        assert run1.status == RunStatus.PARKED

        renamed = PipelineDefinition(
            name="p",
            steps=[_step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose_v2", _hitl())],
        )
        second = _Counting(components=[])
        asyncio.run(
            PipelineRunner(
                renamed, _ctx(tmp_path), registry=_registry(decompose__feature=second), store=store
            ).resume(run1.run_id)
        )

        assert second.calls == 1, "a renamed step was approved using another step's result"

    def test_gateless_passed_record_is_not_approvable(self, tmp_path: Path) -> None:
        pipeline = PipelineDefinition(
            name="p", steps=[_step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose")]
        )
        store = StateStore(tmp_path / "state.db")
        first = _Counting(StepStatus.WAITING_FOR_INPUT)
        run1 = asyncio.run(
            PipelineRunner(
                pipeline, _ctx(tmp_path), registry=_registry(decompose__feature=first), store=store
            ).run()
        )
        second = _Counting(components=[])
        asyncio.run(
            PipelineRunner(
                pipeline, _ctx(tmp_path), registry=_registry(decompose__feature=second), store=store
            ).resume(run1.run_id)
        )
        assert second.calls == 1


# ---------------------------------------------------------------------------
# Boundary — the insertion point
# ---------------------------------------------------------------------------


class TestApprovalInsertionPoint:
    def test_approval_beats_the_staleness_bypass(self, tmp_path: Path) -> None:
        """A parked step whose target is 'pristine' must be APPROVED, not skipped.

        The staleness-bypass block also sits before mark_step_running and would otherwise
        complete the step as SKIPPED, discarding the human's approval and the stored result.
        """
        pipeline = PipelineDefinition(
            name="p",
            steps=[_stale_target_step()],
        )
        store = StateStore(tmp_path / "state.db")
        run1 = asyncio.run(
            PipelineRunner(
                pipeline,
                _ctx(tmp_path),
                registry=_registry(decompose__feature=_Counting(components=[{"n": "a"}])),
                store=store,
            ).run()
        )
        assert run1.status == RunStatus.PARKED

        ctx2 = _ctx(tmp_path)
        # nothing is stale -> the bypass would fire
        ctx2.graph = ctx2.graph.model_copy(update={"stale_nodes": set()})
        second = _Counting()
        run2 = asyncio.run(
            PipelineRunner(
                pipeline, ctx2, registry=_registry(decompose__feature=second), store=store
            ).resume(run1.run_id)
        )

        assert second.calls == 0
        assert run2.step_records[0].status == StepStatus.PASSED, (
            "the staleness bypass overwrote the approval with SKIPPED"
        )
        assert run2.status == RunStatus.COMPLETED
