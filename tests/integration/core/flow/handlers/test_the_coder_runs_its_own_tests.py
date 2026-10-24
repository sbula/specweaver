# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The coder's test step runs the coder's tests; only the scenario step runs the scenario tests.

Proves: B-FLOW-01 NFR-8

Found 2026-10-15: `new_feature.yaml`'s `run_tests` names no file, and the handler fell back to the
scenario converter's output. In a dual run the coder was then retried until the hidden scenario
tests passed — the code was fitted to the tests the design keeps from it.

The shipped pipeline files and the real handler; only the test runner is recorded.

| Bucket | Case |
|---|---|
| Happy | `new_feature`'s `run_tests` runs `tests/test_<stem>.py` |
| Boundary | `scenario_integration`'s `run_scenario_tests` still runs the scenario file |
| Degradation | a scenario file on disk next to the coder's tests is not run by the coder's step |
| Hostile | not applicable — no input crosses a trust line here |
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specweaver.core.flow.engine.parser import load_pipeline
from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.core.flow.handlers.validation import ValidateTestsHandler
from specweaver.sandbox.base import AtomResult, AtomStatus

PIPELINES = Path(__file__).resolve().parents[5] / "src" / "specweaver" / "workflows" / "pipelines"


async def _target_of(pipeline: str, step_name: str, root: Path) -> str:
    (step,) = [s for s in load_pipeline(PIPELINES / pipeline).steps if s.name == step_name]
    handler = ValidateTestsHandler()
    atom = MagicMock()
    atom.run.return_value = AtomResult(
        status=AtomStatus.SUCCESS, message="ok", exports={"passed": 1, "failed": 0, "total": 1}
    )
    with patch.object(handler, "_get_atom", return_value=atom):
        await handler.execute(
            step, RunContext(project_path=root, spec_path=root / "greeter_spec.md")
        )
    return str(atom.run.call_args[0][0]["target"])


@pytest.mark.asyncio
async def test_the_coders_step_runs_the_coders_tests(tmp_path: Path) -> None:
    (tmp_path / "scenarios" / "generated").mkdir(parents=True)
    (tmp_path / "scenarios" / "generated" / "test_greeter_scenarios.py").write_text("")

    target = await _target_of("new_feature.yaml", "run_tests", tmp_path)

    # Relative: read from where the step runs, the run's worktree included.
    assert target == "tests/test_greeter.py"


@pytest.mark.asyncio
async def test_the_scenario_step_runs_the_scenario_tests(tmp_path: Path) -> None:
    target = await _target_of("scenario_integration.yaml", "run_scenario_tests", tmp_path)

    assert "scenarios" in Path(target).parts
