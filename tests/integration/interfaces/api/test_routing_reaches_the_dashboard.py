# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A router jump the engine made is what a reader sees on the dashboard.

Proves: C-FLOW-02 FR-5, E-UI-02 FR-1

US-6 holds two closed capabilities and the seam between them was never crossed by a test. Each side
was proven alone:

* `test_runner_routing.py` asserts the engine writes a `step_routed` row to the audit log.
* `test_ui.py` asserts the dashboard lists the runs the store holds.

Neither asserts that the row the engine writes is the thing the page renders — and FR-5's stated
outcome is exactly that: *"the StateStore logs the parsed condition and target destination so the
Dashboard can visualize"*. A test that stops at the row proves the write; the reader still cannot
see it. Between them sits the `flow_audit_log` table, a schema both sides agree on and neither
checks.

Nothing is mocked. A real `PipelineRunner` over a real SQLite `StateStore`, read back through the
real HTTP app.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from starlette.testclient import TestClient

from specweaver.core.config.database import Database
from specweaver.core.flow.engine.models import (
    PipelineDefinition,
    PipelineStep,
    RouterDefinition,
    RouterRule,
    RuleOperator,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus, StepResult, StepStatus
from specweaver.core.flow.engine.store import StateStore
from specweaver.core.flow.handlers.base import StepHandler
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.interfaces.api.app import create_app

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

#: The step the router must jump over. Named, because "a step did not run" is only meaningful when
#: the test can say which one and the page can be searched for it.
SKIPPED_STEP = "decompose"


class _RecordingHandler(StepHandler):
    """A handler that reports whether it ran. No LLM, no I/O — the router is the subject."""

    def __init__(self, output: dict[str, Any] | None = None) -> None:
        self._output = output or {}
        self.call_count = 0

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        self.call_count += 1
        return StepResult(
            status=StepStatus.PASSED,
            output=self._output,
            started_at="2026-08-19T00:00:00Z",
            completed_at="2026-08-19T00:00:01Z",
        )


def _pipeline() -> PipelineDefinition:
    """Three steps where the first routes past the second."""
    return PipelineDefinition(
        name="routing_reaches_the_dashboard",
        steps=[
            PipelineStep(
                name="assess",
                action=StepAction.PLAN,
                target=StepTarget.SPEC,
                router=RouterDefinition(
                    rules=[
                        RouterRule(
                            field="complexity",
                            operator=RuleOperator.EQ,
                            value="complex",
                            target=SKIPPED_STEP,
                        )
                    ],
                    default_target="generate",
                ),
            ),
            PipelineStep(name=SKIPPED_STEP, action=StepAction.DECOMPOSE, target=StepTarget.FEATURE),
            PipelineStep(name="generate", action=StepAction.GENERATE, target=StepTarget.CODE),
        ],
    )


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the app's own path resolution at a throwaway root.

    The dashboard resolves its store through `state_db_path()` rather than taking one, so the seam
    can only be driven by making that function answer with the store the engine wrote to. Handing
    the test's own `StateStore` to the app instead would prove the two objects agree in memory,
    which is not the claim.
    """
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def client(data_dir: Path) -> TestClient:
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database

    bootstrap_database(str(data_dir / "test.db"))
    return TestClient(create_app(db=Database(db_path=data_dir / "test.db")))


@pytest.fixture
async def routed_run(data_dir: Path, tmp_path: Path) -> tuple[str, _RecordingHandler]:
    """Run a real pipeline whose router skips a step, against the store the dashboard reads."""
    project = tmp_path / "project"
    project.mkdir(parents=True, exist_ok=True)
    (project / "spec.md").touch()

    skipped = _RecordingHandler()
    registry = StepHandlerRegistry()
    registry.register(StepAction.PLAN, StepTarget.SPEC, _RecordingHandler({"complexity": "simple"}))
    registry.register(StepAction.DECOMPOSE, StepTarget.FEATURE, skipped)
    registry.register(StepAction.GENERATE, StepTarget.CODE, _RecordingHandler())

    runner = PipelineRunner(
        _pipeline(),
        RunContext(project_path=project, spec_path=project / "spec.md"),
        registry=registry,
        store=StateStore(data_dir / "pipeline_state.db"),
    )
    run = await runner.run()
    assert run.status == RunStatus.COMPLETED, "the run must finish, or the page has nothing to show"
    return run.run_id, skipped


async def test_the_router_actually_skipped_the_step(
    routed_run: tuple[str, _RecordingHandler],
) -> None:
    """The premise. Without it the assertions below could pass over a run that routed nowhere."""
    _, skipped = routed_run

    assert skipped.call_count == 0


async def test_the_run_reaches_the_dashboard_list(
    client: TestClient, routed_run: tuple[str, _RecordingHandler]
) -> None:
    """E-UI-02 FR-1 across the seam: the run the ENGINE wrote, not one the test inserted."""
    run_id, _ = routed_run

    body = client.get("/dashboard/runs").text

    assert run_id in body


async def test_the_routing_event_is_rendered_on_the_run_page(
    client: TestClient, routed_run: tuple[str, _RecordingHandler]
) -> None:
    """C-FLOW-02 FR-5's stated outcome: the audit row is visible to a reader.

    Asserting the step name as well as the event is deliberate. `step_routed` alone would also be
    satisfied by a page that printed the event name from a constant, and the row's whole value is
    saying WHICH step the pipeline left by.
    """
    run_id, _ = routed_run

    body = client.get(f"/dashboard/runs/{run_id}").text

    assert "step_routed" in body
    assert "assess" in body
