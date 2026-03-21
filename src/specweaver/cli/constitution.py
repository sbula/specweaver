# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""CLI commands for constitution management: show, check, init."""

from __future__ import annotations

import typer

from specweaver.cli import _core
from specweaver.project.discovery import resolve_project_path

constitution_app = typer.Typer(
    name="constitution",
    help="Manage the project constitution (CONSTITUTION.md).",
    no_args_is_help=True,
)
_core.app.add_typer(constitution_app, name="constitution")


@constitution_app.command("show")
def constitution_show(
    project: str | None = typer.Option(
        None, "--project", "-p",
        help="Path to the target project directory.",
    ),
) -> None:
    """Display the current CONSTITUTION.md content."""
    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    from specweaver.project.constitution import find_constitution

    info = find_constitution(project_path)
    if info is None:
        _core.console.print(
            "[yellow]No CONSTITUTION.md found.[/yellow]\n"
            "[dim]Run 'sw constitution init' to create one.[/dim]",
        )
        raise typer.Exit(code=1)

    _core.console.print(
        f"[bold]Constitution:[/bold] {info.path}\n"
        f"[dim]Size: {len(info.content)} bytes[/dim]\n",
    )
    _core.console.print(info.content)


@constitution_app.command("check")
def constitution_check(
    project: str | None = typer.Option(
        None, "--project", "-p",
        help="Path to the target project directory.",
    ),
) -> None:
    """Validate the constitution against size limits."""
    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    from specweaver.project.constitution import check_constitution, find_constitution

    info = find_constitution(project_path)
    if info is None:
        _core.console.print(
            "[yellow]No CONSTITUTION.md found.[/yellow]\n"
            "[dim]Run 'sw constitution init' to create one.[/dim]",
        )
        raise typer.Exit(code=1)

    # Try to get the configured max size from DB
    max_size_kwargs: dict = {}
    try:
        db = _core.get_db()
        active = db.get_active_project()
        if active:
            max_size_kwargs["max_size"] = db.get_constitution_max_size(active)
    except Exception:
        pass  # Fall back to default if DB unavailable

    errors = check_constitution(info.path, **max_size_kwargs)

    _core.console.print(f"[bold]Constitution:[/bold] {info.path}")
    _core.console.print(f"[dim]Size: {len(info.content)} bytes[/dim]")

    if "max_size" in max_size_kwargs:
        _core.console.print(f"[dim]Max allowed: {max_size_kwargs['max_size']} bytes[/dim]")

    if not errors:
        _core.console.print("\n[green]\u2713 Constitution is within size limits.[/green]")
    else:
        for err in errors:
            _core.console.print(f"[red]\u2717[/red] {err}")
        raise typer.Exit(code=1)


@constitution_app.command("init")
def constitution_init(
    project: str | None = typer.Option(
        None, "--project", "-p",
        help="Path to the target project directory.",
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Overwrite existing CONSTITUTION.md.",
    ),
) -> None:
    """Create or reset the CONSTITUTION.md template."""
    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    constitution_path = project_path / "CONSTITUTION.md"

    if constitution_path.exists() and not force:
        _core.console.print(
            "[yellow]CONSTITUTION.md already exists.[/yellow]\n"
            "[dim]Use --force to overwrite.[/dim]",
        )
        raise typer.Exit(code=1)

    if force and constitution_path.exists():
        constitution_path.unlink()

    from specweaver.project.constitution import generate_constitution

    project_name = project_path.name.lower().replace(" ", "-")
    result_path = generate_constitution(project_path, project_name)

    _core.console.print(
        f"[green]\u2713[/green] Constitution created: [bold]{result_path}[/bold]",
    )
