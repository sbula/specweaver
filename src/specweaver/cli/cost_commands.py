# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI commands for cost override management: ``sw costs``."""

from __future__ import annotations

import logging

import typer
from rich.table import Table

from specweaver.cli import _core
from specweaver.llm.telemetry import get_default_cost_table

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
    overrides = db.get_cost_overrides()

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
    db.set_cost_override(model, input_cost, output_cost)
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
    db.delete_cost_override(model)
    _core.console.print(
        f"[green]\u2713[/green] Cost override removed for [bold]{model}[/bold] "
        "(reverted to defaults).",
    )
