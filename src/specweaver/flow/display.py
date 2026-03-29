# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Pipeline progress display backends.

Two display backends that implement the ``on_event`` callback interface
for ``PipelineRunner``:

- ``RichPipelineDisplay`` — Rich live terminal display with step
  checkmarks, elapsed time, and gate annotations.
- ``JsonPipelineDisplay`` — NDJSON event stream to stdout for
  machine-readable output (``--json`` flag).
"""

from __future__ import annotations

import json
import sys
import time
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from specweaver.flow.state import PipelineRun, StepResult


# ---------------------------------------------------------------------------
# Step display state
# ---------------------------------------------------------------------------


class _StepState:
    """Tracks display state for a single pipeline step."""

    __slots__ = ("description", "elapsed", "name", "note", "start_time", "status")

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self.status: str = "pending"  # pending | running | passed | failed | error | parked
        self.start_time: float | None = None
        self.elapsed: float = 0.0
        self.note: str = ""

    def mark_running(self) -> None:
        self.status = "running"
        self.start_time = time.monotonic()

    def mark_done(self, status: str, note: str = "") -> None:
        self.status = status
        if self.start_time is not None:
            self.elapsed = time.monotonic() - self.start_time
        self.note = note


# ---------------------------------------------------------------------------
# Rich display backend (default)
# ---------------------------------------------------------------------------

_STATUS_ICONS = {
    "pending": "[dim]   [/dim]",
    "running": "[cyan]⠋  [/cyan]",
    "passed": "[green]✅ [/green]",
    "failed": "[red]❌ [/red]",
    "error": "[red]💥 [/red]",
    "parked": "[yellow]🅿️ [/yellow]",
}


class RichPipelineDisplay:
    """Rich terminal display showing step list with live checkmarks.

    Renders a live-updating step list like::

        ✅ 1. validate_spec — Run spec validation rules (1.2s)
        ⠋  2. review_spec — LLM semantic review...
           3. generate_code — Generate implementation from spec

    Args:
        console: Rich console to use (default: new Console to stderr).
        verbose: If True, show additional detail for completed steps.
    """

    def __init__(
        self,
        *,
        console: Console | None = None,
        verbose: bool = False,
    ) -> None:
        self._console = console or Console(stderr=True)
        self._verbose = verbose
        self._steps: list[_StepState] = []
        self._live: Live | None = None
        self._pipeline_name: str = ""
        self._run_id: str = ""

    def start(self, pipeline_name: str, steps: list[tuple[str, str]]) -> None:
        """Initialize the display for a pipeline run.

        Args:
            pipeline_name: Name of the pipeline being run.
            steps: List of (step_name, description) tuples.
        """
        self._pipeline_name = pipeline_name
        self._steps = [_StepState(name, desc) for name, desc in steps]
        self._live = Live(
            self._render(),
            console=self._console,
            refresh_per_second=4,
        )
        self._live.start()

    def stop(self) -> None:
        """Stop the live display."""
        if self._live is not None:
            self._live.update(self._render())
            self._live.stop()
            self._live = None

    def __call__(self, event: str, **kwargs: Any) -> None:
        """Handle a runner event — implements the on_event callback."""
        handler = getattr(self, f"_on_{event}", None)
        if handler is not None:
            handler(**kwargs)
        self._refresh()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_run_started(self, *, run: PipelineRun | None = None, **_: Any) -> None:
        if run is not None:
            self._run_id = run.run_id

    def _on_step_started(
        self,
        *,
        step_idx: int | None = None,
        step_name: str | None = None,
        **_: Any,
    ) -> None:
        if step_idx is not None and step_idx < len(self._steps):
            self._steps[step_idx].mark_running()

    def _on_step_completed(
        self,
        *,
        step_idx: int | None = None,
        result: StepResult | None = None,
        **_: Any,
    ) -> None:
        if step_idx is not None and step_idx < len(self._steps):
            self._steps[step_idx].mark_done("passed")

    def _on_step_failed(
        self,
        *,
        step_idx: int | None = None,
        result: StepResult | None = None,
        **_: Any,
    ) -> None:
        if step_idx is not None and step_idx < len(self._steps):
            note = ""
            if result is not None and result.error_message:
                note = result.error_message
            status = "error" if result and result.status.value == "error" else "failed"
            self._steps[step_idx].mark_done(status, note)

    def _on_step_parked(
        self,
        *,
        step_idx: int | None = None,
        **_: Any,
    ) -> None:
        if step_idx is not None and step_idx < len(self._steps):
            self._steps[step_idx].mark_done("parked", "Waiting for human input")

    def _on_gate_result(
        self,
        *,
        step_idx: int | None = None,
        verdict: str | None = None,
        **_: Any,
    ) -> None:
        if step_idx is not None and step_idx < len(self._steps) and verdict:
            gate_notes = {
                "advance": "",
                "stop": "gate: abort",
                "retry": "gate: retry",
                "loop_back": "gate: ↩️ loop back",
                "park": "gate: 🅿️ HITL",
            }
            note = gate_notes.get(verdict, f"gate: {verdict}")
            if note:
                self._steps[step_idx].note = note

    def _on_run_completed(self, *, run: PipelineRun | None = None, **_: Any) -> None:
        self.stop()
        if run is not None:
            self._console.print(
                f"\n[green bold]Pipeline completed[/green bold] "
                f"[dim]({run.pipeline_name}, run {run.run_id[:8]})[/dim]",
            )

    def _on_run_failed(self, *, run: PipelineRun | None = None, **_: Any) -> None:
        self.stop()
        if run is not None:
            self._console.print(
                f"\n[red bold]Pipeline failed[/red bold] "
                f"[dim]({run.pipeline_name}, run {run.run_id[:8]})[/dim]",
            )

    def _on_run_parked(
        self,
        *,
        run: PipelineRun | None = None,
        step_name: str | None = None,
        **_: Any,
    ) -> None:
        self.stop()
        if run is not None:
            self._console.print(
                f"\n[yellow bold]Pipeline parked[/yellow bold] at step [cyan]{step_name}[/cyan]",
            )
            self._console.print(
                f"[dim]Resume with:[/dim] sw run --resume {run.run_id}",
            )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        """Refresh the live display."""
        if self._live is not None:
            self._live.update(self._render())

    def _render(self) -> Table:
        """Build a Rich Table showing all steps and their status."""
        table = Table(
            show_header=False,
            show_edge=False,
            pad_edge=False,
            box=None,
            padding=(0, 1),
        )
        table.add_column("icon", width=3, no_wrap=True)
        table.add_column("step", ratio=1)
        table.add_column("time", justify="right", style="dim", width=8)

        for i, step in enumerate(self._steps):
            icon = _STATUS_ICONS.get(step.status, "   ")
            num = f"{i + 1}."

            # Step name + description
            if step.status == "running":
                label = Text(f"{num} {step.name}", style="bold cyan")
            elif step.status in ("passed",):
                label = Text(f"{num} {step.name}", style="green")
            elif step.status in ("failed", "error"):
                label = Text(f"{num} {step.name}", style="red")
            elif step.status == "parked":
                label = Text(f"{num} {step.name}", style="yellow")
            else:
                label = Text(f"{num} {step.name}", style="dim")

            # Description
            if step.description:
                label.append(f" — {step.description}", style="dim")

            # Note (gate result, error message)
            if step.note:
                label.append(f"  ({step.note})", style="dim italic")

            # Elapsed time
            time_str = ""
            if step.elapsed > 0:
                time_str = f"{step.elapsed:.1f}s"
            elif step.status == "running" and step.start_time:
                elapsed = time.monotonic() - step.start_time
                time_str = f"{elapsed:.1f}s"

            table.add_row(icon, label, time_str)

        return table


# ---------------------------------------------------------------------------
# JSON display backend (--json)
# ---------------------------------------------------------------------------


class JsonPipelineDisplay:
    """Machine-readable NDJSON event stream.

    Writes one JSON object per event to stdout. No Rich formatting.
    Suitable for piping to ``jq`` or consuming from CI scripts.

    Args:
        output: File-like object to write to (default: sys.stdout).
    """

    def __init__(self, *, output: Any = None) -> None:
        self._output = output or sys.stdout

    def start(self, pipeline_name: str, steps: list[tuple[str, str]]) -> None:
        """Emit pipeline start event."""
        self._write(
            {
                "event": "pipeline_start",
                "pipeline": pipeline_name,
                "steps": [{"name": n, "description": d} for n, d in steps],
            }
        )

    def stop(self) -> None:
        """No-op for JSON backend."""

    def __call__(self, event: str, **kwargs: Any) -> None:
        """Write an NDJSON event line."""
        record: dict[str, Any] = {"event": event}

        # Extract serializable fields
        if "step_idx" in kwargs:
            record["step_idx"] = kwargs["step_idx"]
        if "step_name" in kwargs:
            record["step_name"] = kwargs["step_name"]
        if "total_steps" in kwargs:
            record["total_steps"] = kwargs["total_steps"]
        if "verdict" in kwargs:
            record["verdict"] = kwargs["verdict"]

        # Serialize result if present
        result = kwargs.get("result")
        if result is not None:
            record["result"] = {
                "status": result.status.value,
                "error_message": result.error_message or None,
                "output": result.output,
            }

        # Serialize run if present
        run = kwargs.get("run")
        if run is not None:
            record["run_id"] = run.run_id
            record["run_status"] = run.status.value

        self._write(record)

    def _write(self, data: dict[str, Any]) -> None:
        """Write a single JSON line."""
        self._output.write(json.dumps(data, default=str) + "\n")
        self._output.flush()
