# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Pipeline run state — tracks execution progress.

This module defines the in-memory state model for pipeline runs.
It contains no persistence logic (that's in ``store.py``) and no
execution logic (that's in ``runner.py``).

A ``PipelineRun`` tracks which step the runner is on, what happened
at each step, and whether the run is active, parked, or terminal.
"""

from __future__ import annotations

import enum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StepStatus(enum.StrEnum):
    """Status of a single pipeline step."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    WAITING_FOR_INPUT = "waiting_for_input"


class RunStatus(enum.StrEnum):
    """Status of a pipeline run as a whole."""

    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"
    PARKED = "parked"


# ---------------------------------------------------------------------------
# Step result
# ---------------------------------------------------------------------------


class StepResult(BaseModel):
    """Outcome of executing a single pipeline step.

    Attributes:
        status: Final status of the step execution.
        output: Step-specific data (review verdict, rule results, etc.).
        error_message: Human-readable error description (empty if no error).
        started_at: ISO timestamp when execution began.
        completed_at: ISO timestamp when execution finished.
    """

    status: StepStatus
    output: dict[str, Any] = Field(default_factory=dict)
    artifact_uuid: str | None = None
    error_message: str = ""
    started_at: str
    completed_at: str


# ---------------------------------------------------------------------------
# Step record
# ---------------------------------------------------------------------------


class StepRecord(BaseModel):
    """Record of a step within a pipeline run.

    Attributes:
        step_name: Name of the pipeline step.
        status: Current status of this step.
        result: Execution result (None if not yet executed).
        attempt: Current attempt number (for future retry tracking).
    """

    step_name: str
    status: StepStatus = StepStatus.PENDING
    result: StepResult | None = None
    attempt: int = 1


# ---------------------------------------------------------------------------
# Pipeline run
# ---------------------------------------------------------------------------

_TERMINAL_STATUSES = frozenset(
    {
        RunStatus.COMPLETED,
        RunStatus.FAILED,
        RunStatus.ABORTED,
    }
)


class PipelineRun(BaseModel):
    """In-memory state of a pipeline execution.

    Attributes:
        run_id: Unique identifier (UUID).
        pipeline_name: Name of the pipeline definition.
        project_name: Project this run belongs to.
        spec_path: Path to the spec being processed.
        status: Overall run status.
        current_step: Index into step_records (0-based).
        step_records: One record per pipeline step.
        started_at: ISO timestamp when the run started.
        updated_at: ISO timestamp of the last state change.
    """

    run_id: str
    parent_run_id: str | None = None
    pipeline_name: str
    project_name: str
    spec_path: str
    status: RunStatus = RunStatus.NOT_STARTED
    current_step: int = 0
    step_records: list[StepRecord] = Field(default_factory=list)
    started_at: str
    updated_at: str

    @property
    def is_terminal(self) -> bool:
        """True if the run has reached a final state."""
        return self.status in _TERMINAL_STATUSES

    def current_step_record(self) -> StepRecord | None:
        """Get the current step record, or None if past the end."""
        if self.current_step >= len(self.step_records):
            return None
        return self.step_records[self.current_step]

    def mark_step_running(self) -> None:
        """Mark the current step as running and the run as running."""
        record = self.current_step_record()
        if record is not None:
            record.status = StepStatus.RUNNING
            self.status = RunStatus.RUNNING

    def complete_current_step(self, result: StepResult) -> None:
        """Record a successful step and advance to the next.

        If this was the last step, the run is marked COMPLETED.
        """
        record = self.current_step_record()
        if record is not None:
            record.status = result.status
            record.result = result
            self.current_step += 1

            if self.current_step >= len(self.step_records):
                self.status = RunStatus.COMPLETED

    def fail_current_step(self, result: StepResult) -> None:
        """Record a failed step and mark the run as FAILED.

        The current_step stays pointing at the failed step (for resume).
        """
        record = self.current_step_record()
        if record is not None:
            record.status = StepStatus.FAILED
            record.result = result
            self.status = RunStatus.FAILED

    def park_current_step(self, result: StepResult) -> None:
        """Park the run at the current step (HITL interaction needed).

        The current_step stays pointing at the parked step.
        """
        record = self.current_step_record()
        if record is not None:
            record.status = StepStatus.WAITING_FOR_INPUT
            record.result = result
            self.status = RunStatus.PARKED
