# mypy: ignore-errors
"""Tests for decomposition artifact persistence — INT-US-21 SF-02 CB-1 (FR-5, FR-7 data).

These use REAL ``DecompositionPlan`` objects, never a ``MagicMock``. The sibling tests in
``test_decompose.py`` mock the plan, so ``model_dump()`` returns a mock and serialization is
never exercised — which is precisely how the enum-vs-YAML defect (D1) stayed invisible.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

from ruamel.yaml import YAML

from specweaver.commons.enums.dal import DALLevel
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.decompose import DecomposeFeatureHandler
from specweaver.workflows.planning.decomposition import (
    ComponentChange,
    DecompositionPlan,
    IntegrationSeam,
)

if TYPE_CHECKING:
    from pathlib import Path


def _plan(*, components: list[ComponentChange] | None = None, coverage: float = 1.0) -> DecompositionPlan:
    if components is None:
        components = [
            ComponentChange(
                component="auth",
                exists=False,
                change_nature="new_interface",
                description="Handles login and token issuance.",
                proposed_dal=DALLevel.DAL_B,
                dependencies=[],
                target_modules=["src/auth"],
                confidence=90,
            ),
            ComponentChange(
                component="billing",
                exists=True,
                change_nature="behavior",
                description="Charges on signup.",
                proposed_dal=DALLevel.DAL_D,
                dependencies=["auth"],
                target_modules=["src/billing"],
                confidence=70,
            ),
        ]
    return DecompositionPlan(
        feature_spec="specs/onboarding_feature_spec.md",
        components=components,
        integration_seams=[
            IntegrationSeam(between=("auth", "billing"), contract="UserCreated", format="event")
        ],
        build_sequence=[c.component for c in components],
        coverage_score=coverage,
        alignment_notes=[],
        timestamp="2026-07-25T00:00:00Z",
    )


def _step(**params) -> PipelineStep:
    return PipelineStep(
        name="decompose", action=StepAction.DECOMPOSE, target=StepTarget.FEATURE, params=params
    )


def _ctx(tmp_path: Path) -> RunContext:
    specs = tmp_path / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    spec = specs / "onboarding_feature_spec.md"
    spec.write_text("# Onboarding\n", encoding="utf-8")
    ctx = RunContext(project_path=tmp_path, spec_path=spec)
    ctx.llm = AsyncMock()
    ctx.run_id = "run-1"
    return ctx


def _run(ctx: RunContext, step: PipelineStep, plan: DecompositionPlan):
    """Execute the handler with the decomposer stubbed to return a REAL plan."""
    with patch(
        "specweaver.core.flow.handlers.decompose.FeatureDecomposer"
    ) as cls, patch(
        "specweaver.core.flow.handlers.base._build_base_prompt", new=AsyncMock(return_value=MagicMock())
    ):
        inst = AsyncMock()
        inst.decompose.return_value = plan
        cls.return_value = inst
        import asyncio

        return asyncio.run(DecomposeFeatureHandler().execute(step, ctx)), inst


def _artifact(ctx: RunContext) -> Path:
    return ctx.spec_path.with_name(ctx.spec_path.stem + "_decomposition.yaml")


def _loaded(ctx: RunContext) -> dict:
    text = _artifact(ctx).read_text(encoding="utf-8")
    return YAML(typ="safe").load(text)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestArtifactHappyPath:
    def test_artifact_written_next_to_the_spec(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        result, _ = _run(ctx, _step(), _plan())

        assert result.status == StepStatus.PASSED, result.error_message
        assert _artifact(ctx).exists()
        assert _artifact(ctx).parent == ctx.spec_path.parent  # AD-7 / D7

    def test_proposed_dal_is_a_string_in_the_yaml(self, tmp_path: Path) -> None:
        """D1 — the whole reason SF-02 deviates from the design's wording.

        `model_dump()` would leave a DALLevel enum here and ruamel would raise
        RepresenterError; `model_dump(mode="json")` emits a plain string.
        """
        ctx = _ctx(tmp_path)
        _run(ctx, _step(), _plan())

        dals = [c["proposed_dal"] for c in _loaded(ctx)["components"]]
        assert dals == ["DAL_B", "DAL_D"]
        assert all(isinstance(d, str) for d in dals)

    def test_artifact_carries_the_uuid_lineage_tag(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        _run(ctx, _step(), _plan())

        first = _artifact(ctx).read_text(encoding="utf-8").splitlines()[0]
        assert first.startswith("# sw-artifact:")

    def test_output_nests_the_plan_and_exposes_the_path(self, tmp_path: Path) -> None:
        """Option (b): the plan is nested so the frozen seam stays schema-pure."""
        ctx = _ctx(tmp_path)
        result, _ = _run(ctx, _step(), _plan())

        assert "plan" in result.output
        assert result.output["decomposition_path"] == str(_artifact(ctx))
        # The nested plan must be exactly the DecompositionPlan schema — nothing else.
        assert set(result.output["plan"]) == set(_plan().model_dump(mode="json"))

    def test_nested_plan_round_trips_to_an_equal_model(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        result, _ = _run(ctx, _step(), _plan())

        restored = DecompositionPlan.model_validate(result.output["plan"])
        assert [c.component for c in restored.components] == ["auth", "billing"]
        assert restored.components[0].proposed_dal == DALLevel.DAL_B

    def test_feature_name_derived_from_the_spec_stem(self, tmp_path: Path) -> None:
        """T5.1 — kills the 'unknown_feature' fallback when no param is supplied."""
        ctx = _ctx(tmp_path)
        _, decomposer = _run(ctx, _step(), _plan())

        _, kwargs = decomposer.decompose.call_args
        assert kwargs["feature_name"] == "onboarding"

    def test_explicit_feature_name_param_still_wins(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        _, decomposer = _run(ctx, _step(feature_name="explicit"), _plan())

        _, kwargs = decomposer.decompose.call_args
        assert kwargs["feature_name"] == "explicit"

    def test_lineage_event_logged_when_db_configured(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        ctx.db = MagicMock()
        repo = MagicMock()
        repo.log_artifact_event = AsyncMock()

        with patch("specweaver.core.flow.store.FlowRepository", return_value=repo):
            result, _ = _run(ctx, _step(), _plan())

        assert result.status == StepStatus.PASSED, result.error_message
        repo.log_artifact_event.assert_called_once()
        assert repo.log_artifact_event.call_args.kwargs["event_type"] == "generated_decomposition"


# ---------------------------------------------------------------------------
# Boundary / edge
# ---------------------------------------------------------------------------


class TestArtifactBoundaries:
    def test_zero_component_plan_still_writes_an_artifact(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        result, _ = _run(ctx, _step(), _plan(components=[]))

        assert result.status == StepStatus.PASSED, result.error_message
        assert _loaded(ctx)["components"] == []

    def test_rerun_reuses_the_existing_artifact_uuid(self, tmp_path: Path) -> None:
        """A second decomposition must not mint a new lineage identity for the same artifact."""
        ctx = _ctx(tmp_path)
        _run(ctx, _step(), _plan())
        first_tag = _artifact(ctx).read_text(encoding="utf-8").splitlines()[0]

        _run(ctx, _step(), _plan())
        second_tag = _artifact(ctx).read_text(encoding="utf-8").splitlines()[0]

        assert first_tag == second_tag

    def test_coverage_exactly_one_passes(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        result, _ = _run(ctx, _step(), _plan(coverage=1.0))
        assert result.status == StepStatus.PASSED

    def test_low_coverage_fails_and_writes_no_artifact(self, tmp_path: Path) -> None:
        """The 3-strike coverage guard runs BEFORE persistence — no partial artifact."""
        ctx = _ctx(tmp_path)
        result, _ = _run(ctx, _step(), _plan(coverage=0.5))

        assert result.status == StepStatus.FAILED
        assert not _artifact(ctx).exists()


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------


class TestArtifactDegradation:
    def test_unset_db_skips_lineage_but_still_passes(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        assert ctx.db is None

        result, _ = _run(ctx, _step(), _plan())

        assert result.status == StepStatus.PASSED, result.error_message
        assert _artifact(ctx).exists()


# ---------------------------------------------------------------------------
# Hostile / wrong input
# ---------------------------------------------------------------------------


class TestArtifactHostile:
    def test_write_failure_fails_loudly_but_retains_the_plan(self, tmp_path: Path) -> None:
        """D6 — a disk error must not discard an expensive LLM decomposition."""
        ctx = _ctx(tmp_path)

        real_write = type(ctx.spec_path).write_text

        def boom(self, *a, **kw):
            if self.name.endswith("_decomposition.yaml"):
                raise OSError("disk full")
            return real_write(self, *a, **kw)

        with patch.object(type(ctx.spec_path), "write_text", boom):
            result, _ = _run(ctx, _step(), _plan())

        assert result.status in (StepStatus.FAILED, StepStatus.ERROR)
        assert "plan" in result.output, "the decomposition was discarded on a disk error"
        assert result.output["plan"]["components"][0]["component"] == "auth"


# ---------------------------------------------------------------------------
# The frozen seam: hydration must still see a pure DecompositionPlan
# ---------------------------------------------------------------------------


class TestSeamStaysPure:
    def test_hydration_unwraps_the_nested_plan(self, tmp_path: Path) -> None:
        """context.decomposition must remain canonical DecompositionPlan JSON (AD-4)."""
        from specweaver.commons import json
        from specweaver.core.flow.engine.hydration import hydrate_plan_context

        ctx = _ctx(tmp_path)
        result, _ = _run(ctx, _step(), _plan())

        hydrate_plan_context(_step(), result, ctx)

        assert ctx.decomposition is not None
        hydrated = json.loads(ctx.decomposition)
        assert "decomposition_path" not in hydrated, "the frozen seam was polluted"
        assert set(hydrated) == set(_plan().model_dump(mode="json"))
        assert hydrated["components"][0]["proposed_dal"] == "DAL_B"

    def test_hydration_is_backward_compatible_with_flat_output(self, tmp_path: Path) -> None:
        """Records persisted before SF-02 have the plan flat at the top level."""
        from specweaver.commons import json
        from specweaver.core.flow.engine.hydration import hydrate_plan_context
        from specweaver.core.flow.engine.state import StepResult

        ctx = _ctx(tmp_path)
        legacy = StepResult(
            status=StepStatus.PASSED,
            output=_plan().model_dump(mode="json"),
            started_at="1",
            completed_at="2",
        )

        hydrate_plan_context(_step(), legacy, ctx)

        assert json.loads(ctx.decomposition)["components"][0]["component"] == "auth"


# ---------------------------------------------------------------------------
# Pre-commit Phase 3 additions (CB-1 gate, 2026-07-26) — T2..T5
# ---------------------------------------------------------------------------


def _ctx_named(tmp_path: Path, filename: str) -> RunContext:
    """A context whose spec has an arbitrary filename (the default helper hardcodes one)."""
    specs = tmp_path / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    spec = specs / filename
    spec.write_text("# Spec\n", encoding="utf-8")
    ctx = RunContext(project_path=tmp_path, spec_path=spec)
    ctx.llm = AsyncMock()
    ctx.run_id = "run-1"
    return ctx


class TestFeatureNameDerivation:
    """T3: the `removesuffix(...) or stem` fallback at decompose.py:28."""

    def test_spec_without_the_feature_spec_suffix_uses_the_stem_verbatim(
        self, tmp_path: Path
    ) -> None:
        ctx = _ctx_named(tmp_path, "checkout.md")
        _, inst = _run(ctx, _step(), _plan())
        assert inst.decompose.await_args.kwargs["feature_name"] == "checkout"

    def test_spec_named_exactly_the_suffix_falls_back_to_the_stem(self, tmp_path: Path) -> None:
        """`_feature_spec.md` strips to "" — the `or` guard must not pass an empty name."""
        ctx = _ctx_named(tmp_path, "_feature_spec.md")
        _, inst = _run(ctx, _step(), _plan())
        assert inst.decompose.await_args.kwargs["feature_name"] == "_feature_spec"


class TestUuidContinuity:
    """T2: an existing artifact whose lineage tag was stripped by hand."""

    def test_untagged_existing_artifact_mints_a_fresh_uuid(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        _artifact(ctx).write_text("components: []\n", encoding="utf-8")  # no sw-artifact tag

        result, _ = _run(ctx, _step(), _plan())

        assert result.status == StepStatus.PASSED
        assert result.artifact_uuid, "no uuid was minted for an untagged artifact"
        text = _artifact(ctx).read_text(encoding="utf-8")
        assert result.artifact_uuid in text


class TestExecuteGuardPaths:
    """T4/T5: two guards in `execute` with no coverage before this gate."""

    def test_invalid_render_profile_errors_and_writes_no_artifact(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path)
        result, inst = _run(ctx, _step(render_profile="no_such_profile"), _plan())

        assert result.status in (StepStatus.ERROR, StepStatus.FAILED)
        assert not _artifact(ctx).exists()
        inst.decompose.assert_not_awaited()

    def test_missing_spec_file_still_runs_with_empty_spec_content(self, tmp_path: Path) -> None:
        """The guard is deliberate: decompose does not own spec existence (draft/validate do)."""
        ctx = _ctx(tmp_path)
        ctx.spec_path.unlink()

        result, inst = _run(ctx, _step(), _plan())

        assert result.status == StepStatus.PASSED
        assert inst.decompose.await_args.kwargs["spec_content"] == ""
