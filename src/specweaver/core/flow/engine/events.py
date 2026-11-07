# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The runner's progress-event contract.

A Protocol the CLI and API display layers implement, which is why it does not sit beside worktree
teardown, and the one JSON record both send for an event.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.engine.state import PipelineRun, StepResult


@runtime_checkable
class RunnerEventCallback(Protocol):
    """Protocol for runner event callbacks."""

    def __call__(
        self,
        event: str,
        *,
        step_idx: int | None = None,
        step_name: str | None = None,
        step_def: PipelineStep | None = None,
        total_steps: int | None = None,
        result: StepResult | None = None,
        run: PipelineRun | None = None,
        verdict: str | None = None,
        **kwargs: Any,
    ) -> None: ...


def event_record(event: str, **kwargs: Any) -> dict[str, Any]:
    """The JSON-ready record of one runner event; fields it does not know are dropped."""
    record: dict[str, Any] = {"event": event}
    for key in ("step_idx", "step_name", "total_steps", "verdict"):
        if key in kwargs:
            record[key] = kwargs[key]
    result = kwargs.get("result")
    if result is not None:
        record["result"] = {
            "status": result.status.value,
            "error_message": result.error_message or None,
            "output": result.output,
        }
    run = kwargs.get("run")
    if run is not None:
        record["run_id"] = run.run_id
        record["run_status"] = run.status.value
    return record
