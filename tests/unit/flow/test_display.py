# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for pipeline display backends (Rich and JSON)."""

from __future__ import annotations

import io
import json

import pytest

from specweaver.flow.display import JsonPipelineDisplay, RichPipelineDisplay, _StepState
from specweaver.flow.state import StepResult, StepStatus


# ---------------------------------------------------------------------------
# _StepState tests
# ---------------------------------------------------------------------------


class TestStepState:
    """Tests for _StepState internal display model."""

    def test_initial_state_is_pending(self) -> None:
        state = _StepState("test_step", "A test step")
        assert state.status == "pending"
        assert state.name == "test_step"
        assert state.description == "A test step"
        assert state.elapsed == 0.0
        assert state.start_time is None
        assert state.note == ""

    def test_mark_running_sets_start_time(self) -> None:
        state = _StepState("test_step")
        state.mark_running()
        assert state.status == "running"
        assert state.start_time is not None

    def test_mark_done_records_elapsed(self) -> None:
        state = _StepState("test_step")
        state.mark_running()
        state.mark_done("passed", "all good")
        assert state.status == "passed"
        assert state.elapsed >= 0
        assert state.note == "all good"

    def test_mark_done_without_running_no_crash(self) -> None:
        state = _StepState("test_step")
        state.mark_done("failed")
        assert state.status == "failed"
        assert state.elapsed == 0.0


# ---------------------------------------------------------------------------
# RichPipelineDisplay tests
# ---------------------------------------------------------------------------


class TestRichPipelineDisplay:
    """Tests for the Rich terminal display backend."""

    def test_start_initializes_steps(self) -> None:
        display = RichPipelineDisplay()
        display.start("test_pipe", [("step_0", "Desc 0"), ("step_1", "Desc 1")])
        display.stop()
        assert len(display._steps) == 2
        assert display._steps[0].name == "step_0"
        assert display._steps[1].name == "step_1"

    def test_step_started_marks_running(self) -> None:
        display = RichPipelineDisplay()
        display.start("test_pipe", [("step_0", ""), ("step_1", "")])
        display("step_started", step_idx=0, step_name="step_0", total_steps=2)
        assert display._steps[0].status == "running"
        display.stop()

    def test_step_completed_marks_passed(self) -> None:
        display = RichPipelineDisplay()
        display.start("test_pipe", [("step_0", "")])
        display("step_started", step_idx=0, step_name="step_0", total_steps=1)
        display("step_completed", step_idx=0, step_name="step_0", total_steps=1,
                result=StepResult(status=StepStatus.PASSED,
                    started_at="2026-01-01T00:00:00Z",
                    completed_at="2026-01-01T00:00:01Z"))
        assert display._steps[0].status == "passed"
        display.stop()

    def test_step_failed_marks_failed(self) -> None:
        display = RichPipelineDisplay()
        display.start("test_pipe", [("step_0", "")])
        result = StepResult(status=StepStatus.FAILED, error_message="Boom",
                            started_at="2026-01-01T00:00:00Z",
                            completed_at="2026-01-01T00:00:01Z")
        display("step_failed", step_idx=0, step_name="step_0", total_steps=1, result=result)
        assert display._steps[0].status == "failed"
        assert display._steps[0].note == "Boom"
        display.stop()

    def test_step_parked_marks_parked(self) -> None:
        display = RichPipelineDisplay()
        display.start("test_pipe", [("step_0", "")])
        display("step_parked", step_idx=0, step_name="step_0", total_steps=1)
        assert display._steps[0].status == "parked"
        display.stop()

    def test_gate_result_sets_note(self) -> None:
        display = RichPipelineDisplay()
        display.start("test_pipe", [("step_0", "")])
        display("gate_result", step_idx=0, step_name="step_0", verdict="retry")
        assert "retry" in display._steps[0].note
        display.stop()

    def test_unknown_event_no_crash(self) -> None:
        display = RichPipelineDisplay()
        display.start("test_pipe", [("step_0", "")])
        display("unknown_event", step_idx=0)  # should not crash
        display.stop()

    def test_stop_without_start_no_crash(self) -> None:
        display = RichPipelineDisplay()
        display.stop()  # should not crash

    def test_out_of_range_step_idx_no_crash(self) -> None:
        display = RichPipelineDisplay()
        display.start("test_pipe", [("step_0", "")])
        display("step_started", step_idx=99, step_name="step_99", total_steps=1)
        display.stop()  # should not crash


# ---------------------------------------------------------------------------
# JsonPipelineDisplay tests
# ---------------------------------------------------------------------------


class TestJsonPipelineDisplay:
    """Tests for the NDJSON display backend."""

    def test_start_emits_pipeline_start(self) -> None:
        buf = io.StringIO()
        display = JsonPipelineDisplay(output=buf)
        display.start("test_pipe", [("step_0", "Desc 0")])

        lines = buf.getvalue().strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["event"] == "pipeline_start"
        assert data["pipeline"] == "test_pipe"
        assert len(data["steps"]) == 1

    def test_event_emits_ndjson_line(self) -> None:
        buf = io.StringIO()
        display = JsonPipelineDisplay(output=buf)
        display("step_started", step_idx=0, step_name="step_0", total_steps=2)

        lines = buf.getvalue().strip().split("\n")
        data = json.loads(lines[0])
        assert data["event"] == "step_started"
        assert data["step_idx"] == 0
        assert data["step_name"] == "step_0"
        assert data["total_steps"] == 2

    def test_result_serialized(self) -> None:
        buf = io.StringIO()
        display = JsonPipelineDisplay(output=buf)
        result = StepResult(
            status=StepStatus.PASSED,
            output={"key": "value"},
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:01Z",
        )
        display("step_completed", step_idx=0, result=result)

        data = json.loads(buf.getvalue().strip())
        assert data["result"]["status"] == "passed"
        assert data["result"]["output"] == {"key": "value"}

    def test_run_serialized(self) -> None:
        """Run metadata should be included when run kwarg is passed."""
        from specweaver.flow.state import PipelineRun, RunStatus, StepRecord

        buf = io.StringIO()
        display = JsonPipelineDisplay(output=buf)

        run = PipelineRun(
            run_id="abc123",
            pipeline_name="test_pipe",
            project_name="test_proj",
            spec_path="/fake/spec.md",
            status=RunStatus.COMPLETED,
            current_step=0,
            step_records=[StepRecord(step_name="step_0")],
            started_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:01Z",
        )
        display("run_completed", run=run)

        data = json.loads(buf.getvalue().strip())
        assert data["run_id"] == "abc123"
        assert data["run_status"] == "completed"

    def test_stop_is_noop(self) -> None:
        buf = io.StringIO()
        display = JsonPipelineDisplay(output=buf)
        display.stop()  # should not crash or write

    def test_multiple_events_produce_multiple_lines(self) -> None:
        buf = io.StringIO()
        display = JsonPipelineDisplay(output=buf)
        display("step_started", step_idx=0)
        display("step_completed", step_idx=0)
        display("run_completed")

        lines = buf.getvalue().strip().split("\n")
        assert len(lines) == 3


# ---------------------------------------------------------------------------
# CLI sw pipelines tests
# ---------------------------------------------------------------------------


class TestCLIPipelines:
    """Tests for the sw pipelines command."""

    def test_pipelines_shows_bundled(self) -> None:
        from typer.testing import CliRunner

        from specweaver.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["pipelines"])
        assert result.exit_code == 0
        assert "new_feature" in result.output
        assert "validate_only" in result.output
