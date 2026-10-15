# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Kept scenario sets keep checking their specs; the result reaches the person and nobody else.

Proves: B-FLOW-01 FR-19

A registered project with its real store and kept records; the real acceptance step (its test
runner recorded), the real handover, the real pipelines and the real end of `sw run`.

| Bucket | Case |
|---|---|
| Happy | a fresh kept set runs against the code; a failing test names its requirement at the end of the run |
| Boundary | no kept set: nothing runs and nothing is shown |
| Degradation | no container: the step says it did not run, and still passes |
| Hostile | a failing check never fails the step, never reaches `feedback`, the handover or the coding side; a set for a changed spec does not run and is listed as stale |
"""

from __future__ import annotations

import contextlib
import json
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
import typer

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.flow.engine.handover import _failed_step_errors
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import PipelineRun, RunStatus, StepRecord, StepStatus
from specweaver.core.flow.handlers.dual_pipeline import side_pipeline
from specweaver.core.flow.handlers.reviewed_spec import keep_set
from specweaver.core.flow.handlers.run_context import GraphContext, RunContext
from specweaver.core.flow.handlers.validation import ValidateTestsHandler
from specweaver.core.flow.interfaces import cli
from specweaver.sandbox.base import AtomResult, AtomStatus
from tests.fixtures.db_utils import register_test_project
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_TESTS = (
    "# @trace(FR-91)\n"
    "def test_greet_happy():  # @trace(FR-91)\n    assert True\n\n"
    "def test_farewell_error():  # @trace(FR-92)\n    assert True\n"
)
_STEP = PipelineStep(
    name="acceptance",
    action=StepAction.VALIDATE,
    target=StepTarget.TESTS,
    params={"kind": "acceptance"},
)


def _spec(root: Path, stem: str, text: str) -> RunContext:
    spec = root / "specs" / f"{stem}_spec.md"
    spec.write_text(text, encoding="utf-8")
    contract = root / "contracts" / f"{stem}_contract.py"
    contract.write_text(f"class {stem.title()}Protocol: ...\n", encoding="utf-8")
    return RunContext(
        project_path=root, spec_path=spec, graph=GraphContext(api_contract_paths=[str(contract)])
    )


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[RunContext, Path]:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    bootstrap_database(str(data / "specweaver.db"))
    db = Database(data / "specweaver.db")
    root = tmp_path / "greeter"
    for folder in ("specs", "contracts", "src"):
        (root / folder).mkdir(parents=True)
    register_test_project(db, "greeter", str(root))
    store = data / "projects" / "greeter" / "scenarios"
    (store / "generated").mkdir(parents=True)
    for stem in ("greet", "bye"):
        (store / "generated" / f"test_{stem}_scenarios.py").write_text(_TESTS)
        kept = _spec(root, stem, f"# {stem}\n")
        kept.db = db
        keep_set(kept)
    # The bye spec changed after its set was kept: that set is stale.
    (root / "specs" / "bye_spec.md").write_text("# bye, changed\n", encoding="utf-8")
    context = _spec(root, "greet", "# greet\n")
    context.db = db
    return context, store


def _atom(failures: list[dict[str, Any]]) -> MagicMock:
    atom = MagicMock()
    atom.run.return_value = AtomResult(
        status=AtomStatus.FAILED if failures else AtomStatus.SUCCESS,
        message="ran",
        exports={
            "passed": 2 - len(failures),
            "failed": len(failures),
            "total": 2,
            "failures": failures,
        },
    )
    return atom


async def _accept(context: RunContext, atom: MagicMock, *, container: bool = True) -> Any:
    with (
        patch("specweaver.sandbox.qa_runner.core.atom.QARunnerAtom", return_value=atom),
        patch(
            "specweaver.core.flow.handlers.acceptance.container_available", lambda root: container
        ),
    ):
        return await ValidateTestsHandler().execute(_STEP, context)


def _shown(result: Any, root: Path) -> str:
    run = PipelineRun.model_construct(
        status=RunStatus.COMPLETED,
        step_records=[StepRecord(step_name="acceptance", status=result.status, result=result)],
    )
    with patch.object(cli._core, "console") as console, contextlib.suppress(typer.Exit):
        cli._finish_run(run, root, warn_on_console=False)
    return " ".join(str(call) for call in console.print.call_args_list)


_FAILED = [
    {
        "nodeid": "/scenarios/generated/test_greet_scenarios.py::test_farewell_error",
        "message": "boom",
    }
]


@pytest.mark.asyncio
async def test_a_kept_set_checks_the_code_and_the_person_sees_the_result(
    world: tuple[RunContext, Path],
) -> None:
    context, _ = world
    atom = _atom(_FAILED)

    result = await _accept(context, atom)

    targets = atom.run.call_args.args[0]["targets"]
    assert targets == ["/scenarios/generated/test_greet_scenarios.py"]
    report = result.output["acceptance"]
    assert report["failed_requirements"] == ["FR-92"]
    assert report["stale"] == ["specs/bye_spec.md"]
    shown = _shown(result, context.project_path)
    assert shows(shown, "FR-92") and shows(shown, "specs/bye_spec.md")


@pytest.mark.asyncio
async def test_a_failing_check_reaches_nobody_but_the_person(
    world: tuple[RunContext, Path],
) -> None:
    context, _ = world

    result = await _accept(context, _atom(_FAILED))

    assert result.status == StepStatus.PASSED
    assert context.feedback == {}
    run = PipelineRun.model_construct(
        status=RunStatus.COMPLETED,
        step_records=[StepRecord(step_name="acceptance", status=result.status, result=result)],
    )
    assert _failed_step_errors(run) == []
    for pipe, coder in (("new_feature.yaml", True), ("new_feature.yaml", False)):
        names = [s.name for s in side_pipeline(pipe, "", coder_side=coder).steps]
        assert ("acceptance" in names) is not coder


@pytest.mark.asyncio
async def test_no_kept_set_runs_nothing(tmp_path: Path) -> None:
    (tmp_path / "specs").mkdir()
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "specs" / "x_spec.md")
    atom = _atom([])

    result = await _accept(context, atom)

    assert result.status == StepStatus.PASSED
    assert atom.run.call_count == 0
    assert "Kept scenario" not in _shown(result, tmp_path)


@pytest.mark.asyncio
async def test_without_a_container_it_says_it_did_not_run(world: tuple[RunContext, Path]) -> None:
    context, _ = world
    atom = _atom([])

    result = await _accept(context, atom, container=False)

    assert result.status == StepStatus.PASSED
    assert atom.run.call_count == 0
    assert "container" in json.dumps(result.output["acceptance"])


def test_both_normal_pipelines_end_with_the_acceptance_step() -> None:
    from specweaver.workflows.implementation.interfaces.cli import _build_implement_pipeline

    implement = _build_implement_pipeline("greet")
    feature = side_pipeline("new_feature.yaml", "", coder_side=False)
    for pipeline in (implement, feature):
        last = pipeline.steps[-1]
        assert last.name == "acceptance" and last.params.get("kind") == "acceptance"


@pytest.mark.asyncio
async def test_sw_implement_shows_the_kept_checks_too(world: tuple[RunContext, Path]) -> None:
    from specweaver.workflows.implementation.interfaces import cli as implement_cli

    context, _ = world
    result = await _accept(context, _atom(_FAILED))
    run = PipelineRun.model_construct(
        status=RunStatus.COMPLETED,
        step_records=[StepRecord(step_name="acceptance", status=result.status, result=result)],
    )

    with patch.object(cli._core, "console") as console:
        implement_cli._report_implementation(run)

    assert shows(" ".join(str(c) for c in console.print.call_args_list), "FR-92")
