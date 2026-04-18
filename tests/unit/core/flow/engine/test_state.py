# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for pipeline state model — enums, result types, run state."""

from __future__ import annotations

import uuid

from specweaver.core.flow.engine.state import (
    PipelineRun,
    RunStatus,
    StepRecord,
    StepResult,
    StepStatus,
)

# ---------------------------------------------------------------------------
# StepStatus enum
# ---------------------------------------------------------------------------


class TestStepStatus:
    """Tests for StepStatus enum."""

    def test_all_statuses_exist(self) -> None:
        assert StepStatus.PENDING == "pending"
        assert StepStatus.RUNNING == "running"
        assert StepStatus.PASSED == "passed"
        assert StepStatus.FAILED == "failed"
        assert StepStatus.SKIPPED == "skipped"
        assert StepStatus.ERROR == "error"
        assert StepStatus.WAITING_FOR_INPUT == "waiting_for_input"

    def test_status_count(self) -> None:
        assert len(StepStatus) == 7


# ---------------------------------------------------------------------------
# RunStatus enum
# ---------------------------------------------------------------------------


class TestRunStatus:
    """Tests for RunStatus enum."""

    def test_all_statuses_exist(self) -> None:
        assert RunStatus.NOT_STARTED == "not_started"
        assert RunStatus.RUNNING == "running"
        assert RunStatus.COMPLETED == "completed"
        assert RunStatus.FAILED == "failed"
        assert RunStatus.ABORTED == "aborted"
        assert RunStatus.PARKED == "parked"

    def test_status_count(self) -> None:
        assert len(RunStatus) == 6


# ---------------------------------------------------------------------------
# StepResult
# ---------------------------------------------------------------------------


class TestStepResult:
    """Tests for StepResult model."""

    def test_minimal_result(self) -> None:
        result = StepResult(
            status=StepStatus.PASSED,
            started_at="2026-03-14T18:00:00Z",
            completed_at="2026-03-14T18:00:01Z",
            artifact_uuid="fake-uuid-1234",
        )
        assert result.status == StepStatus.PASSED
        assert result.output == {}
        assert result.error_message == ""
        assert result.artifact_uuid == "fake-uuid-1234"

    def test_failed_result_with_error(self) -> None:
        result = StepResult(
            status=StepStatus.FAILED,
            output={"rule_count": 5, "failures": 2},
            error_message="2 validation rules failed",
            started_at="2026-03-14T18:00:00Z",
            completed_at="2026-03-14T18:00:01Z",
        )
        assert result.status == StepStatus.FAILED
        assert result.error_message == "2 validation rules failed"
        assert result.output["failures"] == 2

    def test_waiting_for_input_result(self) -> None:
        result = StepResult(
            status=StepStatus.WAITING_FOR_INPUT,
            output={"message": "Please run 'sw draft' to create the spec"},
            started_at="2026-03-14T18:00:00Z",
            completed_at="2026-03-14T18:00:00Z",
        )
        assert result.status == StepStatus.WAITING_FOR_INPUT

    def test_serialization_roundtrip(self) -> None:
        result = StepResult(
            status=StepStatus.PASSED,
            output={"verdict": "accepted", "findings": []},
            started_at="2026-03-14T18:00:00Z",
            completed_at="2026-03-14T18:00:01Z",
        )
        data = result.model_dump()
        result2 = StepResult.model_validate(data)
        assert result2.status == result.status
        assert result2.output == result.output


# ---------------------------------------------------------------------------
# StepRecord
# ---------------------------------------------------------------------------


class TestStepRecord:
    """Tests for StepRecord model."""

    def test_pending_record(self) -> None:
        record = StepRecord(step_name="validate_spec", status=StepStatus.PENDING)
        assert record.step_name == "validate_spec"
        assert record.status == StepStatus.PENDING
        assert record.result is None
        assert record.attempt == 1

    def test_record_with_result(self) -> None:
        result = StepResult(
            status=StepStatus.PASSED,
            started_at="2026-03-14T18:00:00Z",
            completed_at="2026-03-14T18:00:01Z",
        )
        record = StepRecord(
            step_name="validate_spec",
            status=StepStatus.PASSED,
            result=result,
        )
        assert record.result is not None
        assert record.result.status == StepStatus.PASSED

    def test_record_with_attempt(self) -> None:
        record = StepRecord(
            step_name="review_spec",
            status=StepStatus.FAILED,
            attempt=3,
        )
        assert record.attempt == 3


