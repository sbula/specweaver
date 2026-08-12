# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests — decomposition artifacts (INT-US-21 SF-02 CB-1 + CB-2; FR-5, FR-6, FR-7).

The unit tests in ``tests/unit/core/flow/handlers/test_decompose_artifact.py`` instantiate
``DecomposeFeatureHandler()`` and call ``execute()`` directly, with a mocked ``context.db``. That
proves the handler's own logic and nothing about the machinery around it. These tests exercise the
seams the unit suite structurally cannot reach:

* the **real** ``StepHandlerRegistry`` resolving ``decompose+feature`` to this handler — a unit test
  that constructs the handler by hand cannot notice an unregistered row, which is exactly how
  `D-INTL-02` shipped an unrunnable pipeline;
* the **real** runner hydration hook, so FR-5's claim that the on-disk artifact and the in-memory
  ``context.plan_context.decomposition`` agree is proven in production wiring rather than by calling
  ``hydrate_plan_context`` by hand;
* **real SQLite** for both the state store round trip and the ``generated_decomposition`` lineage
  row;
* a **real filesystem failure** for D6, rather than a patched ``write_text``;
* **real files on disk** for FR-6's stub component specs — the claim is that a user can carry
  them into ``sw implement``, which a mocked filesystem cannot demonstrate.

The mocked edge is the LLM: ``FeatureDecomposer`` is doubled to return a real ``DecompositionPlan``
(never a ``MagicMock`` — a mock's ``model_dump()`` hides the enum-serialization defect that D1
exists to prevent). Per ``tests/CLAUDE.md``, mocking external APIs only is the integration
convention.

The full three-session CLI journey through the bundled ``feature_decomposition.yaml`` is **SF-03
/ FR-10** — it needs approve-on-resume twice and a spec that passes the real feature battery. These
tests drive a minimal pipeline containing the real decompose step instead.
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ruamel.yaml import YAML

from specweaver.commons import json
from specweaver.commons.enums.dal import DALLevel
from specweaver.commons.lineage import extract_artifact_uuid
from specweaver.core.config.database import Database
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
from specweaver.core.flow.engine.state import RunStatus, StepStatus
from specweaver.core.flow.engine.store import StateStore
from specweaver.core.flow.handlers.decompose import DecomposeFeatureHandler
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.workflows.planning.decomposition import (
    ComponentChange,
    DecompositionPlan,
    IntegrationSeam,
)

SPEC_STEM = "onboarding_feature_spec"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _plan(coverage: float = 1.0) -> DecompositionPlan:
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
        feature_spec=f"specs/{SPEC_STEM}.md",
        components=components,
        integration_seams=[
            IntegrationSeam(between=("auth", "billing"), contract="UserCreated", format="event")
        ],
        build_sequence=[c.component for c in components],
        coverage_score=coverage,
        alignment_notes=[],
        timestamp="2026-07-26T00:00:00Z",
    )


def _spec(tmp_path: Path) -> Path:
    specs = tmp_path / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    spec = specs / f"{SPEC_STEM}.md"
    spec.write_text("# Onboarding\n\nEpic-level feature spec.\n", encoding="utf-8")
    return spec


def _ctx(tmp_path: Path, db: Database | None = None) -> RunContext:
    ctx = RunContext(project_path=tmp_path, spec_path=_spec(tmp_path))
    ctx.model = ctx.model.model_copy(update={"llm": AsyncMock()})
    if db is not None:
        ctx.db = db
    return ctx


def _artifact_path(tmp_path: Path) -> Path:
    return tmp_path / "specs" / f"{SPEC_STEM}_decomposition.yaml"


def _pipeline(*, hitl: bool = False) -> PipelineDefinition:
    """A minimal pipeline whose only step is the real decompose step."""
    step = PipelineStep(name="decompose", action=StepAction.DECOMPOSE, target=StepTarget.FEATURE)
    if hitl:
        step.gate = GateDefinition(type=GateType.HITL, condition=GateCondition.COMPLETED)
    return PipelineDefinition(name="decompose_only", steps=[step])


