# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI commands for workspace project management: projects, constitution, hooks."""

from __future__ import annotations

import logging
import stat
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from specweaver.workspace.context.inferrer import ContextInferrer

import anyio
import typer
from rich.table import Table

from specweaver.interfaces.cli import _core
from specweaver.workspace.project.constitution import check_constitution, find_constitution
from specweaver.workspace.project.discovery import resolve_project_path
from specweaver.workspace.project.scaffold import scaffold_project
from specweaver.workspace.project.tach_sync import sync_tach_toml
from specweaver.workspace.store import WorkspaceRepository

logger = logging.getLogger(__name__)

def _run_workspace_op(method_name: str, *args: Any, **kwargs: Any) -> Any:
    db = _core.get_db()
    async def _action() -> Any:
        async with db.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            method = getattr(repo, method_name)
            return await method(*args, **kwargs)
    return anyio.run(_action)

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
        _run_workspace_op("register_project", name, str(project_path))
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _run_workspace_op("set_active_project", name)

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
    proj = _run_workspace_op("get_project", name)
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

    _run_workspace_op("set_active_project", name)
    _core.console.print(f"[green]Switched[/green] to project [bold]{name}[/bold] ({root})")


@_core.app.command()
def projects() -> None:
    """List all registered projects."""
    db = _core.get_db()
    all_projects = _run_workspace_op("list_projects")
    active = _run_workspace_op("get_active_project")

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
    proj = _run_workspace_op("get_project", name)
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

    _run_workspace_op("remove_project", name)
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
            _run_workspace_op("update_project_path", name, value)
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
    active = _run_workspace_op("get_active_project")
    if not active:
        _core.console.print(
            "[red]Error:[/red] No active project. "
            "Run [bold]sw init <name>[/bold] or [bold]sw use <name>[/bold] first.",
        )
        raise typer.Exit(code=1)

    proj = _run_workspace_op("get_project", active)
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
        from specweaver.assurance.graph.topology import TopologyGraph

        engine = TopologyEngine()
        graph = TopologyGraph.from_project(project_path, engine)
        sync_result = sync_tach_toml(graph, project_path)
        _core.console.print(
            f"  [green]\u2713[/green] [bold]Tach Sync[/bold]: Synchronized {sync_result.modules_synced} modules "
            f"and {sync_result.interfaces_synced} interfaces into tach.toml"
        )
    except Exception as exc:
        _core.console.print(f"  [red]\u2717[/red] Tach Sync Failed: {exc}")

constitution_app = typer.Typer(
    name="constitution",
    help="Manage the project constitution (CONSTITUTION.md).",
    no_args_is_help=True,
)
_core.app.add_typer(constitution_app, name="constitution")


@constitution_app.command("show")
def constitution_show(
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory.",
    ),
) -> None:
    """Display the current CONSTITUTION.md content."""
    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


    info = find_constitution(project_path)
    if info is None:
        _core.console.print(
            "[yellow]No CONSTITUTION.md found.[/yellow]\n"
            "[dim]Run 'sw constitution init' to create one.[/dim]",
        )
        raise typer.Exit(code=1)

    _core.console.print(
        f"[bold]Constitution:[/bold] {info.path}\n[dim]Size: {len(info.content)} bytes[/dim]\n",
    )
    _core.console.print(info.content)


@constitution_app.command("check")
def constitution_check(
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory.",
    ),
) -> None:
    """Validate the constitution against size limits."""
    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


    info = find_constitution(project_path)
    if info is None:
        _core.console.print(
            "[yellow]No CONSTITUTION.md found.[/yellow]\n"
            "[dim]Run 'sw constitution init' to create one.[/dim]",
        )
        raise typer.Exit(code=1)

    # Try to get the configured max size from DB
    max_size_kwargs: dict[str, int] = {}
    try:
        db = _core.get_db()
        active = _run_workspace_op("get_active_project")
        if active:
            import anyio

            from specweaver.workspace.store import WorkspaceRepository

            async def _get_max_size() -> int:
                async with db.async_session_scope() as session:
                    return await WorkspaceRepository(session).get_constitution_max_size(active)

            max_size_kwargs["max_size"] = anyio.run(_get_max_size)
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
        None,
        "--project",
        "-p",
        help="Path to the target project directory.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
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

    from specweaver.workspace.project.constitution import generate_constitution

    project_name = project_path.name.lower().replace(" ", "-")
    result_path = generate_constitution(project_path, project_name)

    _core.console.print(
        f"[green]\u2713[/green] Constitution created: [bold]{result_path}[/bold]",
    )


