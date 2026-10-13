# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The hash cache marks the last green test run, so only a run whose tests passed saves it.

Proves: C-FLOW-06 FR-2

The next run's test step runs the tests of what changed since this point. Saved after a run that
tested nothing, it would mark untested code as tested.

| Bucket | Case |
|---|---|
| Happy | a completed run whose whole-project test step passed saves the cache |
| Boundary | a test step over one folder, or no test step: not saved |
| Degradation | a failed or parked run: not saved |
| Hostile | a step without output is ignored |
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
import typer

from specweaver.core.flow.engine.state import (
    PipelineRun,
    RunStatus,
    StepRecord,
    StepResult,
    StepStatus,
)
from specweaver.core.flow.interfaces.cli import _finish_run

if TYPE_CHECKING:
    from pathlib import Path

_SAVE = "specweaver.assurance.graph.hasher.DependencyHasher.save_cache"


def _run(status: RunStatus, *outputs: object, step_status: StepStatus = StepStatus.PASSED):
    records = [
        StepRecord(
            step_name=f"s{i}",
            status=step_status,
            result=StepResult(status=step_status, output=out, started_at="", completed_at=""),
        )
        for i, out in enumerate(outputs)
    ]
    return PipelineRun.model_construct(status=status, step_records=records)


def _saved(run: PipelineRun, tmp_path: Path) -> bool:
    with patch(_SAVE) as save, contextlib.suppress(typer.Exit):
        _finish_run(run, tmp_path, warn_on_console=False)
    return save.called


def test_a_passed_whole_project_test_step_saves(tmp_path: Path) -> None:
    # Proves: C-FLOW-06 FR-2
    run = _run(RunStatus.COMPLETED, {"lint": "ok"}, {"total": 3, "tests_cover_project": True})
    assert _saved(run, tmp_path)


def test_a_test_step_over_one_folder_does_not_save(tmp_path: Path) -> None:
    # Proves: C-FLOW-06 FR-2
    run = _run(RunStatus.COMPLETED, {"total": 3, "tests_cover_project": False})
    assert not _saved(run, tmp_path)


def test_a_run_without_tests_does_not_save(tmp_path: Path) -> None:
    # Proves: C-FLOW-06 FR-2
    assert not _saved(_run(RunStatus.COMPLETED, {"verdict": "accepted"}), tmp_path)


def test_a_skipped_test_step_does_not_save(tmp_path: Path) -> None:
    run = _run(RunStatus.COMPLETED, {"tests_cover_project": True}, step_status=StepStatus.SKIPPED)
    assert not _saved(run, tmp_path)


@pytest.mark.parametrize("status", [RunStatus.FAILED, RunStatus.PARKED])
def test_a_run_that_did_not_complete_does_not_save(tmp_path: Path, status: RunStatus) -> None:
    assert not _saved(_run(status, {"tests_cover_project": True}), tmp_path)


def test_a_step_without_output_is_ignored(tmp_path: Path) -> None:
    assert not _saved(_run(RunStatus.COMPLETED, {}), tmp_path)