def _run(pipeline: PipelineDefinition, ctx: RunContext, store: StateStore, plan: DecompositionPlan):
    """Drive the pipeline through the REAL registry with only the decomposer doubled."""
    registry = StepHandlerRegistry()
    resolved = registry.get(StepAction.DECOMPOSE, StepTarget.FEATURE)
    assert isinstance(resolved, DecomposeFeatureHandler), (
        "the real registry must resolve decompose+feature to the real handler; "
        "constructing the handler by hand is what let D-INTL-02 ship unregistered"
    )
    runner = PipelineRunner(pipeline, ctx, registry=registry, store=store)
    with (
        patch("specweaver.core.flow.handlers.decompose.FeatureDecomposer") as cls,
        patch(
            "specweaver.core.flow.handlers.base._build_base_prompt",
            new=AsyncMock(return_value=MagicMock()),
        ),
    ):
        inst = AsyncMock()
        inst.decompose.return_value = plan
        cls.return_value = inst
        return asyncio.run(runner.run()), runner


def _yaml_body(path: Path) -> dict:
    """Load the artifact, which carries a uuid tag line ahead of the YAML."""
    return YAML(typ="safe").load(path.read_text(encoding="utf-8"))


@pytest.fixture
def lineage_db(tmp_path: Path) -> Database:
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database

    db_path = tmp_path / "specweaver.db"
    bootstrap_database(str(db_path))
    return Database(db_path)


# ---------------------------------------------------------------------------
# Happy path — the real registry, runner and filesystem together
# ---------------------------------------------------------------------------


class TestArtifactThroughTheRealRunner:
    def test_registry_resolved_run_writes_the_artifact_next_to_the_spec(
        self, tmp_path: Path
    ) -> None:
        store = StateStore(tmp_path / "state.db")
        ctx = _ctx(tmp_path)
        run, _ = _run(_pipeline(), ctx, store, _plan())

        assert run.status == RunStatus.COMPLETED
        artifact = _artifact_path(tmp_path)
        assert artifact.is_file(), "the shipped handler wrote no artifact through the real runner"
        body = _yaml_body(artifact)
        assert [c["component"] for c in body["components"]] == ["auth", "billing"]

    def test_proposed_dal_survives_as_a_string_end_to_end(self, tmp_path: Path) -> None:
        """FR-7 data half. A python-mode dump raises RepresenterError here (D1)."""
        store = StateStore(tmp_path / "state.db")
        run, _ = _run(_pipeline(), _ctx(tmp_path), store, _plan())

        assert run.status == RunStatus.COMPLETED
        body = _yaml_body(_artifact_path(tmp_path))
        dals = [c["proposed_dal"] for c in body["components"]]
        assert dals == ["DAL_B", "DAL_D"]
        assert all(isinstance(d, str) for d in dals)

    def test_hydrated_context_matches_the_on_disk_artifact(self, tmp_path: Path) -> None:
        """FR-5's central claim, proven through the runner's own hydration hook.

        The unit suite calls ``hydrate_plan_context`` by hand, which proves nothing about
        production wiring. AD-4 freezes both halves of this seam, so they must agree.
        """
        store = StateStore(tmp_path / "state.db")
        ctx = _ctx(tmp_path)
        run, _ = _run(_pipeline(), ctx, store, _plan())

        assert run.status == RunStatus.COMPLETED
        assert ctx.plan_context.decomposition is not None, (
            "the runner hook never hydrated context.plan_context.decomposition"
        )
        in_memory = json.loads(ctx.plan_context.decomposition)
        on_disk = _yaml_body(_artifact_path(tmp_path))
        assert in_memory == on_disk

    def test_decomposition_path_points_at_the_real_file(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path / "state.db")
        run, _ = _run(_pipeline(), _ctx(tmp_path), store, _plan())

        output = run.step_records[0].result.output
        assert "decomposition_path" in output
        assert Path(output["decomposition_path"]).is_file()
        assert Path(output["decomposition_path"]) == _artifact_path(tmp_path)


