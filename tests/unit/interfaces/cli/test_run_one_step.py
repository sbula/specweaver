# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One helper builds, sets up and runs a one-step pipeline for a CLI command.

Proves: TECH-077 FR-11

The run builder and the runner are replaced; the claim is what the helper hands them and returns.

| Bucket | Case |
|---|---|
| Happy | the step has the given name, action, target and params; its record comes back with the context |
| Boundary | a run with no step record gives None |
| Degradation | not applicable — the builder's refusals are proven by `test_run_doors.py` |
| Hostile | the door's `models` and `read_only` reach the builder unchanged |
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from specweaver.core.flow.engine.models import StepAction, StepTarget
from specweaver.interfaces.cli import run_doors


def _run(records: list[object], **kw: object) -> tuple[MagicMock, MagicMock, object]:
    context = MagicMock()
    with (
        patch.object(run_doors, "build_run_or_exit", return_value=context) as build,
        patch("specweaver.core.flow.engine.runner.PipelineRunner") as runner_class,
    ):
        runner_class.return_value.run = AsyncMock(
            return_value=SimpleNamespace(step_records=records)
        )
        out = run_doors.run_one_step(
            Path("/p"),
            Path("/p/plan.yaml"),
            name="drift_check",
            action=StepAction.DETECT,
            target=StepTarget.DRIFT,
            description="Drift",
            params={"analyze": True},
            **kw,
        )
    return build, runner_class, (out, context)


def test_the_step_is_built_as_asked_and_its_record_returned() -> None:
    build, runner_class, ((record, given), context) = _run(["first", "last"])

    pipeline = build.call_args.args[2]
    step = pipeline.steps[0]
    assert (len(pipeline.steps), step.name, step.action, step.target, step.params) == (
        1,
        "drift_check",
        StepAction.DETECT,
        StepTarget.DRIFT,
        {"analyze": True},
    )
    assert runner_class.call_args.args == (pipeline, context)
    assert (record, given) == ("last", context)


def test_no_record_is_none() -> None:
    _build, _runner, ((record, _given), _context) = _run([])

    assert record is None


def test_the_doors_choices_reach_the_builder() -> None:
    build, _runner, _out = _run(["x"], models="none", read_only=True)

    assert (build.call_args.kwargs["models"], build.call_args.kwargs["read_only"]) == ("none", True)
