# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw sandbox preflight` — what the sandbox will do with a project, before it does it.

The prepare phase makes decisions a reader would otherwise meet inside a container, minutes into a
run: a project without a lockfile is resolved fresh and stops reproducing its own pins, tox lines
needing substitution are skipped, and a project declaring no runner is given one the sandbox chose.

This prints the same plan the executor acts on, so it cannot describe a different phase. It reads
that plan from `commons`, never from the sandbox — the delivery layer delegates rather than
importing execution.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from specweaver.commons.prepare_plan import plan_for

sandbox_cli = typer.Typer(name="sandbox", help="Inspect how the sandbox will treat a project.")
console = Console()

#: Exit 1 on a warning, so CI can gate on it. A plan with no warnings is a project whose QA run
#: will use its own pinned toolchain — the only case where nothing needs saying.
_EXIT_WARNED = 1

_ROUTE_EXPLANATION = {
    "locked": "uv sync --frozen — installs exactly what uv.lock pins",
    "resolved": "uv venv + uv pip install — resolves fresh from pyproject.toml",
    "none": "nothing — no manifest for uv to read",
}


@sandbox_cli.command()
def preflight(
    path: str = typer.Argument(".", help="Project to inspect. Defaults to the current directory."),
) -> None:
    """Report how the sandbox will build a QA environment for this project."""
    root = Path(path).resolve()
    if not root.is_dir():
        console.print(f"[red]Not a directory:[/red] {root}")
        raise typer.Exit(code=2)

    plan = plan_for(root)

    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column(style="bold")
    table.add_column()
    table.add_row("Project", str(root))
    table.add_row("Environment", _ROUTE_EXPLANATION.get(plan.route, plan.route))
    table.add_row("Test runner", _runner_line(plan.runner_source))
    if plan.groups:
        table.add_row("Groups synced", ", ".join(plan.groups))
    console.print(table)

    if plan.skipped:
        console.print(f"\n[yellow]Not installed[/yellow] ({len(plan.skipped)} line(s)):")
        for line in plan.skipped[:10]:
            console.print(f"  {line}")
        if len(plan.skipped) > 10:
            console.print(f"  ... and {len(plan.skipped) - 10} more")

    for warning in plan.warnings:
        console.print(f"\n[yellow]![/yellow] {warning}")

    if plan.warnings:
        raise typer.Exit(code=_EXIT_WARNED)
    console.print("\n[green]Ready.[/green] The run will use the project's own pinned toolchain.")


def _runner_line(source: str) -> str:
    """Where the runner comes from, said in the reader's terms rather than the field's."""
    if not source:
        return "none — the container image's interpreter has no test runner"
    if source == "sandbox":
        return "supplied by the sandbox (the project declares none)"
    return f"declared in {source}"
