# mypy: ignore-errors
"""Tests for the runner's plan-hydration bridge — INT-US-21 SF-01 CB-2 (FR-2).

Two colliding plan concepts previously shared one never-written field:
  * decompose+feature -> a DecompositionPlan  -> context.decomposition (new)
  * plan+spec         -> an implementation PlanArtifact -> context.plan

`hydrate_plan_context` is the single place both are written, shared with the
resume-time rehydration (CB-3) so the two can never drift apart.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.engine.hydration import hydrate_plan_context
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import RunContext

if TYPE_CHECKING:
    from pathlib import Path


def _step(action: StepAction, target: StepTarget, name: str = "s") -> PipelineStep:
    return PipelineStep(name=name, action=action, target=target)


def _result(status: StepStatus = StepStatus.PASSED, **output) -> StepResult:
    return StepResult(status=status, output=output, started_at="1", completed_at="2")


def _ctx(tmp_path: Path) -> RunContext:
    return RunContext(project_path=tmp_path, spec_path=tmp_path / "greeter_spec.md")


DECOMPOSE_STEP = _step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose")
PLAN_STEP = _step(StepAction.PLAN, StepTarget.SPEC, "plan_spec")


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHydrationHappyPath:
    def test_decompose_output_lands_in_context_decomposition(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        plan = {"components": [{"name": "auth", "proposed_dal": "B"}], "coverage_score": 1.0}

        hydrate_plan_context(DECOMPOSE_STEP, _result(**plan), ctx)

        assert ctx.decomposition is not None
        assert json.loads(ctx.decomposition) == plan

    def test_decomposition_is_a_json_string_not_a_dict(self, tmp_path: Path) -> None:
        """The add-on seam is frozen as a string contract (plan decision D4)."""
        ctx = _ctx(tmp_path)

        hydrate_plan_context(DECOMPOSE_STEP, _result(components=[]), ctx)

        assert isinstance(ctx.decomposition, str)

    def test_plan_step_loads_file_content_into_context_plan(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        plan_file = tmp_path / "greeter_spec_plan.yaml"
        plan_file.write_text("files:\n  - src/greeter.py\n", encoding="utf-8")

        hydrate_plan_context(PLAN_STEP, _result(plan_path=str(plan_file)), ctx)

        assert ctx.plan == "files:\n  - src/greeter.py\n"

    def test_decompose_hydration_logs_at_info_with_run_id(self, tmp_path: Path, caplog) -> None:
        """NFR-7: every hydration is observable, tagged with the run it belongs to."""
        ctx = _ctx(tmp_path)
        ctx.run_id = "run-abc"

        with caplog.at_level("INFO"):
            hydrate_plan_context(DECOMPOSE_STEP, _result(components=[]), ctx)

        msgs = [r.getMessage() for r in caplog.records if r.levelname == "INFO"]
        assert any("run-abc" in m and "context.decomposition" in m for m in msgs)

    def test_plan_hydration_logs_at_info_with_run_id_and_path(
        self, tmp_path: Path, caplog
    ) -> None:
        ctx = _ctx(tmp_path)
        ctx.run_id = "run-xyz"
        plan_file = tmp_path / "greeter_spec_plan.yaml"
        plan_file.write_text("impl: plan\n", encoding="utf-8")

        with caplog.at_level("INFO"):
            hydrate_plan_context(PLAN_STEP, _result(plan_path=str(plan_file)), ctx)

        msgs = [r.getMessage() for r in caplog.records if r.levelname == "INFO"]
        assert any("run-xyz" in m and "greeter_spec_plan.yaml" in m for m in msgs)

    def test_the_two_fields_do_not_collide(self, tmp_path: Path) -> None:
        """The whole point of AD-1: both bridges populated, neither overwrites the other."""
        ctx = _ctx(tmp_path)
        plan_file = tmp_path / "greeter_spec_plan.yaml"
        plan_file.write_text("impl: plan\n", encoding="utf-8")

        hydrate_plan_context(DECOMPOSE_STEP, _result(components=[{"name": "auth"}]), ctx)
        hydrate_plan_context(PLAN_STEP, _result(plan_path=str(plan_file)), ctx)

        assert json.loads(ctx.decomposition)["components"][0]["name"] == "auth"
        assert ctx.plan == "impl: plan\n"


# ---------------------------------------------------------------------------
# Boundary / edge cases
# ---------------------------------------------------------------------------


class TestHydrationBoundaries:
    @pytest.mark.parametrize(
        "status",
        [StepStatus.FAILED, StepStatus.ERROR, StepStatus.WAITING_FOR_INPUT, StepStatus.SKIPPED,
         StepStatus.PENDING],
    )
    def test_only_passed_results_hydrate(self, tmp_path: Path, status: StepStatus) -> None:
        ctx = _ctx(tmp_path)

        hydrate_plan_context(DECOMPOSE_STEP, _result(status, components=[]), ctx)

        assert ctx.decomposition is None

    @pytest.mark.parametrize("status", [StepStatus.SKIPPED, StepStatus.WAITING_FOR_INPUT])
    def test_non_failure_statuses_do_not_clear(
        self, tmp_path: Path, status: StepStatus
    ) -> None:
        """SKIPPED / parked produce no new verdict — there is nothing to supersede.

        Wiping a still-valid plan because a step was bypassed (or parked and due to re-run on
        resume) would be gratuitous. Only a genuine FAILED/ERROR invalidates a prior output.
        """
        ctx = _ctx(tmp_path)
        hydrate_plan_context(DECOMPOSE_STEP, _result(components=[{"name": "still_valid"}]), ctx)

        hydrate_plan_context(DECOMPOSE_STEP, _result(status), ctx)

        assert ctx.decomposition is not None
        assert json.loads(ctx.decomposition)["components"][0]["name"] == "still_valid"

    @pytest.mark.parametrize("status", [StepStatus.FAILED, StepStatus.ERROR])
    def test_failed_rerun_clears_a_previously_hydrated_decomposition(
        self, tmp_path: Path, status: StepStatus
    ) -> None:
        """F4: a superseded plan must never survive a failed re-run of its own step.

        decompose passes -> hydrates -> a later step loops back -> decompose re-runs and
        fails. Without clearing, context.decomposition still holds the OLD plan and a
        downstream orchestrate step silently consumes stale data. No plan (loud failure)
        beats wrong plan (silent success).
        """
        ctx = _ctx(tmp_path)
        hydrate_plan_context(DECOMPOSE_STEP, _result(components=[{"name": "stale"}]), ctx)
        assert ctx.decomposition is not None

        hydrate_plan_context(DECOMPOSE_STEP, _result(status), ctx)

        assert ctx.decomposition is None

    def test_failed_plan_step_clears_a_previously_hydrated_plan(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        plan_file = tmp_path / "greeter_spec_plan.yaml"
        plan_file.write_text("impl: plan\n", encoding="utf-8")
        hydrate_plan_context(PLAN_STEP, _result(plan_path=str(plan_file)), ctx)
        assert ctx.plan == "impl: plan\n"

        hydrate_plan_context(PLAN_STEP, _result(StepStatus.FAILED), ctx)

        assert ctx.plan is None

    def test_a_failed_step_only_clears_its_own_field(self, tmp_path: Path) -> None:
        """A failed decompose must not wipe the unrelated implementation plan."""
        ctx = _ctx(tmp_path)
        plan_file = tmp_path / "greeter_spec_plan.yaml"
        plan_file.write_text("impl: plan\n", encoding="utf-8")
        hydrate_plan_context(PLAN_STEP, _result(plan_path=str(plan_file)), ctx)
        hydrate_plan_context(DECOMPOSE_STEP, _result(components=[{"name": "x"}]), ctx)

        hydrate_plan_context(DECOMPOSE_STEP, _result(StepStatus.FAILED), ctx)

        assert ctx.decomposition is None
        assert ctx.plan == "impl: plan\n"

    def test_an_unrelated_failed_step_clears_nothing(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        hydrate_plan_context(DECOMPOSE_STEP, _result(components=[{"name": "x"}]), ctx)

        hydrate_plan_context(
            _step(StepAction.VALIDATE, StepTarget.SPEC), _result(StepStatus.FAILED), ctx
        )

        assert ctx.decomposition is not None

    def test_unrelated_step_hydrates_nothing(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        step = _step(StepAction.VALIDATE, StepTarget.SPEC)

        hydrate_plan_context(step, _result(anything="here"), ctx)

        assert ctx.decomposition is None
        assert ctx.plan is None

    def test_empty_decompose_output_still_hydrates(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)

        hydrate_plan_context(DECOMPOSE_STEP, _result(), ctx)

        assert ctx.decomposition == "{}"

    def test_empty_plan_file_hydrates_empty_string(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        plan_file = tmp_path / "empty_plan.yaml"
        plan_file.write_text("", encoding="utf-8")

        hydrate_plan_context(PLAN_STEP, _result(plan_path=str(plan_file)), ctx)

        assert ctx.plan == ""


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------


class TestHydrationDegradation:
    def test_missing_plan_path_key_leaves_context_plan_untouched(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        ctx.plan = "pre-existing"

        hydrate_plan_context(PLAN_STEP, _result(something_else="x"), ctx)

        assert ctx.plan == "pre-existing"

    def test_deleted_plan_file_warns_and_leaves_context_plan_untouched(
        self, tmp_path: Path, caplog
    ) -> None:
        """Human deleted the plan between park and resume — warn, never crash (NFR-2)."""
        ctx = _ctx(tmp_path)
        missing = tmp_path / "gone_plan.yaml"

        with caplog.at_level("WARNING"):
            hydrate_plan_context(PLAN_STEP, _result(plan_path=str(missing)), ctx)

        assert ctx.plan is None
        assert any("gone_plan.yaml" in r.getMessage() for r in caplog.records)

    def test_unreadable_plan_file_does_not_raise(self, tmp_path: Path) -> None:
        """A directory where a file is expected must degrade, not explode."""
        ctx = _ctx(tmp_path)
        as_dir = tmp_path / "weird_plan.yaml"
        as_dir.mkdir()

        hydrate_plan_context(PLAN_STEP, _result(plan_path=str(as_dir)), ctx)

        assert ctx.plan is None


# ---------------------------------------------------------------------------
# Hostile / wrong input
# ---------------------------------------------------------------------------


class TestHydrationHostile:
    def test_none_plan_path_does_not_raise(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)

        hydrate_plan_context(PLAN_STEP, _result(plan_path=None), ctx)

        assert ctx.plan is None

    def test_non_string_plan_path_does_not_raise(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)

        hydrate_plan_context(PLAN_STEP, _result(plan_path=12345), ctx)

        assert ctx.plan is None

    def test_empty_string_plan_path_does_not_raise(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)

        hydrate_plan_context(PLAN_STEP, _result(plan_path=""), ctx)

        assert ctx.plan is None

    def test_non_serializable_decompose_output_does_not_raise(self, tmp_path: Path) -> None:
        """A handler returning exotic objects must not take the whole run down."""
        ctx = _ctx(tmp_path)

        hydrate_plan_context(DECOMPOSE_STEP, _result(obj=object()), ctx)

        # Either skipped or coerced — the contract is only "does not raise".
        assert ctx.decomposition is None or isinstance(ctx.decomposition, str)

    def test_binary_plan_file_does_not_raise(self, tmp_path: Path) -> None:
        """UnicodeDecodeError is a ValueError, not an OSError — it must still be caught."""
        ctx = _ctx(tmp_path)
        corrupt = tmp_path / "corrupt_plan.yaml"
        corrupt.write_bytes(b"\xff\xfe\x00not utf8 \x80\x81")

        hydrate_plan_context(PLAN_STEP, _result(plan_path=str(corrupt)), ctx)

        assert ctx.plan is None


# ---------------------------------------------------------------------------
# Live-path / resume-path serialization parity
# ---------------------------------------------------------------------------


class TestSerializationParityWithTheStore:
    """The live hook and the resume rehydration MUST produce identical results.

    StateStore persists step records with `default=str` (store.py:132-133). If the live
    hook serialized more strictly, an output carrying a Path/set would fail to hydrate
    during the run but succeed after a resume — the same run behaving differently
    depending on whether it was interrupted.
    """

    @pytest.mark.parametrize(
        ("label", "value"),
        [
            ("path", __import__("pathlib").Path("src/auth.py")),
            ("set", {"a", "b"}),
            ("custom_object", object()),
        ],
    )
    def test_exotic_values_hydrate_the_same_way_the_store_persists_them(
        self, tmp_path: Path, label: str, value: object
    ) -> None:
        ctx = _ctx(tmp_path)

        hydrate_plan_context(DECOMPOSE_STEP, _result(components=[{label: value}]), ctx)

        assert ctx.decomposition is not None, f"{label} failed to hydrate on the live path"
        assert isinstance(json.loads(ctx.decomposition)["components"][0][label], str)

    def test_live_hydration_matches_a_store_round_trip(self, tmp_path: Path) -> None:
        """Byte-for-byte parity between hydrating live and hydrating from a stored record."""
        from specweaver.commons import json as cjson

        output = {"components": [{"name": "auth", "src": __import__("pathlib").Path("a.py")}]}

        live_ctx = _ctx(tmp_path)
        hydrate_plan_context(DECOMPOSE_STEP, _result(**output), live_ctx)

        # What the store would hand back after a resume (store.py:132-133 semantics).
        round_tripped = cjson.loads(cjson.dumps(output, default=str))
        resumed_ctx = _ctx(tmp_path)
        hydrate_plan_context(DECOMPOSE_STEP, _result(**round_tripped), resumed_ctx)

        assert live_ctx.decomposition == resumed_ctx.decomposition


# ---------------------------------------------------------------------------
# Runner wiring — the hook must fire from the real loop, on BOTH advance paths
# ---------------------------------------------------------------------------


class _StubHandler:
    """Returns a fixed PASSED result."""

    def __init__(self, **output) -> None:
        self._output = output

    async def execute(self, step, context) -> StepResult:
        return StepResult(
            status=StepStatus.PASSED,
            output=self._output,
            started_at="1",
            completed_at="2",
        )


def _run(pipeline, ctx) -> None:
    import asyncio

    from specweaver.core.flow.engine.runner import PipelineRunner
    from specweaver.core.flow.handlers.registry import StepHandlerRegistry

    registry = StepHandlerRegistry()
    registry.register(
        StepAction.DECOMPOSE, StepTarget.FEATURE, _StubHandler(components=[{"name": "auth"}])
    )
    registry.register(
        StepAction.PLAN,
        StepTarget.SPEC,
        _StubHandler(plan_path=str(ctx.project_path / "greeter_spec_plan.yaml")),
    )
    asyncio.run(PipelineRunner(pipeline, ctx, registry=registry).run())


class TestHydrationWiredIntoTheLoop:
    def test_gateless_plan_step_still_hydrates(self, tmp_path: Path) -> None:
        """R/B C1.1: placing the call inside the gate block would silently skip this."""
        from specweaver.core.flow.engine.models import PipelineDefinition

        ctx = _ctx(tmp_path)
        (tmp_path / "greeter_spec_plan.yaml").write_text("impl: plan\n", encoding="utf-8")
        pipeline = PipelineDefinition(
            name="p", steps=[_step(StepAction.PLAN, StepTarget.SPEC, "plan_spec")]
        )

        _run(pipeline, ctx)

        assert ctx.plan == "impl: plan\n"

    def test_router_bearing_step_still_hydrates(self, tmp_path: Path) -> None:
        """The join point sits before the router branch — both routing outcomes hydrate."""
        from specweaver.core.flow.engine.models import PipelineDefinition, RouterDefinition

        ctx = _ctx(tmp_path)
        decompose = _step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose")
        tail = _step(StepAction.PLAN, StepTarget.SPEC, "plan_spec")
        (tmp_path / "greeter_spec_plan.yaml").write_text("impl: plan\n", encoding="utf-8")
        decompose.router = RouterDefinition(default_target="plan_spec")
        pipeline = PipelineDefinition(name="p", steps=[decompose, tail])

        _run(pipeline, ctx)

        assert ctx.decomposition is not None
        assert json.loads(ctx.decomposition)["components"][0]["name"] == "auth"

    def test_downstream_handler_observes_the_hydrated_field(self, tmp_path: Path) -> None:
        """CB-2's own seam: the NEXT step's handler sees the field already populated."""
        import asyncio

        from specweaver.core.flow.engine.models import PipelineDefinition
        from specweaver.core.flow.engine.runner import PipelineRunner
        from specweaver.core.flow.handlers.registry import StepHandlerRegistry

        seen: dict[str, object] = {}

        class _ObservingHandler:
            async def execute(self, step, context):
                seen["decomposition"] = context.decomposition
                return StepResult(
                    status=StepStatus.PASSED, output={}, started_at="1", completed_at="2"
                )

        ctx = _ctx(tmp_path)
        registry = StepHandlerRegistry()
        registry.register(
            StepAction.DECOMPOSE, StepTarget.FEATURE, _StubHandler(components=[{"name": "auth"}])
        )
        registry.register(StepAction.VALIDATE, StepTarget.SPEC, _ObservingHandler())
        pipeline = PipelineDefinition(
            name="p",
            steps=[
                _step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose"),
                _step(StepAction.VALIDATE, StepTarget.SPEC, "downstream"),
            ],
        )

        asyncio.run(PipelineRunner(pipeline, ctx, registry=registry).run())

        assert seen["decomposition"] is not None
        assert json.loads(seen["decomposition"])["components"][0]["name"] == "auth"

    def test_gated_decompose_step_hydrates(self, tmp_path: Path) -> None:
        from specweaver.core.flow.engine.models import (
            GateCondition,
            GateDefinition,
            GateType,
            PipelineDefinition,
        )

        ctx = _ctx(tmp_path)
        step = _step(StepAction.DECOMPOSE, StepTarget.FEATURE, "decompose")
        step.gate = GateDefinition(type=GateType.AUTO, condition=GateCondition.ALL_PASSED)
        pipeline = PipelineDefinition(name="p", steps=[step])

        _run(pipeline, ctx)

        assert ctx.decomposition is not None
        assert json.loads(ctx.decomposition)["components"][0]["name"] == "auth"
