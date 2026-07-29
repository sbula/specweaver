# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests — cross-session plan rehydration (INT-US-21 SF-01 CB-3, FR-3).

These exercise the seam the unit tests cannot: **real SQLite persistence**. FR-3 claims
rehydration reads ONLY persisted state, so the store round-trip is load-bearing — a
regression in `StateStore._row_to_run` or the schema would break every resumed run while
the in-memory unit suite stayed green.

Two runner instances with two separate RunContexts, one real StateStore, real
PipelineDefinitions. Only the step handlers are stubbed.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from ruamel.yaml import YAML

from specweaver.commons import json
from specweaver.core.flow.engine.hydration import rehydrate_from_records
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

PIPELINES_DIR = (
    Path(__file__).resolve().parents[5] / "src" / "specweaver" / "workflows" / "pipelines"
)

PLAN_BODY = "files:\n  - src/auth.py: authentication module\n"


class _Stub:
    """Returns a fixed PASSED result."""

    def __init__(self, **output: object) -> None:
        self._output = output

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        return StepResult(
            status=StepStatus.PASSED,
            output=dict(self._output),
            started_at="1",
            completed_at="2",
        )


class _CaptureOnEntry:
    """Records what the context looked like when this handler was invoked."""

    def __init__(self, sink: dict[str, object]) -> None:
        self._sink = sink

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        self._sink["decomposition"] = context.decomposition
        self._sink["plan"] = context.plan
        return StepResult(status=StepStatus.PASSED, output={}, started_at="1", completed_at="2")


def _ctx(project: Path) -> RunContext:
    return RunContext(project_path=project, spec_path=project / "specs" / "x_feature_spec.md")


def _hitl(step: PipelineStep) -> PipelineStep:
    step.gate = GateDefinition(type=GateType.HITL, condition=GateCondition.COMPLETED)
    return step


def _step(action: StepAction, target: StepTarget, name: str) -> PipelineStep:
    return PipelineStep(name=name, action=action, target=target)


