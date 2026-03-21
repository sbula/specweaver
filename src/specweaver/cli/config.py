# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""CLI commands for config management: set/get/list/reset, log level,
constitution max size, and domain profiles."""

from __future__ import annotations

import logging

import typer
from rich.table import Table

from specweaver.cli import _core

logger = logging.getLogger(__name__)

config_app = typer.Typer(
    name="config",
    help="Manage per-project validation rule overrides.",
    no_args_is_help=True,
)
_core.app.add_typer(config_app, name="config")


@config_app.command("set")
def config_set(
    rule_id: str = typer.Argument(help="Rule ID (e.g. S08, C04)."),
    *,
    enabled: bool | None = typer.Option(None, help="Enable/disable the rule."),
    warn: float | None = typer.Option(None, "--warn", help="Warning threshold."),
    fail: float | None = typer.Option(None, "--fail", help="Failure threshold."),
) -> None:
    """Set a validation override for the active project."""
    name = _core._require_active_project()
    rule_upper = rule_id.upper()

    if enabled is None and warn is None and fail is None:
        _core.console.print(
            "[red]Error:[/red] Provide at least one of "
            "--enabled/--no-enabled, --warn, --fail.",
        )
        raise typer.Exit(code=1)

    db = _core.get_db()
    db.set_validation_override(
        name,
        rule_upper,
        enabled=enabled,
        warn_threshold=warn,
        fail_threshold=fail,
    )

    parts: list[str] = []
    if enabled is not None:
        parts.append(f"enabled={enabled}")
    if warn is not None:
        parts.append(f"warn={warn}")
    if fail is not None:
        parts.append(f"fail={fail}")

    _core.console.print(
        f"[green]\u2713[/green] Override set for [bold]{rule_upper}[/bold] "
        f"({', '.join(parts)}) on project [bold]{name}[/bold].",
    )


@config_app.command("get")
def config_get(
    rule_id: str = typer.Argument(help="Rule ID to query."),
) -> None:
    """Show the current override for a rule in the active project."""
    name = _core._require_active_project()
    rule_upper = rule_id.upper()

    db = _core.get_db()
    o = db.get_validation_override(name, rule_upper)

    if o is None:
        _core.console.print(
            f"[dim]No override for [bold]{rule_upper}[/bold] "
            f"on project [bold]{name}[/bold] (using defaults).[/dim]",
        )
        return

    table = Table(title=f"Override: {rule_upper} ({name})")
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("enabled", str(bool(o["enabled"])))
    table.add_row("warn_threshold", str(o["warn_threshold"]))
    table.add_row("fail_threshold", str(o["fail_threshold"]))
    _core.console.print(table)


@config_app.command("list")
def config_list() -> None:
    """List all validation overrides for the active project."""
    name = _core._require_active_project()

    db = _core.get_db()
    overrides = db.get_validation_overrides(name)

    if not overrides:
        _core.console.print(
            f"[dim]No overrides configured for project [bold]{name}[/bold] "
            "(all rules use defaults).[/dim]",
        )
        return

    table = Table(title=f"Validation Overrides ({name})")
    table.add_column("Rule", style="cyan")
    table.add_column("Enabled")
    table.add_column("Warn Threshold")
    table.add_column("Fail Threshold")

    for o in overrides:
        table.add_row(
            o["rule_id"],
            "[green]Yes[/green]" if o["enabled"] else "[red]No[/red]",
            str(o["warn_threshold"]) if o["warn_threshold"] is not None else "[dim]\u2014[/dim]",
            str(o["fail_threshold"]) if o["fail_threshold"] is not None else "[dim]\u2014[/dim]",
        )

    _core.console.print(table)


@config_app.command("reset")
def config_reset(
    rule_id: str = typer.Argument(help="Rule ID to reset (removes override)."),
) -> None:
    """Remove the override for a rule, reverting to defaults."""
    name = _core._require_active_project()
    rule_upper = rule_id.upper()

    db = _core.get_db()
    db.delete_validation_override(name, rule_upper)

    _core.console.print(
        f"[green]\u2713[/green] Override removed for [bold]{rule_upper}[/bold] "
        f"on project [bold]{name}[/bold] (using defaults).",
    )


@config_app.command("set-log-level")
def config_set_log_level(
    level: str = typer.Argument(
        help="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL.",
    ),
) -> None:
    """Set the log level for the active project."""
    name = _core._require_active_project()
    db = _core.get_db()
    try:
        db.set_log_level(name, level)
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _core.console.print(
        f"[green]\u2713[/green] Log level set to [bold]{level.upper()}[/bold] "
        f"for project [bold]{name}[/bold].",
    )
    logger.info("Log level changed to %s for project %s", level.upper(), name)


@config_app.command("get-log-level")
def config_get_log_level() -> None:
    """Show the current log level for the active project."""
    name = _core._require_active_project()
    db = _core.get_db()
    try:
        level = db.get_log_level(name)
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    from specweaver.logging import get_log_path

    log_path = get_log_path(name)
    _core.console.print(
        f"Log level for [bold]{name}[/bold]: [cyan]{level}[/cyan]\n"
        f"Log file: [dim]{log_path}[/dim]",
    )


@config_app.command("set-constitution-max-size")
def config_set_constitution_max_size(
    size: int = typer.Argument(
        help="Maximum constitution file size in bytes. Must be positive.",
    ),
) -> None:
    """Set the maximum allowed CONSTITUTION.md size for the active project."""
    name = _core._require_active_project()
    db = _core.get_db()
    try:
        db.set_constitution_max_size(name, size)
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _core.console.print(
        f"[green]\u2713[/green] Constitution max size set to "
        f"[bold]{size}[/bold] bytes for project [bold]{name}[/bold].",
    )


@config_app.command("get-constitution-max-size")
def config_get_constitution_max_size() -> None:
    """Show the current constitution max size for the active project."""
    name = _core._require_active_project()
    db = _core.get_db()
    try:
        max_size = db.get_constitution_max_size(name)
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _core.console.print(
        f"Constitution max size for [bold]{name}[/bold]: "
        f"[cyan]{max_size}[/cyan] bytes",
    )


# -- Domain profile commands ------------------------------------------------


@config_app.command("profiles")
def config_profiles() -> None:
    """List all available domain profiles."""
    from specweaver.config.profiles import list_profiles

    profiles = list_profiles()

    table = Table(title="Available Domain Profiles")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Description")
    table.add_column("Overrides", justify="right")

    for p in profiles:
        table.add_row(p.name, p.description, str(len(p.overrides)))

    _core.console.print(table)


@config_app.command("show-profile")
def config_show_profile(
    profile_name: str = typer.Argument(help="Profile name to preview."),
) -> None:
    """Show the overrides a domain profile would apply."""
    from specweaver.config.profiles import get_profile

    profile = get_profile(profile_name)
    if profile is None:
        _core.console.print(
            f"[red]Error:[/red] Unknown profile '{profile_name}'. "
            "Use 'sw config profiles' to list available profiles.",
        )
        raise typer.Exit(code=1)

    table = Table(title=f"Profile: {profile.name} -- {profile.description}")
    table.add_column("Rule", style="cyan")
    table.add_column("Warn", justify="right")
    table.add_column("Fail", justify="right")

    for rule_id, override in sorted(profile.overrides.items()):
        warn_str = str(override.warn_threshold) if override.warn_threshold is not None else "-"
        fail_str = str(override.fail_threshold) if override.fail_threshold is not None else "-"
        table.add_row(rule_id, warn_str, fail_str)

    _core.console.print(table)
    _core.console.print(
        "\n[dim]Rules not listed use code defaults.[/dim]",
    )


@config_app.command("set-profile")
def config_set_profile(
    profile_name: str = typer.Argument(help="Profile name to apply."),
) -> None:
    """Apply a domain profile to the active project.

    This clears all existing validation overrides and replaces them
    with the profile's preset values.
    """
    name = _core._require_active_project()
    db = _core.get_db()
    try:
        db.set_domain_profile(name, profile_name)
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    from specweaver.config.profiles import get_profile

    profile = get_profile(profile_name)
    count = len(profile.overrides) if profile else 0
    _core.console.print(
        f"[green]\u2713[/green] Profile [bold]{profile_name}[/bold] applied to "
        f"project [bold]{name}[/bold] ({count} rule overrides set).",
    )


@config_app.command("get-profile")
def config_get_profile() -> None:
    """Show the active domain profile for the current project."""
    name = _core._require_active_project()
    db = _core.get_db()
    try:
        profile_name = db.get_domain_profile(name)
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if profile_name:
        _core.console.print(
            f"Active profile for [bold]{name}[/bold]: "
            f"[cyan]{profile_name}[/cyan]",
        )
    else:
        _core.console.print(
            f"[dim]No domain profile set for [bold]{name}[/bold] "
            f"(using defaults).[/dim]",
        )


@config_app.command("reset-profile")
def config_reset_profile() -> None:
    """Clear the domain profile and all validation overrides."""
    name = _core._require_active_project()
    db = _core.get_db()
    try:
        db.clear_domain_profile(name)
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _core.console.print(
        f"[green]\u2713[/green] Profile and all overrides cleared "
        f"for project [bold]{name}[/bold].",
    )