# ---------------------------------------------------------------------------
# Persistence seams — real SQLite
# ---------------------------------------------------------------------------


class TestPersistenceSeams:
    def test_output_survives_the_state_store_round_trip(self, tmp_path: Path) -> None:
        """A reload from disk is a genuinely different object graph."""
        store = StateStore(tmp_path / "state.db")
        run, _ = _run(_pipeline(), _ctx(tmp_path), store, _plan())

        reloaded = store.load_run(run.run_id)
        assert reloaded is not None
        result = reloaded.step_records[0].result
        assert result.status == StepStatus.PASSED
        assert result.output["decomposition_path"] == str(_artifact_path(tmp_path))
        assert [c["component"] for c in result.output["plan"]["components"]] == ["auth", "billing"]

    def test_lineage_row_written_to_real_sqlite_with_the_artifact_uuid(
        self, tmp_path: Path, lineage_db: Database
    ) -> None:
        """The unit suite mocks ``context.db``; only this proves a row lands in the schema."""
        store = StateStore(tmp_path / "state.db")
        run, _ = _run(_pipeline(), _ctx(tmp_path, db=lineage_db), store, _plan())
        assert run.status == RunStatus.COMPLETED

        tag_uuid = extract_artifact_uuid(_artifact_path(tmp_path).read_text(encoding="utf-8"))
        assert tag_uuid, "the artifact carries no uuid tag to correlate lineage against"

        with sqlite3.connect(tmp_path / "specweaver.db") as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT artifact_id, parent_id, event_type FROM flow_artifact_events"
            ).fetchall()
        assert len(rows) == 1
        assert rows[0]["event_type"] == "generated_decomposition"
        assert rows[0]["artifact_id"] == tag_uuid
        assert rows[0]["parent_id"] is None

    def test_resume_rehydrates_decomposition_matching_the_artifact(self, tmp_path: Path) -> None:
        """CB-1 and SF-01 CB-3 together, across two sessions and two RunContexts."""
        store = StateStore(tmp_path / "state.db")
        pipeline = _pipeline(hitl=True)
        first = _ctx(tmp_path)
        run, _ = _run(pipeline, first, store, _plan())
        assert run.status == RunStatus.PARKED

        # Session 2: a fresh context that has never seen the plan in memory.
        second = _ctx(tmp_path)
        assert second.plan_context.decomposition is None
        reloaded = store.load_run(run.run_id)
        from specweaver.core.flow.engine.hydration import rehydrate_from_records

        rehydrate_from_records(pipeline, reloaded, second)

        assert second.plan_context.decomposition is not None
        assert json.loads(second.plan_context.decomposition) == _yaml_body(_artifact_path(tmp_path))


# ---------------------------------------------------------------------------
# Boundary
# ---------------------------------------------------------------------------


class TestArtifactBoundaries:
    def test_rerun_reuses_the_artifact_uuid_across_two_real_runs(
        self, tmp_path: Path, lineage_db: Database
    ) -> None:
        """Lineage identity is stable for the same logical artifact (R-6)."""
        store = StateStore(tmp_path / "state.db")
        _run(_pipeline(), _ctx(tmp_path, db=lineage_db), store, _plan())
        first_uuid = extract_artifact_uuid(_artifact_path(tmp_path).read_text(encoding="utf-8"))

        _run(_pipeline(), _ctx(tmp_path, db=lineage_db), store, _plan())
        second_uuid = extract_artifact_uuid(_artifact_path(tmp_path).read_text(encoding="utf-8"))

        assert first_uuid == second_uuid, "a re-decomposition minted a new lineage identity"

        with sqlite3.connect(tmp_path / "specweaver.db") as conn:
            ids = [r[0] for r in conn.execute("SELECT artifact_id FROM flow_artifact_events")]
        assert ids == [first_uuid, first_uuid]

    def test_low_coverage_fails_the_run_and_writes_nothing(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path / "state.db")
        run, _ = _run(_pipeline(), _ctx(tmp_path), store, _plan(coverage=0.5))

        assert run.status == RunStatus.FAILED
        assert not _artifact_path(tmp_path).exists()


