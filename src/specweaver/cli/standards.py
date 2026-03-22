# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""CLI commands for standards management: scan, show, clear, scopes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import typer
from rich.table import Table

from specweaver.cli import _core

if TYPE_CHECKING:
    from specweaver.config.database import Database
    from specweaver.standards.analyzer import CategoryResult

standards_app = typer.Typer(
    name="standards",
    help="Auto-discover and manage coding standards for the active project.",
    no_args_is_help=True,
)
_core.app.add_typer(standards_app, name="standards")


@standards_app.command("scan")
def standards_scan(
    scope: str | None = typer.Option(
        None,
        "--scope",
        "-s",
        help="Scan only this scope (e.g., 'backend/auth').",
    ),
    no_review: bool = typer.Option(
        False,
        "--no-review",
        help="Skip HITL review, auto-accept all (CI mode).",
    ),
    compare: bool = typer.Option(
        False,
        "--compare",
        help="Force LLM best-practice comparison.",
    ),
) -> None:
    """Scan the active project and auto-discover coding standards.

    Detects scopes (up to 2 levels deep), analyses source files per scope,
    and presents a combined HITL review (unless --no-review is set).
    """
    import asyncio

    from specweaver.llm.adapters.gemini import GeminiAdapter
    from specweaver.standards.discovery import discover_files
    from specweaver.standards.enricher import StandardsEnricher
    from specweaver.standards.reviewer import StandardsReviewer
    from specweaver.standards.scanner import StandardsScanner
    from specweaver.standards.scope_detector import detect_scopes

    name = _core._require_active_project()
    db = _core.get_db()
    proj = db.get_project(name)
    if proj is None:
        _core.console.print(f"[red]Error:[/red] Project '{name}' not found.")
        raise typer.Exit(code=1)
    project_path = Path(str(proj["root_path"]))

    if not project_path.exists():
        _core.console.print(
            f"[red]Error:[/red] Project root does not exist: {project_path}",
        )
        raise typer.Exit(code=1)

    _core.console.print(f"[bold]Scanning standards for[/bold] [cyan]{name}[/cyan]")
    _core.console.print(f"  [dim]Root: {project_path}[/dim]\n")

    # Detect scopes
    scopes = [scope] if scope else detect_scopes(project_path)

    _core.console.print(f"  Detected [bold]{len(scopes)}[/bold] scope(s): {', '.join(scopes)}\n")

    # Discover all files once
    all_files = discover_files(project_path)

    scanner = StandardsScanner()
    enricher = StandardsEnricher(GeminiAdapter())
    half_life_days = 90.0

    # Scan each scope
    scope_results: dict[str, list[CategoryResult]] = {}

    for s in scopes:
        scope_path = project_path if s == "." else project_path / s

        # Filter files to this scope
        scope_files = [
            f for f in all_files
            if _file_in_scope(f, scope_path, project_path, s, scopes)
        ]

        if not scope_files:
            continue

        _core.console.print(
            f"  Scope [cyan]{s}[/cyan]: {len(scope_files)} source files",
        )

        raw_results = scanner.scan(scope_files, half_life_days)
        results = [r for r in raw_results if r.confidence >= 0.3]

        if results:
            asyncio.run(enricher.enrich(results, language="auto", force_compare=compare))
            scope_results[s] = results

    if not scope_results:
        _core.console.print("\n[yellow]No standards discovered above confidence threshold.[/yellow]")
        return

    # Load existing for re-scan diff
    existing_by_scope: dict[str, list[dict[str, Any]]] = {}
    for s in scope_results:
        existing_by_scope[s] = db.get_standards(name, scope=s)

    # HITL review
    if no_review:
        accepted = scope_results
    else:
        reviewer = StandardsReviewer(console=_core.console)
        accepted = reviewer.review(scope_results, existing=existing_by_scope)

    # Save accepted standards
    saved = _save_accepted_standards(db, name, accepted, no_review=no_review)

    _core.console.print(
        f"\n[bold]Scan complete[/bold]: {saved} standards saved "
        f"for project [bold]{name}[/bold].",
    )

    # Bootstrap hint: if standards were saved and no constitution exists
    # (or it's still the unmodified starter), offer to bootstrap.
    if saved > 0:
        _maybe_bootstrap_constitution(
            project_path=project_path,
            project_name=name,
            db=db,
            accepted=accepted,
            no_review=no_review,
        )


def _save_accepted_standards(
    db: Database,
    project_name: str,
    accepted: dict[str, list[CategoryResult]],
    no_review: bool,
) -> int:
    """Helper to save accepted standards to the database."""
    saved = 0
    for s, results in accepted.items():
        for result in results:
            confirmed = "hitl" if not no_review else None
            db.save_standard(
                project_name=project_name,
                scope=s,
                language=result.language or "unknown",
                category=result.category,
                data=dict(result.dominant),
                confidence=result.confidence,
                confirmed_by=confirmed,
            )
            saved += 1
            _core.console.print(
                f"  [green]\u2713[/green] [{s}] {result.category}: "
                f"confidence={result.confidence:.0%}",
            )
    return saved