@constitution_app.command("bootstrap")
def constitution_bootstrap(
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite even a user-edited CONSTITUTION.md.",
    ),
) -> None:
    """Generate CONSTITUTION.md pre-filled from confirmed coding standards.

    Loads auto-discovered standards from the database and populates
    sections 1 (Identity), 2 (Tech Stack), and 4 (Coding Standards).
    Sections 3, 5-8 remain as TODO placeholders for human review.

    If CONSTITUTION.md already exists but is still the unmodified starter
    template, it will be auto-replaced. User-edited constitutions
    require --force to overwrite.
    """
    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    from specweaver.workspace.project.constitution import generate_constitution_from_standards

    # Load standards from DB
    db = _core.get_db()
    name = _core._require_active_project()
    standards = _run_workspace_op("get_standards", name)

    if not standards:
        _core.console.print(
            "[yellow]No confirmed standards found.[/yellow]\n"
            "[dim]Run 'sw standards scan' first to discover coding standards.[/dim]",
        )
        raise typer.Exit(code=1)

    # Extract unique languages
    languages = sorted({str(s["language"]) for s in standards})

    project_name = project_path.name.lower().replace(" ", "-")
    result = generate_constitution_from_standards(
        project_path,
        project_name,
        standards,
        languages,
        force=force,
    )

    if result is None:
        _core.console.print(
            "[yellow]CONSTITUTION.md already exists and has been edited.[/yellow]\n"
            "[dim]Use --force to overwrite.[/dim]",
        )
        raise typer.Exit(code=1)

    _core.console.print(
        f"[green]\u2713[/green] Constitution bootstrapped from "
        f"[bold]{len(standards)}[/bold] standards: [bold]{result}[/bold]",
    )
    _core.console.print(
        f"  [dim]Languages: {', '.join(languages)}[/dim]\n"
        f"  [dim]Review and customize sections marked TODO.[/dim]",
    )

hooks_app = typer.Typer(
    name="hooks",
    help="Git hook installation and management.",
    no_args_is_help=True,
)
_core.app.add_typer(hooks_app, name="hooks")

HOOK_TEMPLATE = """#!/usr/bin/env bash
# AUTO-GENERATED BY SPECWEAVER
# Do not edit this file manually.

# Enforce SpecWeaver AST/Spec contract drift detection.
# If this fails, review the output and either fix the code or the Spec.md contract.

echo ">>> SpecWeaver: Running Bi-Directional Spec Rot Interceptor (Feature 3.23) <<<"

"{python_exec}" -m specweaver.interfaces.cli.main drift check-rot --staged
exit_code=$?

if [ $exit_code -eq 42 ]; then
    echo ""
    echo "================================================================"
    echo "ERROR: SpecWeaver detected structural drift between Spec and Code!"
    echo "Fix the mismatch to proceed with this commit."
    echo "================================================================"
    exit 1
elif [ $exit_code -ne 0 ]; then
    echo ""
    echo "================================================================"
    echo "ERROR: The SpecWeaver pipeline crashed ($exit_code)."
    echo "Please check your python environment or the stack trace above."
    echo "================================================================"
    exit 1
fi
"""


@hooks_app.command("install")
def hooks_install(
    pre_commit: bool = typer.Option(
        True,
        "--pre-commit/--no-pre-commit",
        help="Install the pre-commit hook (Spec Rot Interceptor).",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory.",
    ),
) -> None:
    """Install git hooks for the current repository."""
    try:
        project_path = resolve_project_path(project)
        logger.debug(f"Resolved project path: {project_path}")
    except (FileNotFoundError, NotADirectoryError) as exc:
        logger.error(f"Project path resolution failed: {exc}")
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    git_dir = project_path / ".git"
    if not git_dir.exists() or not git_dir.is_dir():
        logger.error(f"Target is not a git repository: {git_dir}")
        _core.console.print(
            "[red]Error:[/red] Target project is not a git repository (missing .git directory)."
        )
        raise typer.Exit(code=1)

    hooks_dir = git_dir / "hooks"
    logger.debug(f"Ensuring hooks directory exists: {hooks_dir}")
    hooks_dir.mkdir(exist_ok=True)

    if pre_commit:
        hook_path = hooks_dir / "pre-commit"
        python_exec = str(sys.executable)

        hook_content = HOOK_TEMPLATE.format(python_exec=python_exec)

        # Write the file
        logger.debug(f"Writing hook to {hook_path}")
        hook_path.write_text(hook_content, encoding="utf-8")

        # Apply execution permissions (chmod +x)
        st = hook_path.stat()
        hook_path.chmod(st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

        logger.info(f"Successfully installed pre-commit hook at {hook_path}")
        _core.console.print(
            "[green]Success: SpecWeaver pre-commit hook installed successfully.[/green]"
        )
    else:
        logger.info("Skip pre-commit hook installation per options.")