# ---------------------------------------------------------------------------
# Graceful degradation — a real filesystem failure, not a patched writer
# ---------------------------------------------------------------------------


class TestWriteFailureDegradation:
    def test_unwritable_artifact_path_fails_the_run_but_keeps_the_plan(
        self, tmp_path: Path
    ) -> None:
        """D6: fail loud, never discard an expensive LLM decomposition.

        The obstruction is real — a *directory* occupying the artifact's filename, so the genuine
        ``write_text`` raises ``OSError`` on every platform. The unit suite patches the writer,
        which cannot show that the runner records the retained plan.
        """
        store = StateStore(tmp_path / "state.db")
        ctx = _ctx(tmp_path)
        _artifact_path(tmp_path).mkdir(parents=True, exist_ok=True)

        run, _ = _run(_pipeline(), ctx, store, _plan())

        assert run.status == RunStatus.FAILED
        record = run.step_records[0]
        assert record.result.status == StepStatus.FAILED
        assert "decomposition artifact" in (record.result.error_message or "")
        # The plan is retained so a resume can re-persist without another LLM round.
        assert [c["component"] for c in record.result.output["plan"]["components"]] == [
            "auth",
            "billing",
        ]

    def test_failed_write_does_not_hydrate_the_seam(self, tmp_path: Path) -> None:
        """A FAILED result must not leave a half-truth in context.plan_context.decomposition."""
        store = StateStore(tmp_path / "state.db")
        ctx = _ctx(tmp_path)
        _artifact_path(tmp_path).mkdir(parents=True, exist_ok=True)

        _run(_pipeline(), ctx, store, _plan())
        assert ctx.plan_context.decomposition is None


# ---------------------------------------------------------------------------
# Pre-commit Phase 3 additions (CB-1 gate, 2026-07-26) — T1 and A1
# ---------------------------------------------------------------------------


class TestTelemetryFailureIsNotFatal:
    """T1: a lineage-DB failure must never discard a decomposition that is already on disk.

    D6 says an expensive LLM decomposition is never thrown away on a persistence failure. That was
    implemented for the artifact write and NOT for the telemetry call immediately after it, which
    sits outside the guard — so an unusable telemetry DB turned a successful decomposition into an
    ERROR with no plan in the output.
    """

    def test_unusable_lineage_db_still_completes_with_the_artifact_and_plan(
        self, tmp_path: Path
    ) -> None:
        # A Database whose file was never bootstrapped: flow_artifact_events does not exist.
        broken = Database(tmp_path / "never-bootstrapped.db")
        store = StateStore(tmp_path / "state.db")
        ctx = _ctx(tmp_path, db=broken)

        run, _ = _run(_pipeline(), ctx, store, _plan())

        assert run.status == RunStatus.COMPLETED, (
            "a telemetry failure must not fail a decomposition whose artifact is already durable"
        )
        assert _artifact_path(tmp_path).is_file()
        record = run.step_records[0]
        assert record.result.status == StepStatus.PASSED
        assert [c["component"] for c in record.result.output["plan"]["components"]] == [
            "auth",
            "billing",
        ]

    def test_unusable_lineage_db_still_hydrates_the_seam(self, tmp_path: Path) -> None:
        broken = Database(tmp_path / "never-bootstrapped.db")
        store = StateStore(tmp_path / "state.db")
        ctx = _ctx(tmp_path, db=broken)

        _run(_pipeline(), ctx, store, _plan())

        assert ctx.plan_context.decomposition is not None
        assert json.loads(ctx.plan_context.decomposition) == _yaml_body(_artifact_path(tmp_path))