def _maybe_bootstrap_constitution(
    *,
    project_path: Path,
    project_name: str,
    db: Database,
    accepted: dict[str, list[CategoryResult]],
    no_review: bool,
) -> None:
    """Optionally bootstrap CONSTITUTION.md after a scan, based on config.

    Respects the ``auto_bootstrap_constitution`` setting:
    - ``auto``: bootstrap silently.
    - ``prompt``: ask the user (unless ``--no-review``).
    - ``off``: print a hint.
    """
    from specweaver.project.constitution import (
        CONSTITUTION_FILENAME,
        generate_constitution_from_standards,
        is_unmodified_starter,
    )

    constitution_path = project_path / CONSTITUTION_FILENAME
    needs_bootstrap = (
        not constitution_path.exists()
        or is_unmodified_starter(constitution_path)
    )

    if not needs_bootstrap:
        return

    bootstrap_mode = db.get_auto_bootstrap(project_name)
    languages = sorted({
        r.language or "unknown"
        for results in accepted.values()
        for r in results
    })

    if bootstrap_mode == "auto":
        all_standards = db.get_standards(project_name)
        project_slug = project_path.name.lower().replace(" ", "-")
        result = generate_constitution_from_standards(
            project_path, project_slug, all_standards, languages,
        )
        if result:
            _core.console.print(
                f"\n[green]\u2713[/green] CONSTITUTION.md auto-bootstrapped "
                f"from {len(all_standards)} standards.",
            )
    elif bootstrap_mode == "prompt" and not no_review:
        do_bootstrap = typer.confirm(
            "\nBootstrap CONSTITUTION.md from these standards?",
            default=True,
        )
        if do_bootstrap:
            all_standards = db.get_standards(project_name)
            project_slug = project_path.name.lower().replace(" ", "-")
            result = generate_constitution_from_standards(
                project_path, project_slug, all_standards, languages,
            )
            if result:
                _core.console.print(
                    f"[green]\u2713[/green] CONSTITUTION.md bootstrapped: "
                    f"[bold]{result}[/bold]",
                )
    else:
        # mode == "off" or (mode == "prompt" and no_review)
        _core.console.print(
            "\n[dim]Tip: Run 'sw constitution bootstrap' to generate "
            "CONSTITUTION.md from these standards.[/dim]",
        )


def _file_in_scope(
    file_path: Path,
    scope_path: Path,
    project_path: Path,
    scope_name: str,
    all_scopes: list[str],
) -> bool:
    """Check if a file belongs to a specific scope.

    For root scope ("."), only files not in any other scope are included.
    For named scopes, files must be under that scope's directory.
    """
    try:
        file_path.relative_to(scope_path)
    except ValueError:
        return False

    if scope_name == ".":
        # Root scope: exclude files that belong to any named scope
        for other in all_scopes:
            if other == ".":
                continue
            other_path = project_path / other
            try:
                file_path.relative_to(other_path)
                return False  # File belongs to a more specific scope
            except ValueError:
                continue
        return True

    return True


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
        data: dict[str, object] = json.loads(s["data"]) if isinstance(s["data"], str) else cast("dict[str, object]", s["data"])
        patterns = ", ".join(f"{k}={v}" for k, v in data.items())
        conf_str = f"{float(str(s['confidence'])):.0%}"
        confirmed = str(s.get("confirmed_by") or "[dim]\u2014[/dim]")
        table.add_row(
            str(s["scope"]),
            str(s["language"]),
            str(s["category"]),
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


@standards_app.command("scopes")
def standards_scopes() -> None:
    """Show a summary of detected and stored scopes."""
    name = _core._require_active_project()
    db = _core.get_db()

    stored_scopes = db.list_scopes(name)

    if not stored_scopes:
        _core.console.print(
            f"[dim]No scopes found for project [bold]{name}[/bold]. "
            "Run [bold]sw standards scan[/bold] first.[/dim]",
        )
        return

    table = Table(title=f"Scopes ({name})")
    table.add_column("Scope", style="cyan")
    table.add_column("Language")
    table.add_column("Categories", justify="right")
    table.add_column("Last Scanned")

    for scope_name in stored_scopes:
        standards = db.get_standards(name, scope=scope_name)
        if not standards:
            continue
        languages_str = sorted({str(s["language"]) for s in standards})
        cats = len(standards)
        last_scanned = max((str(s.get("scanned_at") or "") for s in standards), default="")
        table.add_row(
            scope_name,
            ", ".join(languages_str),
            str(cats),
            last_scanned[:10] if last_scanned else "[dim]\u2014[/dim]",
        )

    _core.console.print(table)

