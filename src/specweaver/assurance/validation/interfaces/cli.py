# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI commands for validation and AST drift detection."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.table import Table

from specweaver.interfaces.cli import _core
from specweaver.workspace.project.discovery import resolve_project_path
from specweaver.workspace.project.interfaces.cli import _run_workspace_op

if TYPE_CHECKING:
    from specweaver.assurance.validation.models import RuleResult

logger = logging.getLogger(__name__)

# Status display mapping (shared across check command)
_STATUS_STYLE = {
    "pass": "[green]PASS[/green]",
    "fail": "[red]FAIL[/red]",
    "warn": "[yellow]WARN[/yellow]",
    "skip": "[dim]SKIP[/dim]",
}


def _display_results(
    results: list[RuleResult],
    title: str,
) -> None:
    """Display validation results as a Rich table with findings."""
    from specweaver.assurance.validation.models import Status

    table = Table(title=title)
    table.add_column("Rule", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Status", justify="center")
    table.add_column("Message", style="dim")

    for r in results:
        table.add_row(
            r.rule_id,
            r.rule_name,
            _STATUS_STYLE.get(r.status.value, str(r.status)),
            r.message[:80] if r.message else "",
        )
    _core.console.print(table)

    # Show detailed findings for failed/warned rules
    for r in results:
        if r.findings and r.status in (Status.FAIL, Status.WARN):
            _core.console.print(
                f"\n[bold]{r.rule_id} {r.rule_name}[/bold] findings:",
            )
            for f in r.findings:
                line_info = f" (line {f.line})" if f.line else ""
                _core.console.print(
                    f"  [{f.severity.value}] {f.message}{line_info}",
                )
                if f.suggestion:
                    _core.console.print(f"    [dim]-> {f.suggestion}[/dim]")


def _print_summary(results: list[RuleResult], *, strict: bool = False) -> None:
    """Print pass/fail summary and raise Exit(1) on failures.

    Args:
        results: Validation results to summarize.
        strict: If True, WARNs also cause exit code 1.
    """
    from specweaver.assurance.validation.models import Status

    fail_count = sum(1 for r in results if r.status == Status.FAIL)
    warn_count = sum(1 for r in results if r.status == Status.WARN)

    if fail_count > 0:
        _core.console.print(
            f"\n[red]FAILED[/red]: {fail_count} rule(s) failed, {warn_count} warning(s)",
        )
        raise typer.Exit(code=1)
    if warn_count > 0:
        _core.console.print(
            f"\n[yellow]PASSED with warnings[/yellow]: {warn_count} warning(s)",
        )
        if strict:
            raise typer.Exit(code=1)
    else:
        _core.console.print("\n[green]ALL PASSED[/green]")


def _resolve_pipeline_name(
    level: str,
    pipeline: str | None,
    active_project: str | None = None,
) -> str:
    """Resolve the YAML pipeline name from --pipeline, --level, or active profile.

    Thin CLI wrapper around
    :func:`specweaver.assurance.validation.pipeline_loader.resolve_pipeline_name`.
    Translates :class:`ValueError` into ``typer.Exit(1)``.
    """
    import contextlib

    from specweaver.assurance.validation.pipeline_loader import resolve_pipeline_name

    active_profile = None
    if active_project:
        with contextlib.suppress(ValueError, Exception):
            active_profile = _run_workspace_op("get_domain_profile", active_project)

    try:
        return resolve_pipeline_name(
            level,
            pipeline,
            active_profile=active_profile,
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


validation_cli = typer.Typer(no_args_is_help=True)


@validation_cli.command(name="check")
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
    import specweaver.assurance.validation.rules.code
    import specweaver.assurance.validation.rules.spec  # noqa: F401
    from specweaver.assurance.validation.executor import execute_validation_pipeline
    from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml

    if lineage:
        from specweaver.graph.interfaces.cli import check_lineage

        _core.get_db()
        active = _run_workspace_op("get_active_project")

        if project:
            proj_path = Path(project)
        elif active:
            proj_data = _run_workspace_op("get_project", active)
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


    _core.get_db()
    # Ensure project resolution handles implicit CWD and active project logic
    try:
        project_dir: Path | None = resolve_project_path(project)
    except Exception:
        # Fallback to None if not inside a valid project
        project_dir = Path(project) if project else None

    # Determine active project for profile-aware pipeline selection
    active = _run_workspace_op("get_active_project")
    pipeline_name = _resolve_pipeline_name(level, pipeline, active_project=active)

    try:
        resolved = load_pipeline_yaml(pipeline_name, project_dir=project_dir)
    except FileNotFoundError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    from specweaver.core.config.dal_resolver import DALResolver

    project_root = project_dir or Path.cwd()
    dal_resolver = DALResolver(project_root)
    dal_level = dal_resolver.resolve(target_path)
    effective_strict = strict or (dal_level.is_strict if dal_level else False)

    results = execute_validation_pipeline(resolved, content, target_path)

    label = _build_result_label(level, pipeline, pipeline_name)
    dal_str = dal_level.value if dal_level else "Unbound"
    _display_results(results, f"{label} Validation: {target_path.name} (DAL: {dal_str})")
    _print_summary(results, strict=effective_strict)


@validation_cli.command("list-rules")
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
    import specweaver.assurance.validation.rules.code
    import specweaver.assurance.validation.rules.spec  # noqa: F401
    from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml

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

from specweaver.assurance.validation.interfaces.cli_drift import drift_app  # noqa: E402

validation_cli.add_typer(drift_app, name="drift")



