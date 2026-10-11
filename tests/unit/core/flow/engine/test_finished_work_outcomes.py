# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which steps count as finished work for the cost history.

Proves: B-FLOW-07 FR-2

Agreed 2026-10-11: a review that returned its verdict did its work, accepted or denied; any other
failed step stays out, so cheap failed attempts never lower the typical cost.

| Bucket | Case |
|---|---|
| Happy | a passed step and a denied review count as passed |
| Boundary | a step still waiting or not run has no outcome |
| Degradation | a review that could not run (ERROR) is failed |
| Hostile | a failed non-review step is failed even if it carries some output |
"""

from __future__ import annotations

from specweaver.core.flow.engine.state import PipelineRun, StepRecord, StepResult, StepStatus
from specweaver.core.flow.engine.telemetry import step_outcomes


def _record(name: str, status: StepStatus, output: dict | None = None) -> StepRecord:
    result = (
        StepResult(status=status, output=output or {}, started_at="t", completed_at="t")
        if status != StepStatus.PENDING
        else None
    )
    return StepRecord(step_name=name, status=status, result=result)


def test_finished_work_counts() -> None:
    run = PipelineRun(
        run_id="r",
        started_at="t",
        updated_at="t",
        pipeline_name="p",
        project_name="x",
        spec_path="s.md",
        step_records=[
            _record("draft", StepStatus.PASSED),
            _record("review", StepStatus.FAILED, {"verdict": "denied", "findings_count": 3}),
            _record("review_err", StepStatus.ERROR, {"verdict": "error"}),
            _record("implement", StepStatus.FAILED, {"tests": "2 failed"}),
            _record("later", StepStatus.PENDING),
        ],
    )

    assert step_outcomes(run) == {
        "draft": "passed",
        "review": "passed",
        "review_err": "failed",
        "implement": "failed",
    }
