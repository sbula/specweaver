# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""CLI commands for validation: check, list-rules."""

from __future__ import annotations

import logging
from pathlib import Path

import typer

from specweaver.cli import _core
from specweaver.cli._helpers import _display_results, _print_summary

logger = logging.getLogger(__name__)


def _resolve_pipeline_name(
    level: str,
    pipeline: str | None,
    active_project: str | None = None,
) -> str:
    """Resolve the YAML pipeline name from --pipeline, --level, or active profile.

    Thin CLI wrapper around
    :func:`specweaver.validation.pipeline_loader.resolve_pipeline_name`.
    Translates :class:`ValueError` into ``typer.Exit(1)``.
    """
    from specweaver.validation.pipeline_loader import resolve_pipeline_name

    db = _core.get_db()
    try:
        return resolve_pipeline_name(
            level,
            pipeline,
            db=db,
            active_project=active_project,
        )
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


def _build_result_label(level: str, pipeline: str | None, pipeline_name: str) -> str:
    """Return a human-readable label for the validation result output."""
    if pipeline:
        return pipeline_name
    if level == "feature":
        return "Feature"
    if level == "code":
        return "Code"
    return "Spec"


@_core.app.command()
def check(
    target: str = typer.Argument(
        "",
        help="Path to the spec or code file to check. Optional if using --lineage.",
    ),
    level: str = typer.Option(
        "component",
        "--level",
        "-l",
        help=(
            "Validation level: feature (spec, feature thresholds), "
            "component (spec, default thresholds), or code."
        ),
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory.",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Treat warnings as failures (exit code 1).",
    ),
    pipeline: str | None = typer.Option(
        None,
        "--pipeline",
        help="Name of the validation pipeline to use (e.g. validation_spec_library).",
    ),
    lineage: bool = typer.Option(
        False,
        "--lineage",
        help="Run a scan over the project's source tree to detect files missing lineage tags (orphans).",
    ),
) -> None:
    """Run validation rules against a spec or code file.

    Uses --level to determine which rule set to apply:
    - feature: Spec validation rules S01-S11 with feature-level thresholds
    - component: Spec validation rules S01-S11 with component-level thresholds (default)
    - code: Code validation rules C01-C08

    Use --pipeline to choose a specific validation pipeline by name.

    Override cascade is strictly pipeline YAML defaults -> applied pipeline configurations.
    """
    # Trigger auto-registration of built-in rules
    import specweaver.validation.rules.code
    import specweaver.validation.rules.spec  # noqa: F401
    from specweaver.validation.executor import execute_validation_pipeline
    from specweaver.validation.pipeline_loader import load_pipeline_yaml

    if lineage:
        from specweaver.cli.lineage import check_lineage

        db = _core.get_db()
        active = db.get_active_project()

        if project:
            proj_path = Path(project)
        elif active:
            proj_data = db.get_project(active)
            proj_path = Path(str(proj_data["root_path"])) if proj_data else Path.cwd()
        else:
            proj_path = Path.cwd()

        src_dir = proj_path / "src"

        orphans = check_lineage(src_dir)
        if orphans:
            _core.console.print("[red]Lineage Tracking Error:[/red] Missing '# sw-artifact:' tags.")
            for orphan in orphans:
                _core.console.print(f"  - {orphan}")
            raise typer.Exit(code=1)

        _core.console.print("[green]Lineage scan passed.[/green] All files correctly tagged.")
        return

    target_path = Path(target)
    if not target or not target_path.exists():
        _core.console.print(f"[red]Error:[/red] File not found: {target}")
        raise typer.Exit(code=1)

    try:
        content = target_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        _core.console.print(
            f"[red]Error:[/red] Cannot read '{target}': file is not valid UTF-8 text.",
        )
        raise typer.Exit(code=1) from None

    from specweaver.project.discovery import resolve_project_path
    db = _core.get_db()
    # Ensure project resolution handles implicit CWD and active project logic
    try:
        project_dir: Path | None = resolve_project_path(project)
    except Exception:
        # Fallback to None if not inside a valid project
        project_dir = Path(project) if project else None
        
    # Determine active project for profile-aware pipeline selection
    active = db.get_active_project()
    pipeline_name = _resolve_pipeline_name(level, pipeline, active_project=active)

    try:
        resolved = load_pipeline_yaml(pipeline_name, project_dir=project_dir)
    except FileNotFoundError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    results = execute_validation_pipeline(resolved, content, target_path)

    label = _build_result_label(level, pipeline, pipeline_name)
    _display_results(results, f"{label} Validation: {target_path.name}")
    _print_summary(results, strict=strict)


@_core.app.command("list-rules")
def list_rules(
    pipeline: str | None = typer.Option(
        None,
        "--pipeline",
        help="Show rules for a specific pipeline only.",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory (for project pipelines).",
    ),
) -> None:
    """List all validation rules, grouped by pipeline in execution order."""
    # Trigger auto-registration
    import specweaver.validation.rules.code
    import specweaver.validation.rules.spec  # noqa: F401
    from specweaver.validation.pipeline_loader import load_pipeline_yaml

    project_dir = Path(project) if project else None

    # Determine which pipelines to show
    if pipeline:
        pipeline_names = [pipeline]
    else:
        pipeline_names = ["validation_spec_default", "validation_code_default"]

    for pname in pipeline_names:
        try:
            resolved = load_pipeline_yaml(pname, project_dir=project_dir)
        except FileNotFoundError:
            _core.console.print(f"[yellow]Pipeline '{pname}' not found, skipping.[/yellow]")
            continue

        _core.console.print(f"\n[bold cyan]{resolved.name}[/bold cyan]", highlight=False)
        if resolved.description:
            _core.console.print(f"  [dim]{resolved.description.strip()}[/dim]")
        _core.console.print()

        for i, step in enumerate(resolved.steps, 1):
            params_str = ""
            if step.params:
                params_str = "  " + " ".join(f"[dim]{k}={v}[/dim]" for k, v in step.params.items())
            _core.console.print(f"  {i:>2}. [green]{step.rule}[/green]  {step.name}{params_str}")

        _core.console.print(f"\n  [dim]{len(resolved.steps)} rules total[/dim]")
