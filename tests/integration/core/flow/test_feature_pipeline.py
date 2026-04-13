# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests — Feature pipeline (C5↔C6↔C7↔C8).

Tests the feature_decomposition pipeline definition, flow engine
execution with DECOMPOSE steps, and ValidateSpecHandler kind=feature
wiring.  Only the LLM adapter is mocked.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from specweaver.core.flow.handlers import (
    RunContext,
    StepHandler,
    StepHandlerRegistry,
    ValidateSpecHandler,
    _now_iso,
)
from specweaver.core.flow.models import (
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.runner import PipelineRunner
from specweaver.core.flow.state import RunStatus, StepResult, StepStatus
from specweaver.core.flow.store import StateStore

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PIPELINES_DIR = (
    Path(__file__).resolve().parents[4] / "src" / "specweaver" / "workflows" / "pipelines"
)


# ---------------------------------------------------------------------------
# Fixture specs
# ---------------------------------------------------------------------------

_FEATURE_SPEC = """\
# User Onboarding — Feature Spec

> **Status**: DRAFT

---

## Intent

The system enables new users to register, verify their email, and complete
their profile in a single guided flow.

---

## Value Proposition

Users can onboard in under 2 minutes.

---

## Done Definition

- [ ] All acceptance criteria pass
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _AlwaysPassHandler:
    """Handler that always returns PASSED."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        return StepResult(
            status=StepStatus.PASSED,
            output={"verdict": "accepted"},
            started_at=started,
            completed_at=_now_iso(),
        )


class _ParamsCapturingHandler:
    """Handler that records the step.params it received."""

    def __init__(self) -> None:
        self.captured_params: dict[str, Any] = {}

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        self.captured_params = dict(step.params)
        started = _now_iso()
        return StepResult(
            status=StepStatus.PASSED,
            output={"params_captured": True},
            started_at=started,
            completed_at=_now_iso(),
        )


def _make_context(project: Path, spec_path: Path | None = None) -> RunContext:
    """Create a RunContext from a project path."""
    if spec_path is None:
        spec_path = project / "specs" / "feature.md"
    return RunContext(project_path=project, spec_path=spec_path)


def _make_store(project: Path) -> StateStore:
    """Create a StateStore in the project directory."""
    return StateStore(project / ".specweaver" / "pipeline_state.db")


def _registry_with(*handlers: tuple[StepAction, StepTarget, StepHandler]) -> StepHandlerRegistry:
    """Build a registry with custom handlers."""
    reg = StepHandlerRegistry()
    for action, target, handler in handlers:
        reg.register(action, target, handler)
    return reg


# ---------------------------------------------------------------------------
# Pipeline YAML → Flow Engine integration
# ---------------------------------------------------------------------------


class TestFeatureDecompositionPipelineIntegration:
    """feature_decomposition.yaml can be loaded and run through the flow engine."""

    def test_pipeline_yaml_loads_and_parks_at_hitl(self, sample_project: Path) -> None:
        """Load pipeline YAML → run → PARKED at first HITL gate (draft_feature)."""
        yaml = YAML(typ="safe")
        path = PIPELINES_DIR / "feature_decomposition.yaml"
        if not path.exists():
            import pytest

            pytest.skip(f"Pipeline YAML not found: {path}")

        data = yaml.load(path)
        pipeline = PipelineDefinition.model_validate(data)

        # Register mock handlers for all steps in the pipeline
        registry = StepHandlerRegistry()
        for step in pipeline.steps:
            registry.register(step.action, step.target, _AlwaysPassHandler())

        spec = sample_project / "specs" / "feature.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(_FEATURE_SPEC, encoding="utf-8")

        ctx = _make_context(sample_project, spec)
        store = _make_store(sample_project)

        runner = PipelineRunner(pipeline, ctx, registry=registry, store=store)
        run = asyncio.run(runner.run())

        # Pipeline has HITL gates → correctly parks for human approval
        assert run.status == RunStatus.PARKED
        # State was persisted and is resumable
        reloaded = store.load_run(run.run_id)
        assert reloaded is not None
        assert reloaded.status == RunStatus.PARKED

    def test_pipeline_step_params_preserved_in_definition(self) -> None:
        """step.params (e.g. kind=feature) are preserved in the PipelineDefinition."""
        yaml = YAML(typ="safe")
        path = PIPELINES_DIR / "feature_decomposition.yaml"
        if not path.exists():
            import pytest

            pytest.skip(f"Pipeline YAML not found: {path}")

        data = yaml.load(path)
        pipeline = PipelineDefinition.model_validate(data)

        # The validate_feature step should have kind=feature in params
        val_step = pipeline.get_step("validate_feature")
        assert val_step is not None
        assert val_step.params.get("kind") == "feature"

        # All three steps should have the correct action+target combos
        combos = [(s.action, s.target) for s in pipeline.steps]
        assert (StepAction.DRAFT, StepTarget.FEATURE) in combos
        assert (StepAction.VALIDATE, StepTarget.FEATURE) in combos
        assert (StepAction.DECOMPOSE, StepTarget.FEATURE) in combos


# ---------------------------------------------------------------------------
# ValidateSpecHandler with kind=feature (real validation)
# ---------------------------------------------------------------------------