class TestSeamKeyIsOneSymbol:
    """A1: the nesting key was a literal duplicated in decompose.py and hydration.py.

    Two string literals that must agree, with nothing forcing them to, is not a frozen seam.
    """

    def test_writer_and_hydration_agree_through_a_shared_constant(self, tmp_path: Path) -> None:
        from specweaver.core.flow.engine.hydration import DECOMPOSITION_PLAN_KEY

        store = StateStore(tmp_path / "state.db")
        ctx = _ctx(tmp_path)
        run, _ = _run(_pipeline(), ctx, store, _plan())

        output = run.step_records[0].result.output
        assert DECOMPOSITION_PLAN_KEY in output, "the writer does not use the shared seam constant"
        assert json.loads(ctx.plan_context.decomposition) == output[DECOMPOSITION_PLAN_KEY], (
            "hydration did not read the key the writer wrote"
        )


# ---------------------------------------------------------------------------
# CB-2 — stub component specs (FR-6)
# ---------------------------------------------------------------------------


def _stub(tmp_path: Path, component: str) -> Path:
    """D7: stubs land next to the spec, NOT in project_path/'specs'."""
    return tmp_path / "specs" / f"{component}_spec.md"


def _scaffold_template(tmp_path: Path, body: str | None = None) -> Path:
    tpl = tmp_path / ".specweaver" / "templates" / "component_spec.md"
    tpl.parent.mkdir(parents=True, exist_ok=True)
    tpl.write_text(
        body
        or (
            "# {{ component_name }} - Component Spec\n\n"
            '> **Parent Feature**: {{ parent_feature | default("N/A") }}\n\n'
            '## 1. Purpose\n\n{{ purpose | default("TODO") }}\n'
        ),
        encoding="utf-8",
    )
    return tpl


class TestStubComponentSpecs:
    """FR-6: the DAG becomes tangible spec files a user can carry into `sw implement`."""

    def test_one_stub_written_per_component_next_to_the_spec(self, tmp_path: Path) -> None:
        _scaffold_template(tmp_path)
        run, _ = _run(_pipeline(), _ctx(tmp_path), StateStore(tmp_path / "s.db"), _plan())

        assert run.status == RunStatus.COMPLETED
        assert _stub(tmp_path, "auth").is_file()
        assert _stub(tmp_path, "billing").is_file()

    def test_template_is_rendered_not_copied(self, tmp_path: Path) -> None:
        """A verbatim copy would leave literal Jinja in the user's spec file."""
        _scaffold_template(tmp_path)
        _run(_pipeline(), _ctx(tmp_path), StateStore(tmp_path / "s.db"), _plan())

        text = _stub(tmp_path, "auth").read_text(encoding="utf-8")
        assert "{{" not in text and "}}" not in text
        assert "auth" in text
        assert "Handles login and token issuance." in text  # purpose seeded from description

    def test_missing_template_falls_back_to_a_local_skeleton(self, tmp_path: Path) -> None:
        """Unscaffolded projects have no .specweaver/templates — R-3."""
        run, _ = _run(_pipeline(), _ctx(tmp_path), StateStore(tmp_path / "s.db"), _plan())

        assert run.status == RunStatus.COMPLETED
        text = _stub(tmp_path, "auth").read_text(encoding="utf-8")
        assert "auth" in text
        assert "{{" not in text

    def test_existing_spec_is_never_overwritten(self, tmp_path: Path) -> None:
        _scaffold_template(tmp_path)
        existing = _stub(tmp_path, "auth")
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text("# hand-written, do not clobber\n", encoding="utf-8")
        before = existing.read_bytes()

        _run(_pipeline(), _ctx(tmp_path), StateStore(tmp_path / "s.db"), _plan())

        assert existing.read_bytes() == before

    def test_created_and_skipped_are_reported_not_silent(self, tmp_path: Path) -> None:
        """R/B C1.2: a skip must be visible, or stale stubs look authored."""
        _scaffold_template(tmp_path)
        _stub(tmp_path, "auth").parent.mkdir(parents=True, exist_ok=True)
        _stub(tmp_path, "auth").write_text("# mine\n", encoding="utf-8")

        run, _ = _run(_pipeline(), _ctx(tmp_path), StateStore(tmp_path / "s.db"), _plan())

        stubs = run.step_records[0].result.output["component_specs"]
        assert stubs["created"] == ["billing"]
        assert stubs["skipped"] == ["auth"]

    def test_zero_component_plan_writes_no_stubs(self, tmp_path: Path) -> None:
        from specweaver.workflows.planning.decomposition import DecompositionPlan

        empty = DecompositionPlan(
            feature_spec=f"specs/{SPEC_STEM}.md",
            components=[],
            integration_seams=[],
            build_sequence=[],
            coverage_score=1.0,
            alignment_notes=[],
            timestamp="2026-07-26T00:00:00Z",
        )
        run, _ = _run(_pipeline(), _ctx(tmp_path), StateStore(tmp_path / "s.db"), empty)

        assert run.status == RunStatus.COMPLETED
        assert run.step_records[0].result.output["component_specs"]["created"] == []
        # The feature spec itself matches *_spec.md, so assert on the exact set.
        written = {p.name for p in (tmp_path / "specs").glob("*_spec.md")}
        assert written == {f"{SPEC_STEM}.md"}

    def test_artifact_still_written_when_stubs_are_impossible(self, tmp_path: Path) -> None:
        """A stub failure must not discard the durable artifact — the T1 lesson."""
        _scaffold_template(tmp_path)
        # Occupy every stub filename with a directory so write_text raises.
        for name in ("auth", "billing"):
            _stub(tmp_path, name).mkdir(parents=True, exist_ok=True)

        run, _ = _run(_pipeline(), _ctx(tmp_path), StateStore(tmp_path / "s.db"), _plan())

        assert run.status == RunStatus.COMPLETED
        assert _artifact_path(tmp_path).is_file()
        assert sorted(run.step_records[0].result.output["component_specs"]["failed"]) == [
            "auth",
            "billing",
        ]


