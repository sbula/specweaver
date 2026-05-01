# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI commands for project management: init, use, projects, remove, update, scan."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.table import Table

from specweaver.assurance.graph.topology import TopologyGraph
from specweaver.interfaces.cli import _core
from specweaver.workspace.project.discovery import resolve_project_path
from specweaver.workspace.project.scaffold import scaffold_project
from specweaver.workspace.project.tach_sync import sync_tach_toml

if TYPE_CHECKING:
    from specweaver.assurance.graph.inference import ContextInferrer  # type: ignore

logger = logging.getLogger(__name__)


@_core.app.command()
def init(
    name: str = typer.Argument(
        help="Project name (lowercase, hyphens, underscores only).",
    ),
    path: str | None = typer.Option(
        None,
        "--path",
        "-p",
        help="Path to the project directory. Defaults to cwd.",
    ),
    mcp: str | None = typer.Option(
        None,
        "--mcp",
        help="Scaffold MCP boundary (e.g., 'postgres').",
    ),
) -> None:
    """Register a project and create SpecWeaver scaffolding.

    Creates .specweaver/ marker, context.yaml, specs/, templates.
    Registers the project in the SpecWeaver database and sets it as active.
    """
    try:
        project_path = resolve_project_path(path)
    except (FileNotFoundError, NotADirectoryError) as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    # Register in DB
    db = _core.get_db()
    try:
        db.register_project(name, str(project_path))
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    db.set_active_project(name)

    # Scaffold files
    try:
        result = scaffold_project(project_path, mcp_target=mcp)
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _core.console.print(
        f"[green]Project initialized[/green] at [bold]{result.project_path}[/bold]",
    )
    for item in result.created:
        _core.console.print(f"  [dim]Created:[/dim] {item}")
    _core.console.print(f"  [dim]Registered:[/dim] project [bold]{name}[/bold]")
    _core.console.print(f"  [dim]Active:[/dim] {name}")

    # Hint: if existing source files detected, suggest standards scan
    source_exts = {".py", ".js", ".jsx", ".ts", ".tsx"}
    has_source = any(
        f.suffix in source_exts
        for f in project_path.rglob("*")
        if f.is_file()
        and not any(p.startswith(".") or p == "__pycache__" or p == "node_modules" for p in f.parts)
    )
    if has_source:
        _core.console.print(
            "\n[dim]Existing code detected. Run [bold]sw standards scan[/bold] "
            "to discover coding conventions.[/dim]",
        )


@_core.app.command()
def use(
    name: str = typer.Argument(
        help="Name of the project to switch to.",
    ),
) -> None:
    """Switch the active project."""
    db = _core.get_db()
    proj = db.get_project(name)
    if not proj:
        _core.console.print(
            f"[red]Error:[/red] Project '{name}' not found. "
            f"Run [bold]sw init {name} --path <path>[/bold] to register it.",
        )
        raise typer.Exit(code=1)

    # Check path still exists
    root = Path(str(proj["root_path"]))
    if not root.exists():
        _core.console.print(
            f"[red]Error:[/red] Project root no longer exists: {root}\n"
            f"  Run [bold]sw update {name} path <new-path>[/bold] if moved, or\n"
            f"  [bold]sw remove {name}[/bold] to unregister.",
        )
        raise typer.Exit(code=1)

    db.set_active_project(name)
    _core.console.print(f"[green]Switched[/green] to project [bold]{name}[/bold] ({root})")


@_core.app.command()
def projects() -> None:
    """List all registered projects."""
    db = _core.get_db()
    all_projects = db.list_projects()
    active = db.get_active_project()

    if not all_projects:
        _core.console.print(
            "[dim]No projects registered. Run [bold]sw init <name>[/bold] to add one.[/dim]",
        )
        return

    table = Table(title="SpecWeaver Projects")
    table.add_column("", width=2)
    table.add_column("Name", style="bold")
    table.add_column("Path")
    table.add_column("Last Used", style="dim")

    for proj in all_projects:
        marker = "*" if proj["name"] == active else ""
        table.add_row(
            marker,
            str(proj["name"]),
            str(proj["root_path"]),
            str(proj["last_used_at"])[:10],
        )

    _core.console.print(table)