class TestValidateSpecHandlerKindIntegration:
    """ValidateSpecHandler reads kind from step.params and threads it to runner."""

    def test_handler_with_kind_feature_skips_s04(self, sample_project: Path) -> None:
        """ValidateSpecHandler with kind=feature excludes S04 (dependency direction).

        With the sub-pipeline architecture, feature pipeline removes S04
        entirely rather than marking it as skipped.
        """
        spec = sample_project / "specs" / "feature.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(_FEATURE_SPEC, encoding="utf-8")

        step = PipelineStep(
            name="validate_feature",
            action=StepAction.VALIDATE,
            target=StepTarget.FEATURE,
            params={"kind": "feature"},
        )
        ctx = RunContext(project_path=sample_project, spec_path=spec)

        handler = ValidateSpecHandler()
        result = asyncio.run(handler.execute(step, ctx))

        assert result.status == StepStatus.PASSED or result.status == StepStatus.FAILED
        # S04 should NOT be in results (removed from feature pipeline)
        if result.output and "results" in result.output:
            s04 = next(
                (r for r in result.output["results"] if r["rule_id"] == "S04"),
                None,
            )
            assert s04 is None, "S04 should not be in feature pipeline results"

    def test_handler_without_kind_runs_component_defaults(self, sample_project: Path) -> None:
        """ValidateSpecHandler without kind param uses component defaults."""
        spec = sample_project / "specs" / "component.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(
            "# Component Spec\n\n## 1. Purpose\n\nDoes things.\n",
            encoding="utf-8",
        )

        step = PipelineStep(
            name="validate_spec",
            action=StepAction.VALIDATE,
            target=StepTarget.SPEC,
            # No params — no kind override
        )
        ctx = RunContext(project_path=sample_project, spec_path=spec)

        handler = ValidateSpecHandler()
        result = asyncio.run(handler.execute(step, ctx))

        # S04 should NOT be skip (no feature kind)
        if result.output and "results" in result.output:
            s04 = next(
                (r for r in result.output["results"] if r["rule_id"] == "S04"),
                None,
            )
            if s04 is not None:
                assert s04["status"] != "skip", "S04 should not skip for component"


# ---------------------------------------------------------------------------
# Flow engine with DECOMPOSE step
# ---------------------------------------------------------------------------


class TestDecomposeStepFlowIntegration:
    """DECOMPOSE+FEATURE step runs through the flow engine."""

    def test_decompose_step_with_mock_handler(self, sample_project: Path) -> None:
        """DECOMPOSE+FEATURE step can be executed through the pipeline runner."""
        pipeline = PipelineDefinition(
            name="decompose_test",
            steps=[
                PipelineStep(
                    name="draft_feature",
                    action=StepAction.DRAFT,
                    target=StepTarget.FEATURE,
                ),
                PipelineStep(
                    name="validate_feature",
                    action=StepAction.VALIDATE,
                    target=StepTarget.FEATURE,
                    params={"kind": "feature"},
                ),
                PipelineStep(
                    name="decompose",
                    action=StepAction.DECOMPOSE,
                    target=StepTarget.FEATURE,
                ),
            ],
        )

        spec = sample_project / "specs" / "feature.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(_FEATURE_SPEC, encoding="utf-8")

        ctx = _make_context(sample_project, spec)
        store = _make_store(sample_project)
        registry = _registry_with(
            (StepAction.DRAFT, StepTarget.FEATURE, _AlwaysPassHandler()),
            (StepAction.VALIDATE, StepTarget.FEATURE, _AlwaysPassHandler()),
            (StepAction.DECOMPOSE, StepTarget.FEATURE, _AlwaysPassHandler()),
        )

        runner = PipelineRunner(pipeline, ctx, registry=registry, store=store)
        run = asyncio.run(runner.run())

        assert run.status == RunStatus.COMPLETED
        assert len(run.step_records) == 3
        assert all(r.status == StepStatus.PASSED for r in run.step_records)

    def test_three_step_pipeline_state_persistence(self, sample_project: Path) -> None:
        """3-step feature pipeline persists all state and audit events."""
        pipeline = PipelineDefinition(
            name="feature_full",
            steps=[
                PipelineStep(
                    name="draft_feature",
                    action=StepAction.DRAFT,
                    target=StepTarget.FEATURE,
                ),
                PipelineStep(
                    name="validate_feature",
                    action=StepAction.VALIDATE,
                    target=StepTarget.FEATURE,
                ),
                PipelineStep(
                    name="decompose",
                    action=StepAction.DECOMPOSE,
                    target=StepTarget.FEATURE,
                ),
            ],
        )

        spec = sample_project / "specs" / "feature.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(_FEATURE_SPEC, encoding="utf-8")

        ctx = _make_context(sample_project, spec)
        store = _make_store(sample_project)
        registry = _registry_with(
            (StepAction.DRAFT, StepTarget.FEATURE, _AlwaysPassHandler()),
            (StepAction.VALIDATE, StepTarget.FEATURE, _AlwaysPassHandler()),
            (StepAction.DECOMPOSE, StepTarget.FEATURE, _AlwaysPassHandler()),
        )

        runner = PipelineRunner(pipeline, ctx, registry=registry, store=store)
        run = asyncio.run(runner.run())

        assert run.status == RunStatus.COMPLETED

        # State persisted
        reloaded = store.load_run(run.run_id)
        assert reloaded is not None
        assert reloaded.status == RunStatus.COMPLETED

        # Audit log has all events
        log = store.get_audit_log(run.run_id)
        events = [entry["event"] for entry in log]
        assert events.count("step_started") == 3
        assert events.count("step_completed") == 3
