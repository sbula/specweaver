# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI commands for AST drift detection: sw drift check."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.table import Table

from specweaver.cli import _core, _helpers
from specweaver.project.discovery import resolve_project_path

if TYPE_CHECKING:
    from specweaver.flow.state import StepResult

logger = logging.getLogger(__name__)

drift_app = typer.Typer(
    name="drift",
    help="AST Drift detection engine operations.",
    no_args_is_help=True,
)
_core.app.add_typer(drift_app, name="drift")


@drift_app.command("check")
def drift_check(
    target: str = typer.Argument(help="Path to the code file to check."),
    plan: str = typer.Option(
        ...,
        "--plan",
        help="Path to the PlanArtifact YAML file.",
    ),
    analyze: bool = typer.Option(
        False,
        "--analyze",
        help="Use LLM to perform root-cause analysis on the AST drift.",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory.",
    ),
) -> None:
    """Check a code file against its planned AST signatures."""
    target_path = Path(target)
    if not target_path.exists():
        _core.console.print(f"[red]Error:[/red] File not found: {target}")
        raise typer.Exit(code=1)

    plan_path = Path(plan)
    if not plan_path.exists():
        _core.console.print(f"[red]Error:[/red] Plan file not found: {plan}")
        raise typer.Exit(code=1)

    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    from specweaver.flow._base import RunContext
    from specweaver.flow.models import PipelineDefinition, StepAction, StepTarget
    from specweaver.flow.runner import PipelineRunner
    from specweaver.flow.state import StepStatus

    pipeline = PipelineDefinition.create_single_step(
        name="drift_check",
        action=StepAction.DETECT,
        target=StepTarget.DRIFT,
        description=f"AST Drift Check for {target_path.name}",
        params={
            "target_path": str(target_path),
            "plan_path": str(plan_path),
            "analyze": analyze,
        },
    )

    context = RunContext(
        project_path=project_path,
        spec_path=plan_path,
        db=_core.get_db(),
    )

    if analyze:
        _, adapter, _ = _helpers._require_llm_adapter(project_path)
        context.llm = adapter

    runner = PipelineRunner(pipeline, context)
    run_state = asyncio.run(runner.run())

    last_record = run_state.step_records[-1] if run_state.step_records else None

    if not last_record or last_record.status == StepStatus.ERROR or not last_record.result:
        error_msg = (
            last_record.result.error_message
            if last_record and last_record.result
            else "Unknown runner error"
        )
        _core.console.print(f"[red]Execution failed:[/red] {error_msg}")
        raise typer.Exit(code=1)

    _present_result(last_record.result, target_path.name, analyze)


def _present_result(result: StepResult, target_name: str, analyze: bool) -> None:
    is_drifted = result.output.get("is_drifted", False)
    findings = result.output.get("findings", [])

    if not is_drifted:
        _core.console.print(f"[green]✓ AST signatures match specification.[/green] ({target_name})")
        if findings:
            table = Table(title=f"Warnings for {target_name}")
            table.add_column("Severity")
            table.add_column("Description")
            for f in findings:
                table.add_row(f.get("severity", "WARNING"), f.get("description", ""))
            _core.console.print(table)
        return

    _core.console.print(f"[red]✗ AST Drift Detected![/red] ({target_name})")
    table = Table(title=f"Drift Findings for {target_name}")
    table.add_column("Severity", style="red")
    table.add_column("Description")

    for f in findings:
        table.add_row(f.get("severity", "ERROR"), f.get("description", ""))

    _core.console.print(table)

    if analyze and "llm_root_cause" in result.output:
        _core.console.print("\n[bold cyan]LLM Root-Cause Analysis:[/bold cyan]")
        _core.console.print(f"[dim]{result.output['llm_root_cause']}[/dim]")

    raise typer.Exit(code=1)
