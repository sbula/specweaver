# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI command for LLM usage reporting: ``sw usage``."""

from __future__ import annotations

import logging

import typer
from rich.table import Table

from specweaver.cli import _core

logger = logging.getLogger(__name__)


usage_app = typer.Typer(
    name="usage",
    help="View LLM token usage statistics.",
    invoke_without_command=True,
)
_core.app.add_typer(usage_app, name="usage")


@usage_app.callback(invoke_without_command=True)
def usage(
    all_projects: bool = typer.Option(
        False,
        "--all",
        help="Show usage across all projects (not just active).",
    ),
    since: str | None = typer.Option(
        None,
        "--since",
        help="Filter records after this ISO timestamp.",
    ),
) -> None:
    """Show LLM usage summary for the active project.

    Displays token counts, estimated costs, and call counts grouped
    by task type and model.
    """
    db = _core.get_db()

    project: str | None = None
    if not all_projects:
        project = db.get_active_project()
        if not project:
            _core.console.print(
                "[yellow]No active project.[/yellow] "
                "Use [bold]sw use <name>[/bold] or pass [bold]--all[/bold].",
            )
            raise typer.Exit(code=0)

    rows = db.get_usage_summary(project=project, since=since)

    if not rows:
        label = f" for [bold]{project}[/bold]" if project else ""
        _core.console.print(f"[dim]No usage data recorded{label}.[/dim]")
        return

    table = Table(
        title=f"LLM Usage — {project or 'all projects'}",
    )
    table.add_column("Task Type", style="cyan")
    table.add_column("Model")
    table.add_column("Calls", justify="right")
    table.add_column("Prompt Tokens", justify="right")
    table.add_column("Completion Tokens", justify="right")
    table.add_column("Total Tokens", justify="right")
    table.add_column("Cost (USD)", justify="right", style="green")
    table.add_column("Duration (s)", justify="right")

    for r in rows:
        duration_s = (r["total_duration_ms"] or 0) / 1000
        table.add_row(
            str(r["task_type"]),
            str(r["model"]),
            str(r["call_count"]),
            f"{r['total_prompt_tokens'] or 0:,}",
            f"{r['total_completion_tokens'] or 0:,}",
            f"{r['total_tokens'] or 0:,}",
            f"${r['total_cost'] or 0:.6f}",
            f"{duration_s:.1f}",
        )

    _core.console.print(table)