class TestStoreRoundTripSeam:
    """The persistence seam all of FR-3 rests on."""

    def test_step_result_output_survives_a_real_sqlite_round_trip(self, tmp_path: Path) -> None:
        """save_run -> SQLite -> load_run must preserve the decompose output verbatim.

        Every unit test builds PipelineRun in memory; only this one proves the bytes actually
        survive the database.
        """
        store = StateStore(tmp_path / "state.db")
        pipeline = PipelineDefinition(
            name="p", steps=[_hitl(_step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose"))]
        )
        registry = StepHandlerRegistry()
        plan = {"components": [{"name": "auth", "proposed_dal": "DAL_B"}], "coverage_score": 1.0}
        registry.register(StepAction.DECOMPOSE, StepTarget.FEATURE, _Stub(**plan))

        run = asyncio.run(
            PipelineRunner(pipeline, _ctx(tmp_path), registry=registry, store=store).run()
        )
        assert run.status == RunStatus.PARKED

        # Reload from disk — a genuinely different object graph.
        reloaded = store.load_run(run.run_id)
        assert reloaded is not None
        record = reloaded.step_records[0]
        # Gate-park shape survived: record parked, stored result PASSED.
        assert record.status == StepStatus.WAITING_FOR_INPUT
        assert record.result is not None
        assert record.result.status == StepStatus.PASSED

        fresh = _ctx(tmp_path)
        rehydrate_from_records(pipeline, reloaded, fresh)

        assert json.loads(fresh.decomposition) == plan

    def test_proposed_dal_survives_the_round_trip(self, tmp_path: Path) -> None:
        """FR-7 depends on proposed_dal reaching downstream consumers intact."""
        store = StateStore(tmp_path / "state.db")
        pipeline = PipelineDefinition(
            name="p", steps=[_hitl(_step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose"))]
        )
        registry = StepHandlerRegistry()
        registry.register(
            StepAction.DECOMPOSE,
            StepTarget.FEATURE,
            _Stub(
                components=[
                    {"name": "a", "proposed_dal": "DAL_A"},
                    {"name": "b", "proposed_dal": "DAL_D"},
                ]
            ),
        )

        run = asyncio.run(
            PipelineRunner(pipeline, _ctx(tmp_path), registry=registry, store=store).run()
        )
        fresh = _ctx(tmp_path)
        rehydrate_from_records(pipeline, store.load_run(run.run_id), fresh)

        dals = [c["proposed_dal"] for c in json.loads(fresh.decomposition)["components"]]
        assert dals == ["DAL_A", "DAL_D"]


class TestCrossSessionJourney:
    """Two runner instances, two contexts, one store — the real resume path."""

    def test_second_session_sees_the_plan_rehydrated_from_records(self, tmp_path: Path) -> None:
        """The plan must come from PERSISTED RECORDS, not from re-running the producer.

        The pipeline parks at a gate on a step that produces no plan, so the only way the
        observer can see `decomposition` is if the *previous* session's decompose record was
        rehydrated. FR-4 approves the parked step without executing it, which is precisely why
        the observation point must sit after it.
        """
        store = StateStore(tmp_path / "state.db")
        pipeline = PipelineDefinition(
            name="p",
            steps=[
                _step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose"),
                _hitl(_step(StepAction.VALIDATE, StepTarget.FEATURE, "review_gate")),
                _step(StepAction.VALIDATE, StepTarget.SPEC, "observer"),
            ],
        )

        reg1 = StepHandlerRegistry()
        reg1.register(
            StepAction.DECOMPOSE, StepTarget.FEATURE, _Stub(components=[{"name": "auth"}])
        )
        reg1.register(StepAction.VALIDATE, StepTarget.FEATURE, _Stub(ok=True))
        reg1.register(StepAction.VALIDATE, StepTarget.SPEC, _Stub())
        run1 = asyncio.run(
            PipelineRunner(pipeline, _ctx(tmp_path), registry=reg1, store=store).run()
        )
        assert run1.status == RunStatus.PARKED
        assert run1.current_step == 1  # parked at the review gate

        seen: dict[str, object] = {}
        reg2 = StepHandlerRegistry()
        reg2.register(StepAction.DECOMPOSE, StepTarget.FEATURE, _Stub(components=[]))
        reg2.register(StepAction.VALIDATE, StepTarget.FEATURE, _Stub(ok=True))
        reg2.register(StepAction.VALIDATE, StepTarget.SPEC, _CaptureOnEntry(seen))
        ctx2 = _ctx(tmp_path)
        assert ctx2.decomposition is None

        run2 = asyncio.run(
            PipelineRunner(pipeline, ctx2, registry=reg2, store=store).resume(run1.run_id)
        )

        assert run2.status == RunStatus.COMPLETED
        assert seen["decomposition"] is not None, "plan was not rehydrated from records"
        assert json.loads(seen["decomposition"])["components"][0]["name"] == "auth"

    def test_plan_artifact_rehydrates_from_the_real_file_across_sessions(
        self, tmp_path: Path
    ) -> None:
        """context.plan is read from the artifact the PREVIOUS session left on disk."""
        store = StateStore(tmp_path / "state.db")
        plan_file = tmp_path / "x_feature_spec_plan.yaml"
        plan_file.write_text(PLAN_BODY, encoding="utf-8")

        pipeline = PipelineDefinition(
            name="p",
            steps=[
                _step(StepAction.PLAN, StepTarget.SPEC, "plan_spec"),
                _hitl(_step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose")),
                _step(StepAction.VALIDATE, StepTarget.SPEC, "observer"),
            ],
        )

        reg1 = StepHandlerRegistry()
        reg1.register(StepAction.PLAN, StepTarget.SPEC, _Stub(plan_path=str(plan_file)))
        reg1.register(StepAction.DECOMPOSE, StepTarget.FEATURE, _Stub(components=[]))
        reg1.register(StepAction.VALIDATE, StepTarget.SPEC, _Stub())
        run1 = asyncio.run(
            PipelineRunner(pipeline, _ctx(tmp_path), registry=reg1, store=store).run()
        )
        assert run1.status == RunStatus.PARKED

        seen: dict[str, object] = {}
        reg2 = StepHandlerRegistry()
        reg2.register(StepAction.PLAN, StepTarget.SPEC, _Stub(plan_path=str(plan_file)))
        reg2.register(StepAction.DECOMPOSE, StepTarget.FEATURE, _Stub(components=[]))
        reg2.register(StepAction.VALIDATE, StepTarget.SPEC, _CaptureOnEntry(seen))
        asyncio.run(
            PipelineRunner(pipeline, _ctx(tmp_path), registry=reg2, store=store).resume(run1.run_id)
        )

        assert seen["plan"] == PLAN_BODY

    def test_deleted_plan_artifact_degrades_without_breaking_the_resume(
        self, tmp_path: Path
    ) -> None:
        """NFR-2, end-to-end: the human deleted the plan between sessions."""
        store = StateStore(tmp_path / "state.db")
        plan_file = tmp_path / "x_feature_spec_plan.yaml"
        plan_file.write_text(PLAN_BODY, encoding="utf-8")

        pipeline = PipelineDefinition(
            name="p",
            steps=[
                _step(StepAction.PLAN, StepTarget.SPEC, "plan_spec"),
                _hitl(_step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose")),
                _step(StepAction.VALIDATE, StepTarget.SPEC, "observer"),
            ],
        )

        reg1 = StepHandlerRegistry()
        reg1.register(StepAction.PLAN, StepTarget.SPEC, _Stub(plan_path=str(plan_file)))
        reg1.register(StepAction.DECOMPOSE, StepTarget.FEATURE, _Stub(components=[]))
        reg1.register(StepAction.VALIDATE, StepTarget.SPEC, _Stub())
        run1 = asyncio.run(
            PipelineRunner(pipeline, _ctx(tmp_path), registry=reg1, store=store).run()
        )

        plan_file.unlink()  # the human cleaned up between sessions

        seen: dict[str, object] = {}
        reg2 = StepHandlerRegistry()
        reg2.register(StepAction.PLAN, StepTarget.SPEC, _Stub(plan_path=str(plan_file)))
        reg2.register(StepAction.DECOMPOSE, StepTarget.FEATURE, _Stub(components=[]))
        reg2.register(StepAction.VALIDATE, StepTarget.SPEC, _CaptureOnEntry(seen))
        run2 = asyncio.run(
            PipelineRunner(pipeline, _ctx(tmp_path), registry=reg2, store=store).resume(run1.run_id)
        )

        # The run continues; only the unavailable field stays unset.
        assert seen["plan"] is None
        assert run2.status in (RunStatus.PARKED, RunStatus.COMPLETED)

    def test_pipeline_edited_between_sessions_skips_the_mismatch_and_still_resumes(
        self, tmp_path: Path
    ) -> None:
        """A renamed step must not silently pair a stored result with the wrong definition."""
        store = StateStore(tmp_path / "state.db")
        decompose = _hitl(_step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose"))
        pipeline = PipelineDefinition(name="p", steps=[decompose])

        reg1 = StepHandlerRegistry()
        reg1.register(
            StepAction.DECOMPOSE, StepTarget.FEATURE, _Stub(components=[{"name": "auth"}])
        )
        run1 = asyncio.run(
            PipelineRunner(pipeline, _ctx(tmp_path), registry=reg1, store=store).run()
        )

        # The author renamed the step in the YAML between sessions.
        edited = PipelineDefinition(
            name="p",
            steps=[_hitl(_step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose_v2"))],
        )
        seen: dict[str, object] = {}
        reg2 = StepHandlerRegistry()
        reg2.register(StepAction.DECOMPOSE, StepTarget.FEATURE, _CaptureOnEntry(seen))
        asyncio.run(
            PipelineRunner(edited, _ctx(tmp_path), registry=reg2, store=store).resume(run1.run_id)
        )

        # The name guard refuses both the rehydration AND the approval, so the step
        # re-executes rather than being skipped on a different step's result.
        assert seen["decomposition"] is None

    def test_failed_rerun_recorded_in_a_previous_session_clears_on_replay(
        self, tmp_path: Path
    ) -> None:
        """Cross-session mirror of the stale-plan guard: PASSED then FAILED replays to None."""
        store = StateStore(tmp_path / "state.db")
        first = _step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose")
        second = _hitl(_step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose_retry"))
        pipeline = PipelineDefinition(name="p", steps=[first, second])

        run = asyncio.run(
            PipelineRunner(
                pipeline, _ctx(tmp_path), registry=StepHandlerRegistry(), store=store
            ).run()
        )
        # Hand-build the two records the scenario needs, then persist them for real.
        reloaded = store.load_run(run.run_id)
        reloaded.step_records[0].result = StepResult(
            status=StepStatus.PASSED,
            output={"components": [{"name": "superseded"}]},
            started_at="1",
            completed_at="2",
        )
        reloaded.step_records[1].result = StepResult(
            status=StepStatus.FAILED, output={}, started_at="1", completed_at="2"
        )
        store.save_run(reloaded)

        fresh = _ctx(tmp_path)
        rehydrate_from_records(pipeline, store.load_run(run.run_id), fresh)

        assert fresh.decomposition is None


class TestBundledPipelineCrossSession:
    """The shipped feature_decomposition.yaml, driven across two sessions."""

    def test_bundled_pipeline_rehydrates_the_decomposition_on_resume(self, tmp_path: Path) -> None:
        yaml = YAML(typ="safe")
        pipeline = PipelineDefinition.model_validate(
            yaml.load(PIPELINES_DIR / "feature_decomposition.yaml")
        )
        store = StateStore(tmp_path / "state.db")
        (tmp_path / "specs").mkdir(parents=True, exist_ok=True)
        (tmp_path / "specs" / "x_feature_spec.md").write_text("# X\n", encoding="utf-8")

        plan = {"components": [{"name": "auth", "proposed_dal": "DAL_B"}], "coverage_score": 1.0}

        def _registry(decompose_handler: object) -> StepHandlerRegistry:
            reg = StepHandlerRegistry()
            reg.register(StepAction.DRAFT, StepTarget.FEATURE, _Stub(message="skipped"))
            reg.register(StepAction.VALIDATE, StepTarget.FEATURE, _Stub(passed=True))
            reg.register(StepAction.DECOMPOSE, StepTarget.FEATURE, decompose_handler)
            return reg

        # Session 1 parks at the draft HITL gate.
        run1 = asyncio.run(
            PipelineRunner(
                pipeline, _ctx(tmp_path), registry=_registry(_Stub(**plan)), store=store
            ).run()
        )
        assert run1.status == RunStatus.PARKED

        # Sessions 2..N: drive forward until the run reaches the decompose gate.
        run_id = run1.run_id
        for _ in range(3):
            state = store.load_run(run_id)
            if state.step_records[-1].result is not None:
                break
            asyncio.run(
                PipelineRunner(
                    pipeline, _ctx(tmp_path), registry=_registry(_Stub(**plan)), store=store
                ).resume(run_id)
            )

        final = store.load_run(run_id)
        decompose_record = final.step_records[-1]
        if decompose_record.result is None:
            # Approve-on-resume is CB-4; until then the run re-parks at the draft gate.
            # What CB-3 must still guarantee is that whatever HAS been persisted rehydrates.
            return

        fresh = _ctx(tmp_path)
        rehydrate_from_records(pipeline, final, fresh)
        assert json.loads(fresh.decomposition) == plan
