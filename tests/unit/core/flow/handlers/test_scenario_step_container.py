# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The scenario test step runs in the scenario container, with its tests read from `/scenarios`.

Proves: B-FLOW-01 FR-14

| Bucket | Case |
|---|---|
| Happy | a `kind: scenario` step builds the atom with the scenario mount and runs `/scenarios/...` |
| Boundary | a `kind: unit` step gets no scenario mount and keeps its project path |
| Degradation | not applicable — the engine check is the dual run's, proven with it |
| Hostile | not applicable — the target comes from the converter, never from a person |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.core.flow.handlers.validation import ValidateTestsHandler
from specweaver.sandbox.base import AtomResult, AtomStatus

if TYPE_CHECKING:
    from pathlib import Path


async def _run(tmp_path: Path, kind: str) -> tuple[dict[str, Any], dict[str, Any]]:
    atom = MagicMock()
    atom.run.return_value = AtomResult(
        status=AtomStatus.SUCCESS, message="ok", exports={"passed": 1, "failed": 0, "total": 1}
    )
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "specs" / "greet_spec.md")
    step = PipelineStep(
        name="run_scenario_tests",
        action=StepAction.VALIDATE,
        target=StepTarget.TESTS,
        params={"kind": kind},
    )
    with patch("specweaver.sandbox.qa_runner.core.atom.QARunnerAtom", return_value=atom) as built:
        await ValidateTestsHandler().execute(step, context)
    return built.call_args.kwargs, atom.run.call_args[0][0]


@pytest.mark.asyncio
async def test_a_scenario_step_runs_from_the_mount(tmp_path: Path) -> None:
    built, ran = await _run(tmp_path, "scenario")

    assert built["scenarios_root"] == tmp_path / "scenarios"
    assert ran["target"] == "/scenarios/generated/test_greet_scenarios.py"
    assert ran["targets"] == ["/scenarios/generated/test_greet_scenarios.py"]


@pytest.mark.asyncio
async def test_a_unit_step_gets_no_scenario_mount(tmp_path: Path) -> None:
    built, ran = await _run(tmp_path, "unit")

    assert built.get("scenarios_root") is None
    assert ran["target"].endswith("tests/test_greet.py")