class TestStubNameSafety:
    """NFR-5: LLM-authored names reach the filesystem — validate before ANY write."""

    def test_traversal_name_writes_nothing_outside_the_spec_dir(self, tmp_path: Path) -> None:
        from specweaver.commons.enums.dal import DALLevel
        from specweaver.workflows.planning.decomposition import ComponentChange, DecompositionPlan

        hostile = DecompositionPlan(
            feature_spec=f"specs/{SPEC_STEM}.md",
            components=[
                ComponentChange(
                    component="../../../etc/pwned",
                    exists=False,
                    change_nature="new_interface",
                    description="malicious",
                    proposed_dal=DALLevel.DAL_B,
                    dependencies=[],
                    target_modules=[],
                    confidence=50,
                )
            ],
            integration_seams=[],
            build_sequence=["../../../etc/pwned"],
            coverage_score=1.0,
            alignment_notes=[],
            timestamp="2026-07-26T00:00:00Z",
        )
        _scaffold_template(tmp_path)
        run, _ = _run(_pipeline(), _ctx(tmp_path), StateStore(tmp_path / "s.db"), hostile)

        stubs = run.step_records[0].result.output["component_specs"]
        assert stubs["rejected"] == ["../../../etc/pwned"]
        assert stubs["created"] == []

        # The spec lives at tmp_path/specs/, so "../../../etc/pwned" resolves to
        # tmp_path.parent/etc/pwned. Assert on that EXACT file, not on the `etc` directory:
        # tmp_path.parent is pytest's session root, shared with every other test, so asserting the
        # directory is absent passes or fails for reasons that have nothing to do with this claim
        # (it green-lit in isolation and failed in the full suite when an unrelated test made one).
        assert not (tmp_path.parent / "etc" / "pwned_spec.md").exists()
        assert not (tmp_path / "etc").exists()
        # And nothing landed beside the spec except the feature spec and the artifact.
        assert {p.name for p in (tmp_path / "specs").iterdir()} == {
            f"{SPEC_STEM}.md",
            f"{SPEC_STEM}_decomposition.yaml",
        }


