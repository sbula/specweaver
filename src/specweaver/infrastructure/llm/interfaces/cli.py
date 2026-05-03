# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI commands for LLM cost and usage tracking."""

from __future__ import annotations

import logging

import anyio
import typer
from rich.table import Table

from specweaver.infrastructure.llm.store import LlmRepository
from specweaver.infrastructure.llm.telemetry import get_default_cost_table
from specweaver.interfaces.cli import _core
from specweaver.interfaces.cli._helpers import _run_workspace_op

logger = logging.getLogger(__name__)


costs_app = typer.Typer(
    name="costs",
    help="View and manage LLM cost overrides.",
    invoke_without_command=True,
)
_core.app.add_typer(costs_app, name="costs")


@costs_app.callback(invoke_without_command=True)
def costs(ctx: typer.Context) -> None:
    """Show current cost settings (defaults + overrides).

    Displays built-in default pricing and any user-configured overrides.
    """
    if ctx.invoked_subcommand is not None:
        return

    db = _core.get_db()

    async def _costs_view() -> None:
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            overrides = await repo.get_cost_overrides()

            table = Table(title="LLM Cost Configuration")
            table.add_column("Model", style="cyan")
            table.add_column("Input $/1k tokens", justify="right")
            table.add_column("Output $/1k tokens", justify="right")
            table.add_column("Source", style="dim")

            default_table = get_default_cost_table()

            # Show defaults
            for model, entry in sorted(default_table.items()):
                if model in overrides:
                    inp, out = overrides[model]
                    source = "override"
                else:
                    inp, out = entry.input_cost_per_1k, entry.output_cost_per_1k
                    source = "default"
                table.add_row(model, f"${inp:.5f}", f"${out:.5f}", source)

            # Show overrides not in defaults
            for model, (inp, out) in sorted(overrides.items()):
                if model not in default_table:
                    table.add_row(model, f"${inp:.5f}", f"${out:.5f}", "override")

            _core.console.print(table)

    anyio.run(_costs_view)


@costs_app.command("set")
def costs_set(
    model: str = typer.Argument(help="Model name or pattern."),
    input_cost: float = typer.Argument(help="Cost per 1,000 input tokens (USD)."),
    output_cost: float = typer.Argument(help="Cost per 1,000 output tokens (USD)."),
) -> None:
    """Set a cost override for a model.

    Example: sw costs set gpt-4o 0.0025 0.01
    """
    db = _core.get_db()

    async def _costs_set() -> None:
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            await repo.set_cost_override(model, input_cost, output_cost)

    anyio.run(_costs_set)
    _core.console.print(
        f"[green]\u2713[/green] Cost override set for [bold]{model}[/bold]: "
        f"input=${input_cost:.5f}/1k, output=${output_cost:.5f}/1k",
    )


@costs_app.command("reset")
def costs_reset(
    model: str = typer.Argument(help="Model name or pattern to reset."),
) -> None:
    """Remove a cost override, reverting to built-in pricing.

    Example: sw costs reset gpt-4o
    """
    db = _core.get_db()

    async def _costs_reset() -> None:
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            await repo.delete_cost_override(model)

    anyio.run(_costs_reset)
    _core.console.print(
        f"[green]\u2713[/green] Cost override removed for [bold]{model}[/bold] "
        "(reverted to defaults).",
    )


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
        project = _run_workspace_op("get_active_project")
        if not project:
            _core.console.print(
                "[yellow]No active project.[/yellow] "
                "Use [bold]sw use <name>[/bold] or pass [bold]--all[/bold].",
            )
            raise typer.Exit(code=0)

    async def _get_usage() -> None:
        from datetime import datetime

        parsed_since = datetime.fromisoformat(since) if since else None

        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            rows = await repo.get_usage_summary(project=project, since=parsed_since)

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

    anyio.run(_get_usage)