@_core.app.command()
def remove(
    name: str = typer.Argument(
        help="Name of the project to unregister.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt.",
    ),
) -> None:
    """Unregister a project from SpecWeaver."""
    db = _core.get_db()
    proj = db.get_project(name)
    if not proj:
        _core.console.print(f"[red]Error:[/red] Project '{name}' not found.")
        raise typer.Exit(code=1)

    if not force:
        confirm = typer.confirm(
            f"Unregister project '{name}' and delete its config?",
        )
        if not confirm:
            _core.console.print("[dim]Cancelled.[/dim]")
            return

    db.remove_project(name)
    _core.console.print(f"[green]Removed[/green] project [bold]{name}[/bold]")


@_core.app.command()
def update(
    name: str = typer.Argument(
        help="Name of the project to update.",
    ),
    field: str = typer.Argument(
        help="Field to update (currently: 'path').",
    ),
    value: str = typer.Argument(
        help="New value for the field.",
    ),
) -> None:
    """Update a project setting (e.g., root path)."""
    db = _core.get_db()
    if field == "path":
        try:
            db.update_project_path(name, value)
        except ValueError as exc:
            _core.console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        _core.console.print(
            f"[green]Updated[/green] project [bold]{name}[/bold] path -> {value}",
        )
    else:
        _core.console.print(f"[red]Error:[/red] Unknown field '{field}'. Supported: path")
        raise typer.Exit(code=1)


def _infer_subdirs(project_path: Path, inferrer: ContextInferrer) -> tuple[int, int, int]:
    generated = 0
    skipped = 0
    existing = 0

    for subdir in sorted(project_path.rglob("*")):
        if not subdir.is_dir():
            continue
        if any(p.startswith(".") or p == "__pycache__" for p in subdir.parts):
            continue

        context_file = subdir / "context.yaml"
        if context_file.exists():
            rel = subdir.relative_to(project_path)
            _core.console.print(f"  [green]\u2713[/green] {rel}/ \u2014 context.yaml exists")
            existing += 1
            continue

        # Only infer for directories with Python files
        py_files = list(subdir.glob("*.py"))
        if not py_files:
            skipped += 1
            continue

        try:
            inferrer.infer_and_write(subdir)
            rel = subdir.relative_to(project_path)
            _core.console.print(
                f"  [yellow]\u26a0[/yellow] {rel}/ \u2014 AUTO-GENERATED (review recommended)"
            )
            generated += 1
        except Exception:
            rel = subdir.relative_to(project_path)
            _core.console.print(f"  [red]\u2717[/red] {rel}/ \u2014 failed to infer")

    return generated, skipped, existing


@_core.app.command()
def scan() -> None:
    """Scan the active project and auto-generate missing context.yaml files."""
    db = _core.get_db()
    active = db.get_active_project()
    if not active:
        _core.console.print(
            "[red]Error:[/red] No active project. "
            "Run [bold]sw init <name>[/bold] or [bold]sw use <name>[/bold] first.",
        )
        raise typer.Exit(code=1)

    proj = db.get_project(active)
    if proj is None:
        _core.console.print(f"[red]Error:[/red] Project '{active}' not found.")
        raise typer.Exit(code=1)
    project_path = Path(str(proj["root_path"]))

    if not project_path.exists():
        _core.console.print(f"[red]Error:[/red] Project root does not exist: {project_path}")
        raise typer.Exit(code=1)

    from specweaver.workspace.analyzers.factory import AnalyzerFactory
    from specweaver.workspace.context.inferrer import ContextInferrer

    inferrer = ContextInferrer(AnalyzerFactory)
    _core.console.print(f"[bold]Scanning[/bold] {project_path}...")

    generated, skipped, existing = _infer_subdirs(project_path, inferrer)

    _core.console.print(
        f"\n[bold]Scan complete[/bold]: "
        f"{existing} existing, {generated} generated, {skipped} skipped",
    )

    # Sync tach.toml topology layer
    _core.console.print("\n[bold]Synchronizing Tach Architecture Matrix...[/bold]")
    try:
        from specweaver.graph.topology.engine import TopologyEngine
        engine = TopologyEngine()
        graph = TopologyGraph.from_project(project_path, engine)
        sync_result = sync_tach_toml(graph, project_path)
        _core.console.print(
            f"  [green]\u2713[/green] [bold]Tach Sync[/bold]: Synchronized {sync_result.modules_synced} modules "
            f"and {sync_result.interfaces_synced} interfaces into tach.toml"
        )
    except Exception as exc:
        _core.console.print(f"  [red]\u2717[/red] Tach Sync Failed: {exc}")