# ---------------------------------------------------------------------------
# PipelineRun
# ---------------------------------------------------------------------------


def _make_run(
    *,
    run_id: str | None = None,
    parent_run_id: str | None = None,
    status: RunStatus = RunStatus.NOT_STARTED,
    current_step: int = 0,
    step_names: list[str] | None = None,
) -> PipelineRun:
    """Helper to create a PipelineRun with defaults."""
    if step_names is None:
        step_names = ["validate_spec", "review_spec"]
    return PipelineRun(
        run_id=run_id or str(uuid.uuid4()),
        parent_run_id=parent_run_id,
        pipeline_name="test_pipeline",
        project_name="test_project",
        spec_path="specs/test_spec.md",
        status=status,
        current_step=current_step,
        step_records=[StepRecord(step_name=name, status=StepStatus.PENDING) for name in step_names],
        started_at="2026-03-14T18:00:00Z",
        updated_at="2026-03-14T18:00:00Z",
    )


class TestPipelineRun:
    """Tests for PipelineRun model."""

    def test_construction(self) -> None:
        run = _make_run()
        assert run.pipeline_name == "test_pipeline"
        assert run.project_name == "test_project"
        assert run.status == RunStatus.NOT_STARTED
        assert run.current_step == 0
        assert len(run.step_records) == 2
        assert run.parent_run_id is None

    def test_construction_with_parent_run_id(self) -> None:
        run = _make_run(parent_run_id="parent-uuid-5678")
        assert run.parent_run_id == "parent-uuid-5678"

    def test_current_step_record(self) -> None:
        run = _make_run()
        record = run.current_step_record()
        assert record is not None
        assert record.step_name == "validate_spec"

    def test_current_step_record_at_end(self) -> None:
        run = _make_run(current_step=2, step_names=["s1", "s2"])
        assert run.current_step_record() is None

    def test_is_complete(self) -> None:
        run = _make_run(status=RunStatus.COMPLETED)
        assert run.is_terminal is True

    def test_is_failed(self) -> None:
        run = _make_run(status=RunStatus.FAILED)
        assert run.is_terminal is True

    def test_is_aborted(self) -> None:
        run = _make_run(status=RunStatus.ABORTED)
        assert run.is_terminal is True

    def test_is_not_terminal_when_running(self) -> None:
        run = _make_run(status=RunStatus.RUNNING)
        assert run.is_terminal is False

    def test_is_not_terminal_when_parked(self) -> None:
        run = _make_run(status=RunStatus.PARKED)
        assert run.is_terminal is False

    def test_advance_step(self) -> None:
        run = _make_run(current_step=0)
        result = StepResult(
            status=StepStatus.PASSED,
            started_at="2026-03-14T18:00:00Z",
            completed_at="2026-03-14T18:00:01Z",
        )
        run.complete_current_step(result)
        assert run.current_step == 1
        assert run.step_records[0].status == StepStatus.PASSED
        assert run.step_records[0].result is not None

    def test_advance_past_last_step_completes_run(self) -> None:
        run = _make_run(current_step=1, status=RunStatus.RUNNING)
        result = StepResult(
            status=StepStatus.PASSED,
            started_at="2026-03-14T18:00:00Z",
            completed_at="2026-03-14T18:00:01Z",
        )
        run.complete_current_step(result)
        assert run.current_step == 2
        assert run.status == RunStatus.COMPLETED

    def test_route_to_step(self) -> None:
        run = _make_run(current_step=0, step_names=["s1", "s2", "s3"], status=RunStatus.RUNNING)
        result = StepResult(
            status=StepStatus.PASSED,
            started_at="2026-03-14T18:00:00Z",
            completed_at="2026-03-14T18:00:01Z",
        )
        run.route_to_step(result, next_step_idx=2)
        assert run.current_step == 2
        assert run.step_records[0].status == StepStatus.PASSED
        assert run.status == RunStatus.RUNNING

    def test_route_to_out_of_bounds_completes_run(self) -> None:
        run = _make_run(current_step=0, step_names=["s1", "s2"], status=RunStatus.RUNNING)
        result = StepResult(
            status=StepStatus.PASSED,
            started_at="2026-03-14T18:00:00Z",
            completed_at="2026-03-14T18:00:01Z",
        )
        run.route_to_step(result, next_step_idx=2)
        assert run.current_step == 2
        assert run.status == RunStatus.COMPLETED

    def test_mark_current_step_failed(self) -> None:
        run = _make_run(status=RunStatus.RUNNING)
        result = StepResult(
            status=StepStatus.FAILED,
            error_message="Validation failed",
            started_at="2026-03-14T18:00:00Z",
            completed_at="2026-03-14T18:00:01Z",
        )
        run.fail_current_step(result)
        assert run.step_records[0].status == StepStatus.FAILED
        assert run.status == RunStatus.FAILED
        assert run.current_step == 0  # stays at failed step

    def test_park_at_current_step(self) -> None:
        run = _make_run(status=RunStatus.RUNNING)
        result = StepResult(
            status=StepStatus.WAITING_FOR_INPUT,
            output={"message": "Please run 'sw draft'"},
            started_at="2026-03-14T18:00:00Z",
            completed_at="2026-03-14T18:00:00Z",
        )
        run.park_current_step(result)
        assert run.step_records[0].status == StepStatus.WAITING_FOR_INPUT
        assert run.status == RunStatus.PARKED

    def test_serialization_roundtrip(self) -> None:
        run = _make_run()
        data = run.model_dump()
        run2 = PipelineRun.model_validate(data)
        assert run2.run_id == run.run_id
        assert run2.pipeline_name == run.pipeline_name
        assert len(run2.step_records) == len(run.step_records)

    def test_serialization_roundtrip_with_parent(self) -> None:
        run = _make_run(parent_run_id="parent-uuid-5678")
        data = run.model_dump()
        run2 = PipelineRun.model_validate(data)
        assert run2.parent_run_id == "parent-uuid-5678"

    def test_serialization_with_results(self) -> None:
        run = _make_run(status=RunStatus.RUNNING)
        result = StepResult(
            status=StepStatus.PASSED,
            output={"verdict": "accepted"},
            started_at="2026-03-14T18:00:00Z",
            completed_at="2026-03-14T18:00:01Z",
        )
        run.complete_current_step(result)
        data = run.model_dump()
        run2 = PipelineRun.model_validate(data)
        assert run2.step_records[0].result is not None
        assert run2.step_records[0].result.output["verdict"] == "accepted"

    def test_mark_running(self) -> None:
        run = _make_run()
        run.mark_step_running()
        assert run.step_records[0].status == StepStatus.RUNNING
        assert run.status == RunStatus.RUNNING

    # -- Edge cases: transitions at end of steps --

    def test_complete_at_end_is_noop(self) -> None:
        """complete_current_step when past last step should not crash."""
        run = _make_run(current_step=2, step_names=["s1", "s2"])
        result = StepResult(
            status=StepStatus.PASSED,
            started_at="2026-03-14T18:00:00Z",
            completed_at="2026-03-14T18:00:01Z",
        )
        run.complete_current_step(result)
        assert run.current_step == 2  # unchanged

    def test_route_to_step_at_end_is_noop(self) -> None:
        """route_to_step when past last step should not crash."""
        run = _make_run(current_step=2, step_names=["s1", "s2"])
        result = StepResult(
            status=StepStatus.PASSED,
            started_at="2026-03-14T18:00:00Z",
            completed_at="2026-03-14T18:00:01Z",
        )
        run.route_to_step(result, next_step_idx=0)
        assert run.current_step == 2  # unchanged

    def test_fail_at_end_is_noop(self) -> None:
        """fail_current_step when past last step should not crash."""
        run = _make_run(current_step=2, step_names=["s1", "s2"])
        result = StepResult(
            status=StepStatus.FAILED,
            started_at="2026-03-14T18:00:00Z",
            completed_at="2026-03-14T18:00:01Z",
        )
        run.fail_current_step(result)
        # Status should NOT be changed to FAILED (no step to fail)
        assert run.status == RunStatus.NOT_STARTED

    def test_park_at_end_is_noop(self) -> None:
        """park_current_step when past last step should not crash."""
        run = _make_run(current_step=2, step_names=["s1", "s2"])
        result = StepResult(
            status=StepStatus.WAITING_FOR_INPUT,
            started_at="2026-03-14T18:00:00Z",
            completed_at="2026-03-14T18:00:00Z",
        )
        run.park_current_step(result)
        assert run.status == RunStatus.NOT_STARTED

    def test_mark_running_at_end_is_noop(self) -> None:
        """mark_step_running when past last step should not crash."""
        run = _make_run(current_step=2, step_names=["s1", "s2"])
        run.mark_step_running()
        assert run.status == RunStatus.NOT_STARTED

    def test_not_started_is_not_terminal(self) -> None:
        run = _make_run(status=RunStatus.NOT_STARTED)
        assert run.is_terminal is False
