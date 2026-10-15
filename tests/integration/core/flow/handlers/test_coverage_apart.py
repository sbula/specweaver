# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The coder's C09 counts the coder's tests only; the run tells the person who covers what.

Proves: B-FLOW-01 FR-13

A registered project with its real scenario store, the real C09 rule, the real scenario test step
(its runner is recorded) and the real end of `sw run`.

| Bucket | Case |
|---|---|
| Happy | the scenario step reports both / coder / scenario / none per requirement, and `sw run` shows it |
| Boundary | a run with no scenario step shows no coverage |
| Degradation | a failed scenario run still reports its coverage |
| Hostile | a requirement only a scenario test covers is still missing in the coder's C09 |
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
import typer

from specweaver.assurance.validation.rules.code.c09_traceability import TraceabilityRule
from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import PipelineRun, RunStatus, StepRecord, StepStatus
from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.core.flow.handlers.validation import ValidateTestsHandler
from specweaver.core.flow.interfaces import cli
from specweaver.sandbox.base import AtomResult, AtomStatus
from tests.fixtures.db_utils import register_test_project
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_SPEC = "# Greet\n\n## Functional Requirements\n\n| FR-1 | a |\n| FR-2 | b |\n| FR-3 | c |\n| FR-4 | d |\n"


def _test(folder: Path, name: str, *ids: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    body = "".join(
        f"def test_{i}():  # @trace({rid})\n    assert 2 > 1\n" for i, rid in enumerate(ids)
    )
    (folder / name).write_text(body, encoding="utf-8")


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[RunContext, Path]:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    bootstrap_database(str(data / "specweaver.db"))
    db = Database(data / "specweaver.db")
    root = tmp_path / "greeter"
    (root / "specs").mkdir(parents=True)
    (root / "pyproject.toml").write_text('[project]\nname = "greeter"\n')
    (root / "specs" / "greet_spec.md").write_text(_SPEC, encoding="utf-8")
    register_test_project(db, "greeter", str(root))
    _test(root / "tests", "test_greet.py", "FR-1", "FR-3")
    store = data / "projects" / "greeter" / "scenarios"
    _test(store / "generated", "test_greet_scenarios.py", "FR-1", "FR-2")
    context = RunContext(project_path=root, spec_path=root / "specs" / "greet_spec.md", db=db)
    return context, store


async def _scenario_step(context: RunContext, store: Path, status: AtomStatus) -> object:
    atom = MagicMock()
    atom.run.return_value = AtomResult(
        status=status, message="ran", exports={"passed": 1, "failed": 0, "total": 1}
    )
    step = PipelineStep(
        name="run_scenario_tests",
        action=StepAction.VALIDATE,
        target=StepTarget.TESTS,
        params={"kind": "scenario", "target": str(store / "generated" / "test_greet_scenarios.py")},
    )
    with patch("specweaver.sandbox.qa_runner.core.atom.QARunnerAtom", return_value=atom):
        return await ValidateTestsHandler().execute(step, context)


_EXPECTED = {"FR-1": "both", "FR-2": "scenario", "FR-3": "coder", "FR-4": "none"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status", [AtomStatus.SUCCESS, AtomStatus.FAILED], ids=["passed", "failed"]
)
async def test_the_scenario_step_reports_who_covers_what(
    world: tuple[RunContext, Path], status: AtomStatus
) -> None:
    context, store = world

    result = await _scenario_step(context, store, status)

    assert result.output["requirement_coverage"] == _EXPECTED
    assert "requirement_coverage" not in str(context.feedback)


def _finish(run: PipelineRun, root: Path) -> str:
    with patch.object(cli._core, "console") as console, contextlib.suppress(typer.Exit):
        cli._finish_run(run, root, warn_on_console=False)
    return " ".join(str(call) for call in console.print.call_args_list)


@pytest.mark.asyncio
async def test_sw_run_shows_the_coverage_at_its_end(world: tuple[RunContext, Path]) -> None:
    context, store = world
    result = await _scenario_step(context, store, AtomStatus.SUCCESS)
    run = PipelineRun.model_construct(
        status=RunStatus.COMPLETED,
        step_records=[
            StepRecord(step_name="run_scenario_tests", status=StepStatus.PASSED, result=result)
        ],
    )

    shown = _finish(run, context.project_path)

    for rid, side in {
        "FR-1": "both",
        "FR-2": "scenario only",
        "FR-3": "coder only",
        "FR-4": "none",
    }.items():
        assert shows(shown, f"{rid} {side}")


def test_a_run_without_a_scenario_step_shows_no_coverage(world: tuple[RunContext, Path]) -> None:
    context, _ = world
    run = PipelineRun.model_construct(status=RunStatus.COMPLETED, step_records=[])

    assert "coverage" not in _finish(run, context.project_path).lower()


def test_the_coders_c09_does_not_count_the_scenario_tests(world: tuple[RunContext, Path]) -> None:
    context, _ = world

    result = TraceabilityRule().check(_SPEC, context.spec_path)

    missing = {f.message.split()[1] for f in result.findings}
    assert missing == {"FR-2", "FR-4"}
