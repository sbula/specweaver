# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for pipeline display backends (Rich and JSON)."""

from __future__ import annotations

import io
import json

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


# ---------------------------------------------------------------------------
# Edge case tests: _resolve_spec_path
# ---------------------------------------------------------------------------


class TestResolveSpecPath:
    """Tests for the spec argument resolution logic."""

    def test_existing_file_returned_directly(self, tmp_path) -> None:
        from specweaver.cli import _resolve_spec_path
        spec = tmp_path / "my_spec.md"
        spec.write_text("# Test")
        result = _resolve_spec_path("validate_only", str(spec), tmp_path)
        assert result == spec

    def test_new_feature_derives_from_module_name(self, tmp_path) -> None:
        from specweaver.cli import _resolve_spec_path
        result = _resolve_spec_path("new_feature", "greet_service", tmp_path)
        assert result == tmp_path / "specs" / "greet_service_spec.md"

    def test_relative_path_to_project(self, tmp_path) -> None:
        from specweaver.cli import _resolve_spec_path
        relative = tmp_path / "specs" / "calc.md"
        relative.parent.mkdir(parents=True, exist_ok=True)
        relative.write_text("# Calc")
        result = _resolve_spec_path("validate_only", "specs/calc.md", tmp_path)
        assert result == relative

    def test_nonexistent_falls_back_to_literal(self, tmp_path) -> None:
        from specweaver.cli import _resolve_spec_path
        result = _resolve_spec_path("validate_only", "does_not_exist.md", tmp_path)
        from pathlib import Path
        assert result == Path("does_not_exist.md")


# ---------------------------------------------------------------------------
# Edge case tests: Display backends
# ---------------------------------------------------------------------------


class TestDisplayEdgeCases:
    """Additional edge case tests for display backends."""

    def test_rich_render_returns_table(self) -> None:
        from rich.table import Table
        display = RichPipelineDisplay()
        display.start("test_pipe", [("step_0", "Desc")])
        table = display._render()
        assert isinstance(table, Table)
        display.stop()

    def test_rich_double_stop_no_crash(self) -> None:
        display = RichPipelineDisplay()
        display.start("test_pipe", [("step_0", "")])
        display.stop()
        display.stop()  # second stop should be safe

    def test_json_unknown_event(self) -> None:
        buf = io.StringIO()
        display = JsonPipelineDisplay(output=buf)
        display("totally_unknown", custom_key="custom_value")
        data = json.loads(buf.getvalue().strip())
        assert data["event"] == "totally_unknown"

    def test_rich_gate_advance_no_note(self) -> None:
        """Gate verdict 'advance' should not add a note."""
        display = RichPipelineDisplay()
        display.start("test_pipe", [("step_0", "")])
        display("gate_result", step_idx=0, step_name="step_0", verdict="advance")
        assert display._steps[0].note == ""
        display.stop()

    def test_rich_gate_park_sets_note(self) -> None:
        display = RichPipelineDisplay()
        display.start("test_pipe", [("step_0", "")])
        display("gate_result", step_idx=0, step_name="step_0", verdict="park")
        assert "HITL" in display._steps[0].note
        display.stop()

    def test_rich_gate_loop_back_sets_note(self) -> None:
        display = RichPipelineDisplay()
        display.start("test_pipe", [("step_0", "")])
        display("gate_result", step_idx=0, step_name="step_0", verdict="loop_back")
        assert "loop back" in display._steps[0].note
        display.stop()

    def test_json_verdict_included(self) -> None:
        buf = io.StringIO()
        display = JsonPipelineDisplay(output=buf)
        display("gate_result", step_idx=0, verdict="retry")
        data = json.loads(buf.getvalue().strip())
        assert data["verdict"] == "retry"


# ---------------------------------------------------------------------------
# Edge case tests: CLI
# ---------------------------------------------------------------------------


class TestCLIRunEdgeCases:
    """Edge case tests for sw run and sw resume CLI commands."""

    def test_run_help_shows_examples(self) -> None:
        from typer.testing import CliRunner

        from specweaver.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "pipeline" in result.output.lower()
        assert "spec" in result.output.lower()

    def test_resume_help(self) -> None:
        from typer.testing import CliRunner

        from specweaver.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["resume", "--help"])
        assert result.exit_code == 0
        assert "resume" in result.output.lower()

    def test_create_display_json(self) -> None:
        from specweaver.cli import _create_display
        display = _create_display(use_json=True)
        assert isinstance(display, JsonPipelineDisplay)

    def test_create_display_rich(self) -> None:
        from specweaver.cli import _create_display
        display = _create_display(use_json=False, verbose=True)
        assert isinstance(display, RichPipelineDisplay)

    def test_display_loop_back_missing_target(self) -> None:
        """RichPipelineDisplay ignores missing loop target in history without crashing."""
        display = RichPipelineDisplay()
        display.start("test_pipe", [("step_0", "Desc 0")])
        # Manually sending a gate_result loop_back verdict mimicking undefined behavior
        display("_on_gate_result", step_idx=99, verdict="loop_back")
        display.stop()  # Should not crash

    def test_rich_display_missing_event_data_graceful_ignore(self) -> None:
        """Test that all display methods handle None arguments gracefully without crashing."""
        from specweaver.flow.display import RichPipelineDisplay
        from specweaver.flow.models import PipelineStep
        from specweaver.flow.state import PipelineRun, StepResult, StepStatus
        display = RichPipelineDisplay()
        step = PipelineStep.model_construct(name="validate", action="validate+spec", gates=[])
        run = PipelineRun.model_construct(run_id="mock", pipeline_name="test", steps=[step])
        display("run_started", run=run)

        # 1. _on_run_started with run=None
        display("run_started", run=None)

        # 2. _on_step_failed with out-of-bounds step_idx
        display("step_failed", step_idx=999, result=None)

        # 3. _on_step_failed missing result completely, or result.error_message is None
        display("step_failed", step_idx=0, result=None)
        empty_result = StepResult(status=StepStatus.FAILED, output={}, started_at="now", completed_at="now")
        display("step_failed", step_idx=0, result=empty_result)

        # 4. _on_gate_result bounds safety
        display("gate_result", step_idx=999, verdict="park")

        # 5. _on_run_completed with run=None
        display("run_completed", run=None)

        # 6. _on_run_failed with run=None (and run is not None formatting block)
        display("run_failed", run=None)
        display("run_failed", run=run)

        # 7. _on_run_parked with run=None
        display("run_parked", run=None)

        display.stop()