class TestStubRenderingDefaults:
    """A component with no description must get the template's placeholder, never "None"."""

    def test_missing_description_renders_the_placeholder_not_none(self, tmp_path: Path) -> None:
        from specweaver.commons.enums.dal import DALLevel
        from specweaver.workflows.planning.decomposition import ComponentChange, DecompositionPlan

        plan = DecompositionPlan(
            feature_spec=f"specs/{SPEC_STEM}.md",
            components=[
                ComponentChange(
                    component="auth",
                    exists=False,
                    change_nature="new_interface",
                    description="",
                    proposed_dal=DALLevel.DAL_B,
                    dependencies=[],
                    target_modules=[],
                    confidence=50,
                )
            ],
            integration_seams=[],
            build_sequence=["auth"],
            coverage_score=1.0,
            alignment_notes=[],
            timestamp="2026-07-26T00:00:00Z",
        )
        _scaffold_template(tmp_path)
        _run(_pipeline(), _ctx(tmp_path), StateStore(tmp_path / "s.db"), plan)

        text = _stub(tmp_path, "auth").read_text(encoding="utf-8")
        assert "None" not in text
        assert "TODO" in text


# ---------------------------------------------------------------------------
# CB-3 — FR-7 human-readable summary (D2: handler-owned, no display.py change)
# ---------------------------------------------------------------------------


class TestDalSummary:
    """FR-7: `proposed_dal` is carried in a summary the handler emits itself.

    No park surface renders step output today (R-4), so D2 puts the burden on the handler and
    leaves rich rendering to SF-03's CLI journey. What CB-3 owes is that the data and the
    human-readable form both exist in `StepResult.output`.
    """

    def test_summary_names_every_component_and_its_dal(self, tmp_path: Path) -> None:
        run, _ = _run(_pipeline(), _ctx(tmp_path), StateStore(tmp_path / "s.db"), _plan())

        summary = run.step_records[0].result.output["summary"]
        assert "auth" in summary and "DAL_B" in summary
        assert "billing" in summary and "DAL_D" in summary

    def test_summary_names_the_artifact_path_for_review_before_resuming(
        self, tmp_path: Path
    ) -> None:
        """NFR-7: the human must be able to find the artifact from the park."""
        run, _ = _run(_pipeline(), _ctx(tmp_path), StateStore(tmp_path / "s.db"), _plan())

        assert _artifact_path(tmp_path).name in run.step_records[0].result.output["summary"]

    def test_summary_reports_the_stub_outcome(self, tmp_path: Path) -> None:
        _scaffold_template(tmp_path)
        run, _ = _run(_pipeline(), _ctx(tmp_path), StateStore(tmp_path / "s.db"), _plan())

        summary = run.step_records[0].result.output["summary"]
        assert "2 created" in summary

    def test_summary_survives_the_sqlite_round_trip(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path / "s.db")
        run, _ = _run(_pipeline(), _ctx(tmp_path), store, _plan())

        reloaded = store.load_run(run.run_id)
        assert "DAL_B" in reloaded.step_records[0].result.output["summary"]


class TestCarriedForwardGaps:
    """The two gaps CB-2's walkthrough recorded rather than buried."""

    def test_a_component_listed_twice_is_created_once_then_skipped(self, tmp_path: Path) -> None:
        from specweaver.commons.enums.dal import DALLevel
        from specweaver.workflows.planning.decomposition import ComponentChange, DecompositionPlan

        def _c(desc: str) -> ComponentChange:
            return ComponentChange(
                component="auth",
                exists=False,
                change_nature="new_interface",
                description=desc,
                proposed_dal=DALLevel.DAL_B,
                dependencies=[],
                target_modules=[],
                confidence=90,
            )

        dupes = DecompositionPlan(
            feature_spec=f"specs/{SPEC_STEM}.md",
            components=[_c("first"), _c("second")],
            integration_seams=[],
            build_sequence=["auth"],
            coverage_score=1.0,
            alignment_notes=[],
            timestamp="2026-07-26T00:00:00Z",
        )
        _scaffold_template(tmp_path)
        run, _ = _run(_pipeline(), _ctx(tmp_path), StateStore(tmp_path / "s.db"), dupes)

        stubs = run.step_records[0].result.output["component_specs"]
        assert stubs["created"] == ["auth"]
        assert stubs["skipped"] == ["auth"]
        # The first description wins; the duplicate never overwrites it.
        assert "first" in _stub(tmp_path, "auth").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# SF-03 CB-2 — R-10: a component name that collides with the feature spec
