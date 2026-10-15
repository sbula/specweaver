# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A scenario set that passed is kept with its spec's and contract's fingerprints, and made again
only when either changed.

Proves: B-FLOW-01 FR-19

A registered project with its real store; the real arbiter and the real dual handler with a
recorded spawner.

| Bucket | Case |
|---|---|
| Happy | a passing round keeps the set; the next dual run reuses it and runs the coding side only |
| Boundary | a kept record whose generated tests are gone: both sides run |
| Degradation | a broken kept record is not trusted: both sides run |
| Hostile | the spec or the contract changed since the set was kept: the scenario side runs again |
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import RunStatus, StepStatus
from specweaver.core.flow.handlers.arbiter import ArbitrateVerdictHandler
from specweaver.core.flow.handlers.dual_pipeline import ArbitrateDualPipelineHandler
from specweaver.core.flow.handlers.reviewed_spec import record_review
from specweaver.core.flow.handlers.run_context import GraphContext, RunContext, RunHandle
from tests.fixtures.db_utils import register_test_project

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[RunContext, Path]:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    bootstrap_database(str(data / "specweaver.db"))
    db = Database(data / "specweaver.db")
    root = tmp_path / "greeter"
    (root / "specs").mkdir(parents=True)
    (root / "contracts").mkdir()
    (root / "specs" / "greet_spec.md").write_text("# Greet\n\n| FR-91 | greet |\n")
    contract = root / "contracts" / "greet_contract.py"
    contract.write_text("class GreetProtocol: ...\n")
    register_test_project(db, "greeter", str(root))
    store = data / "projects" / "greeter" / "scenarios"
    (store / "generated").mkdir(parents=True)
    (store / "generated" / "test_greet_scenarios.py").write_text("def test_x():\n    pass\n")
    context = RunContext(
        project_path=root,
        spec_path=root / "specs" / "greet_spec.md",
        db=db,
        graph=GraphContext(api_contract_paths=[str(contract)]),
    )
    record_review(context)
    return context, store


async def _passing_round(context: RunContext) -> Any:
    context.run = RunHandle(run_id="r", step_name="arbitrate_verdict")
    context.feedback = {
        "scenario_test_failures": {
            "total": 3,
            "passed": 3,
            "failed": 0,
            "errors": 0,
            "failures": [],
        }
    }
    step = PipelineStep(
        name="arbitrate_verdict", action=StepAction.ARBITRATE, target=StepTarget.VERDICT
    )
    return await ArbitrateVerdictHandler().execute(step, context)


async def _sides(context: RunContext) -> list[str]:
    sides: list[str] = []

    class _Spawner:
        def spawn(self, pipeline: Any, feedback: Any = None, side: str | None = None) -> Any:
            sides.append(side or "?")

            class _Done:
                async def run(self, parent_run_id: str | None = None) -> Any:
                    class _Run:
                        status = RunStatus.COMPLETED
                        step_records: tuple[Any, ...] = ()

                    return _Run()

            return _Done()

    context.feedback = {}
    context.run = RunHandle(run_id="r2", pipeline_runner=_Spawner())
    step = PipelineStep(
        name="run_dual_pipelines", action=StepAction.ORCHESTRATE, target=StepTarget.COMPONENTS
    )
    with (
        patch.object(
            ArbitrateDualPipelineHandler, "container_available", staticmethod(lambda r: True)
        ),
        patch.object(
            ArbitrateDualPipelineHandler, "isolation_refusal", staticmethod(lambda c: None)
        ),
    ):
        result = await ArbitrateDualPipelineHandler().execute(step, context)
    assert result.status == StepStatus.PASSED
    return sorted(sides)


@pytest.mark.asyncio
async def test_a_passing_set_is_kept_and_reused(world: tuple[RunContext, Path]) -> None:
    context, store = world

    passed = await _passing_round(context)

    assert passed.status == StepStatus.PASSED
    kept = json.loads((store / "kept" / "greet_spec.json").read_text(encoding="utf-8"))
    assert len(kept["spec_sha256"]) == 64 and len(kept["contract_sha256"]) == 64
    assert await _sides(context) == ["coder"]


@pytest.mark.asyncio
async def test_without_its_tests_the_set_is_made_again(world: tuple[RunContext, Path]) -> None:
    context, store = world
    await _passing_round(context)
    (store / "generated" / "test_greet_scenarios.py").unlink()

    assert await _sides(context) == ["coder", "scenario"]


@pytest.mark.asyncio
async def test_a_broken_record_is_not_trusted(world: tuple[RunContext, Path]) -> None:
    context, store = world
    await _passing_round(context)
    (store / "kept" / "greet_spec.json").write_text("{not json")

    assert await _sides(context) == ["coder", "scenario"]


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", ["spec", "contract"])
async def test_a_change_makes_the_set_again(world: tuple[RunContext, Path], changed: str) -> None:
    context, _ = world
    await _passing_round(context)
    if changed == "spec":
        context.spec_path.write_text("# Greet\n\n| FR-91 | greet loudly |\n")
        record_review(context)  # reviewed again, so the dual run may start
    else:
        (context.project_path / "contracts" / "greet_contract.py").write_text("class Other: ...\n")

    assert await _sides(context) == ["coder", "scenario"]
