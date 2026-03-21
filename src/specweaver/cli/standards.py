# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""CLI commands for standards management: scan, show, clear."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from specweaver.cli import _core

standards_app = typer.Typer(
    name="standards",
    help="Auto-discover and manage coding standards for the active project.",
    no_args_is_help=True,
)
_core.app.add_typer(standards_app, name="standards")


@standards_app.command("scan")
def standards_scan() -> None:
    """Scan the active project and auto-discover coding standards."""
    from specweaver.standards.discovery import discover_files
    from specweaver.standards.python_analyzer import PythonStandardsAnalyzer

    name = _core._require_active_project()
    db = _core.get_db()
    proj = db.get_project(name)
    project_path = Path(proj["root_path"])

    if not project_path.exists():
        _core.console.print(f"[red]Error:[/red] Project root does not exist: {project_path}")
        raise typer.Exit(code=1)

    _core.console.print(f"[bold]Scanning standards for[/bold] [cyan]{name}[/cyan]")
    _core.console.print(f"  [dim]Root: {project_path}[/dim]\n")

    all_files = discover_files(project_path)

    analyzer = PythonStandardsAnalyzer()
    py_files = [f for f in all_files if f.suffix in analyzer.file_extensions()]

    if not py_files:
        _core.console.print("[yellow]No Python files found.[/yellow]")
        return

    _core.console.print(f"  Found [bold]{len(py_files)}[/bold] Python files")

    saved = 0
    scope = "."  # project-level scope
    language = analyzer.language_name()
    half_life_days = 90.0  # 3-month decay window

    for category in analyzer.supported_categories():
        result = analyzer.extract(category, py_files, half_life_days)
        if result.confidence < 0.3:
            continue
        db.save_standard(
            project_name=name,
            scope=scope,
            language=language,
            category=result.category,
            data=result.dominant,
            confidence=result.confidence,
        )
        saved += 1
        _core.console.print(
            f"  [green]\u2713[/green] {result.category}: "
            f"confidence={result.confidence:.0%}",
        )

    _core.console.print(
        f"\n[bold]Scan complete[/bold]: {saved} standards saved "
        f"for project [bold]{name}[/bold].",
    )


@standards_app.command("show")
def standards_show(
    scope: str | None = typer.Option(
        None,
        "--scope",
        "-s",
        help="Filter by scope.",
    ),
    language: str | None = typer.Option(
        None,
        "--language",
        "-l",
        help="Filter by language.",
    ),
) -> None:
    """Show discovered coding standards for the active project."""
    import json

    name = _core._require_active_project()
    db = _core.get_db()

    standards = db.get_standards(name, scope=scope, language=language)

    if not standards:
        _core.console.print(
            f"[dim]No standards found for project [bold]{name}[/bold]. "
            "Run [bold]sw standards scan[/bold] first.[/dim]",
        )
        return

    table = Table(title=f"Coding Standards ({name})")
    table.add_column("Scope", style="cyan")
    table.add_column("Language")
    table.add_column("Category", style="green")
    table.add_column("Dominant Patterns")
    table.add_column("Confidence", justify="right")
    table.add_column("Confirmed")

    for s in standards:
        data = json.loads(s["data"]) if isinstance(s["data"], str) else s["data"]
        patterns = ", ".join(f"{k}={v}" for k, v in data.items())
        conf_str = f"{s['confidence']:.0%}"
        confirmed = s.get("confirmed_by") or "[dim]\u2014[/dim]"
        table.add_row(
            s["scope"],
            s["language"],
            s["category"],
            patterns,
            conf_str,
            confirmed,
        )

    _core.console.print(table)


@standards_app.command("clear")
def standards_clear(
    scope: str | None = typer.Option(
        None,
        "--scope",
        "-s",
        help="Only clear standards for this scope.",
    ),
) -> None:
    """Clear discovered standards for the active project."""
    name = _core._require_active_project()
    db = _core.get_db()

    db.clear_standards(name, scope=scope)

    scope_msg = f" (scope: {scope})" if scope else ""
    _core.console.print(
        f"[green]\u2713[/green] Standards cleared for project "
        f"[bold]{name}[/bold]{scope_msg}.",
    )