# ---------------------------------------------------------------------------


class TestFeatureSpecNameCollision:
    """A component whose stub path IS the feature spec must not be reported as `skipped`.

    `spec_path.with_name(f"{name}_spec.md")` for a component named `<feature>_feature` produces
    `<feature>_feature_spec.md` — the feature spec itself. Never-overwrite protects the file, but
    reporting it as `skipped` tells the user a component spec already exists where their own
    feature spec sits, and no stub was produced. Different cause, different remedy: `rejected`
    means fix the LLM output, `collided` means rename the component.
    """

    def _colliding_plan(self):
        from specweaver.commons.enums.dal import DALLevel
        from specweaver.workflows.planning.decomposition import ComponentChange, DecompositionPlan

        def _c(name: str) -> ComponentChange:
            return ComponentChange(
                component=name,
                exists=False,
                change_nature="new_interface",
                description=f"{name} does things.",
                proposed_dal=DALLevel.DAL_B,
                dependencies=[],
                target_modules=[],
                confidence=80,
            )

        # SPEC_STEM is "onboarding_feature_spec"; a component named "onboarding_feature"
        # therefore targets "onboarding_feature_spec.md" — the feature spec.
        return DecompositionPlan(
            feature_spec=f"specs/{SPEC_STEM}.md",
            components=[_c("onboarding_feature"), _c("auth")],
            integration_seams=[],
            build_sequence=["onboarding_feature", "auth"],
            coverage_score=1.0,
            alignment_notes=[],
            timestamp="2026-07-27T00:00:00Z",
        )

    def test_collision_is_reported_distinctly_not_as_skipped(self, tmp_path: Path) -> None:
        _scaffold_template(tmp_path)
        run, _ = _run(
            _pipeline(), _ctx(tmp_path), StateStore(tmp_path / "s.db"), self._colliding_plan()
        )

        stubs = run.step_records[0].result.output["component_specs"]
        assert stubs["collided"] == ["onboarding_feature"]
        assert "onboarding_feature" not in stubs["skipped"]
        assert "onboarding_feature" not in stubs["created"]

    def test_the_feature_spec_is_left_untouched(self, tmp_path: Path) -> None:
        _scaffold_template(tmp_path)
        ctx = _ctx(tmp_path)
        before = ctx.spec_path.read_bytes()

        _run(_pipeline(), ctx, StateStore(tmp_path / "s.db"), self._colliding_plan())

        assert ctx.spec_path.read_bytes() == before

    def test_other_components_are_unaffected(self, tmp_path: Path) -> None:
        """One colliding name must not abort the rest of the batch."""
        _scaffold_template(tmp_path)
        run, _ = _run(
            _pipeline(), _ctx(tmp_path), StateStore(tmp_path / "s.db"), self._colliding_plan()
        )

        stubs = run.step_records[0].result.output["component_specs"]
        assert stubs["created"] == ["auth"]
        assert _stub(tmp_path, "auth").is_file()

    def test_the_report_always_carries_every_bucket(self, tmp_path: Path) -> None:
        """A consumer reading `collided` must not have to guess whether the key exists."""
        _scaffold_template(tmp_path)
        run, _ = _run(_pipeline(), _ctx(tmp_path), StateStore(tmp_path / "s.db"), _plan())

        stubs = run.step_records[0].result.output["component_specs"]
        assert set(stubs) == {"created", "skipped", "rejected", "failed", "collided"}

    def test_the_summary_surfaces_the_collision(self, tmp_path: Path) -> None:
        _scaffold_template(tmp_path)
        run, _ = _run(
            _pipeline(), _ctx(tmp_path), StateStore(tmp_path / "s.db"), self._colliding_plan()
        )

        assert "collided" in run.step_records[0].result.output["summary"]
