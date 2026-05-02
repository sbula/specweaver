# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI commands for config management: set/get/list/reset, log level,
constitution max size, and domain profiles."""

from __future__ import annotations

import logging

from typing import Any
import anyio
import typer
from rich.table import Table

from specweaver.infrastructure.llm.store import LlmRepository
from specweaver.workspace.store import WorkspaceRepository
from specweaver.interfaces.cli import _core

def _run_workspace_op(method_name: str, *args: Any) -> Any:
    db = _core.get_db()
    async def _action() -> Any:
        async with db.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            method = getattr(repo, method_name)
            return await method(*args)
    return anyio.run(_action)
from specweaver.interfaces.cli.config_routing import routing_app

logger = logging.getLogger(__name__)


logger = logging.getLogger(__name__)

config_app = typer.Typer(
    name="config",
    help="Manage per-project validation rule overrides.",
    no_args_is_help=True,
)
_core.app.add_typer(config_app, name="config")


@config_app.command("list")
def config_list() -> None:
    """List all validation rules currently applied via the active pipeline."""
    name = _core._require_active_project()
    
    profile_name = _run_workspace_op("get_domain_profile", name)
    if profile_name:
        _core.console.print(
            f"Validation rules for project [bold]{name}[/bold] are fully declarative "
            f"and managed by domain profile: [cyan]{profile_name}[/cyan].\n"
            f"Use 'sw config show-profile {profile_name}' to see the active thresholds."
        )
    else:
        _core.console.print(
            f"Validation rules for project [bold]{name}[/bold] are fully declarative "
            f"and managed by the default pipeline.\n"
            f"Use 'sw config profiles' to assign a domain profile."
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
        _run_workspace_op("set_log_level", name, level)
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
        level = _run_workspace_op("get_log_level", name)
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    from specweaver.logging import get_log_path

    log_path = get_log_path(name)
    _core.console.print(
        f"Log level for [bold]{name}[/bold]: [cyan]{level}[/cyan]\nLog file: [dim]{log_path}[/dim]",
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
        _run_workspace_op("set_constitution_max_size", name, size)
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
        max_size = _run_workspace_op("get_constitution_max_size", name)
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _core.console.print(
        f"Constitution max size for [bold]{name}[/bold]: [cyan]{max_size}[/cyan] bytes",
    )


@config_app.command("set-auto-bootstrap")
def config_set_auto_bootstrap(
    mode: str = typer.Argument(
        help="Auto-bootstrap mode: off, prompt, or auto.",
    ),
) -> None:
    """Set the auto-bootstrap mode for constitution generation.

    Controls what happens after 'sw standards scan' completes:
    - off:    Only print a hint about 'sw constitution bootstrap'.
    - prompt: Ask the user interactively (default).
    - auto:   Bootstrap silently without asking.
    """
    name = _core._require_active_project()
    db = _core.get_db()
    try:
        _run_workspace_op("set_auto_bootstrap", name, mode)
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _core.console.print(
        f"[green]\u2713[/green] Auto-bootstrap mode set to [bold]{mode.lower()}[/bold] "
        f"for project [bold]{name}[/bold].",
    )


@config_app.command("get-auto-bootstrap")
def config_get_auto_bootstrap() -> None:
    """Show the current auto-bootstrap mode for the active project."""
    name = _core._require_active_project()
    db = _core.get_db()
    try:
        mode = _run_workspace_op("get_auto_bootstrap", name)
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _core.console.print(
        f"Auto-bootstrap mode for [bold]{name}[/bold]: [cyan]{mode}[/cyan]",
    )


# -- Domain profile commands ------------------------------------------------


@config_app.command("profiles")
def config_profiles() -> None:
    """List all available domain profiles."""
    from specweaver.core.config.profiles import list_profiles

    profiles = list_profiles()

    if not profiles:
        _core.console.print(
            "[dim]No domain profiles found. "
            "Built-in profiles are automatically discovered from pipeline YAML files.[/dim]",
        )
        return

    table = Table(title="Available Domain Profiles")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Description")

    for p in profiles:
        table.add_row(p.name, p.description)

    _core.console.print(table)
    _core.console.print(
        "\n[dim]Use 'sw config set-profile <name>' to activate a profile.[/dim]",
    )


@config_app.command("show-profile")
def config_show_profile(
    profile_name: str = typer.Argument(help="Profile name to preview."),
) -> None:
    """Show the pipeline overrides a domain profile applies.

    Loads the profile's YAML pipeline and displays the rule parameters
    that differ from the base (validation_spec_default) pipeline.
    """
    import specweaver.assurance.validation.rules.spec  # noqa: F401
    from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml
    from specweaver.core.config.profiles import get_profile, profile_to_pipeline_name

    profile = get_profile(profile_name)
    if profile is None:
        _core.console.print(
            f"[red]Error:[/red] Unknown profile '{profile_name}'. "
            "Use 'sw config profiles' to list available profiles.",
        )
        raise typer.Exit(code=1)

    pipeline_name = profile_to_pipeline_name(profile.name)
    try:
        resolved = load_pipeline_yaml(pipeline_name)
    except FileNotFoundError:
        _core.console.print(
            f"[red]Error:[/red] Pipeline YAML for profile '{profile_name}' not found.",
        )
        raise typer.Exit(code=1) from None

    table = Table(
        title=f"Profile: {profile.name} \u2014 {profile.description or 'No description'}",
    )
    table.add_column("Rule", style="cyan")
    table.add_column("Parameter")
    table.add_column("Value", justify="right")

    for step in sorted(resolved.steps, key=lambda s: s.rule):
        for param_key, param_val in step.params.items():
            table.add_row(step.rule, param_key, str(param_val))

    _core.console.print(table)
    _core.console.print(
        f"\n[dim]Pipeline: {pipeline_name}.yaml "
        "| Rules not listed use base pipeline defaults.[/dim]",
    )


@config_app.command("set-profile")
def config_set_profile(
    profile_name: str = typer.Argument(help="Profile name to activate."),
) -> None:
    """Activate a domain profile for the active project.

    This records the profile name so that 'sw check' automatically
    selects the matching YAML pipeline.  It does NOT write any
    validation overrides to the database — those remain independent
    and are managed via 'sw config set <RULE>'.

    To deactivate, run 'sw config reset-profile'.
    """
    name = _core._require_active_project()
    try:
        _run_workspace_op("set_domain_profile", name, profile_name)
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _core.console.print(
        f"[green]\u2713[/green] Profile [bold]{profile_name}[/bold] activated for "
        f"project [bold]{name}[/bold]. "
        "'sw check' will now use the matching pipeline YAML.",
    )


@config_app.command("get-profile")
def config_get_profile() -> None:
    """Show the active domain profile for the current project."""
    name = _core._require_active_project()
    try:
        profile_name = _run_workspace_op("get_domain_profile", name)
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if profile_name:
        _core.console.print(
            f"Active profile for [bold]{name}[/bold]: [cyan]{profile_name}[/cyan]",
        )
    else:
        _core.console.print(
            f"[dim]No domain profile set for [bold]{name}[/bold] (using defaults).[/dim]",
        )


@config_app.command("reset-profile")
def config_reset_profile() -> None:
    """Deactivate the domain profile for the active project.

    Only the profile selection is cleared.  Any per-rule overrides set
    via 'sw config set <RULE>' are preserved — remove them individually
    with 'sw config reset <RULE>' if no longer needed.
    """
    name = _core._require_active_project()
    try:
        _run_workspace_op("clear_domain_profile", name)
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _core.console.print(
        f"[green]\u2713[/green] Profile deactivated for project [bold]{name}[/bold]. "
        "Per-rule overrides are preserved.",
    )


@config_app.command("set-provider")
def config_set_provider(
    provider: str = typer.Argument(help="LLM provider name (e.g., gemini, openai, anthropic)."),
    *,
    role: str = typer.Option("draft", help="Project role to set provider for."),
    model: str | None = typer.Option(
        None, help="Optional model name to override the provider default."
    ),
) -> None:
    """Set the LLM provider for a specific project role (default: draft)."""
    name = _core._require_active_project()
    db = _core.get_db()

    from specweaver.infrastructure.llm.adapters.registry import get_all_adapters

    adapters = get_all_adapters()
    if provider not in adapters:
        _core.console.print(
            f"[red]Error:[/red] Unknown provider '{provider}'. "
            f"Available: {', '.join(sorted(adapters.keys()))}",
        )
        raise typer.Exit(code=1)

    async def _update_provider() -> None:
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            profile = await repo.get_project_profile(name, role)

            if profile and not profile.is_global:
                update_args = {"provider": provider}
                if model is not None:
                    update_args["model"] = model
                await repo.update_llm_profile(profile.id, **update_args)

                _core.console.print(
                    f"[green]\u2713[/green] Updated existing custom profile for role [bold]{role}[/bold]. "
                    f"Provider set to [bold]{provider}[/bold].",
                )
            else:
                profile_name = f"{name}-{role}-profile"
                _model = model or "default"

                profile_id = await repo.create_llm_profile(
                    profile_name,
                    provider=provider,
                    model=_model,
                    is_global=False,
                )
                await repo.link_project_profile(name, role, profile_id)

                _core.console.print(
                    f"[green]\u2713[/green] Created new local profile for role [bold]{role}[/bold]. "
                    f"Provider set to [bold]{provider}[/bold].",
                )

    anyio.run(_update_provider)


# -- Model routing commands -------------------------------------------------

config_app.add_typer(routing_app, name="routing")
