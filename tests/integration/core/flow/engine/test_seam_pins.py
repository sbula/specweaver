# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Seam pin — the D-INTL-03 plan bridge, driven by production wiring (INT-US-21 FR-9(b)).

`D-INTL-03` shipped `PlanSpecHandler`, and `GenerateCodeHandler` enriches its prompt from
``context.plan``. Nothing connected the two: ``RunContext.plan`` was documented as
"(set by runner hook)" with **zero writes anywhere in src/** until SF-01 CB-2 added
``hydrate_plan_context``.

The existing coverage does not close that gap. ``test_planning_integration.py`` proves
``PlanSpecHandler`` writes a loadable ``_plan.yaml`` (I8) and, separately, that a
**hand-seeded** ``RunContext(plan=...)`` reaches the generator (I9/I10). Both halves pass while the
bridge between them is missing — which is exactly the state the repo was in for months. Seeding the
field by hand proves the consumer works; it proves nothing about whether anything in production
ever sets it.

This pins the missing middle: a real `plan+spec` step writes a real artifact, the real runner hook
reads it, and the value visible at the next step is asserted to be **the content of that file on
disk**.

Scope, stated so this is not mistaken for more than it is: the generate step is a capture double,
so this proves *the hook delivers*, not *the generator consumes* — that half is I9/I10's job and is
already covered. The equality assertion against the on-disk artifact is what stops the capture
handler from being a self-fulfilling stub (vacuous-proof pattern 2).

FR-9(a) — a decompose→orchestrate fan-out pin freezing the seam for `C-FLOW-12` — was **descoped**
on 2026-07-26: that capability does not exist yet, so the pin would have frozen a guess. See the
design's FR-9 row.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from specweaver.core.flow.engine.models import (
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus, StepResult, StepStatus
from specweaver.core.flow.engine.store import StateStore
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.generation import PlanSpecHandler
from specweaver.core.flow.handlers.registry import StepHandlerRegistry


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text
        self.content = text


class _FakeLLM:
    """Stands in for the paid API only. Everything downstream of it is real."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self._calls = 0

    async def generate(self, messages: Any, config: Any = None) -> _FakeResponse:
        idx = min(self._calls, len(self._responses) - 1)
        self._calls += 1
        return _FakeResponse(text=self._responses[idx])


def _plan_json() -> str:
    return json.dumps(
        {
            "spec_path": "specs/login_spec.md",
            "spec_name": "Login",
            "spec_hash": "ignored",
            "timestamp": "2026-07-26T10:00:00Z",
            "file_layout": [
                {"path": "src/login.py", "action": "create", "purpose": "Login handler"}
            ],
            "architecture": {
                "module_layout": "flat",
                "dependency_direction": "downward",
                "archetype": "adapter",
            },
            "reasoning": "Simple adapter pattern.",
            "confidence": 80,
        }
    )


class _CaptureContextAtGenerate:
    """Records what the context carried when the generate step was reached."""

    def __init__(self, sink: dict[str, Any]) -> None:
        self._sink = sink

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        self._sink["plan"] = context.plan
        self._sink["decomposition"] = context.decomposition
        return StepResult(
            status=StepStatus.PASSED, output={}, started_at="1", completed_at="2"
        )


def _spec(tmp_path: Path) -> Path:
    spec = tmp_path / "login_spec.md"
    spec.write_text("# Login\n\n## 1. Purpose\n\nAuthenticates a user.\n", encoding="utf-8")
    return spec


def _plan_then_generate() -> PipelineDefinition:
    return PipelineDefinition(
        name="plan_then_generate",
        steps=[
            PipelineStep(name="plan_spec", action=StepAction.PLAN, target=StepTarget.SPEC),
            PipelineStep(name="generate_code", action=StepAction.GENERATE, target=StepTarget.CODE),
        ],
    )


def _run(tmp_path: Path, sink: dict[str, Any]):
    """Real registry, real PlanSpecHandler, real hook. Only the LLM and the generator are doubles."""
    registry = StepHandlerRegistry()
    assert isinstance(registry.get(StepAction.PLAN, StepTarget.SPEC), PlanSpecHandler), (
        "the real registry must resolve plan+spec to the real handler"
    )
    registry.register(
        StepAction.GENERATE, StepTarget.CODE, _CaptureContextAtGenerate(sink)
    )
    ctx = RunContext(
        project_path=tmp_path, spec_path=_spec(tmp_path), llm=_FakeLLM([_plan_json()])
    )
    runner = PipelineRunner(
        _plan_then_generate(), ctx, registry=registry, store=StateStore(tmp_path / "state.db")
    )
    return asyncio.run(runner.run()), ctx


@pytest.mark.integration()
class TestPlanBridgeIsHookDriven:
    """FR-9(b): `context.plan` must arrive from the runner hook, not from a fixture."""

    def test_plan_reaches_the_next_step_without_being_seeded(self, tmp_path: Path) -> None:
        sink: dict[str, Any] = {}
        run, _ = _run(tmp_path, sink)

        assert run.status == RunStatus.COMPLETED
        assert sink["plan"] is not None, (
            "context.plan was still unset at the generate step — the D-INTL-03 bridge is not wired"
        )

    def test_the_value_is_the_artifact_on_disk_not_something_invented(
        self, tmp_path: Path
    ) -> None:
        """Guards the capture handler against proving itself (vacuous-proof pattern 2)."""
        sink: dict[str, Any] = {}
        run, _ = _run(tmp_path, sink)

        plan_path = Path(run.step_records[0].result.output["plan_path"])
        assert plan_path.is_file()
        assert sink["plan"] == plan_path.read_text(encoding="utf-8")

    def test_the_plan_bridge_does_not_populate_the_decomposition_seam(
        self, tmp_path: Path
    ) -> None:
        """AD-1: two plan concepts, two fields. A `plan+spec` step must not touch the other one."""
        sink: dict[str, Any] = {}
        _run(tmp_path, sink)

        assert sink["decomposition"] is None

    def test_the_hook_is_what_sets_it(self, tmp_path: Path) -> None:
        """Remove the artifact between the steps and the field must stay unset, not stale.

        If `context.plan` were populated by anything other than reading the step's `plan_path`,
        deleting that file would not change the outcome.
        """
        sink: dict[str, Any] = {}
        registry = StepHandlerRegistry()

        class _DeleteArtifactThenCapture(_CaptureContextAtGenerate):
            pass

        # Run once to learn the artifact path, then re-run with it unlinked mid-flight.
        run, _ = _run(tmp_path, sink)
        plan_path = Path(run.step_records[0].result.output["plan_path"])
        assert plan_path.is_file()

        sink2: dict[str, Any] = {}
        registry.register(
            StepAction.GENERATE, StepTarget.CODE, _DeleteArtifactThenCapture(sink2)
        )

        class _PlanThenVanish:
            """A plan step that reports a path it has already deleted."""

            async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
                missing = tmp_path / "gone_plan.yaml"
                return StepResult(
                    status=StepStatus.PASSED,
                    output={"plan_path": str(missing)},
                    started_at="1",
                    completed_at="2",
                )

        registry.register(StepAction.PLAN, StepTarget.SPEC, _PlanThenVanish())
        ctx = RunContext(project_path=tmp_path, spec_path=_spec(tmp_path), llm=_FakeLLM([""]))
        run2 = asyncio.run(
            PipelineRunner(
                _plan_then_generate(),
                ctx,
                registry=registry,
                store=StateStore(tmp_path / "state2.db"),
            ).run()
        )

        assert run2.status == RunStatus.COMPLETED, "a missing plan file must degrade, not crash"
        assert sink2["plan"] is None
