# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI commands for config management: set/get/list/reset, log level,
constitution max size, and domain profiles, plus model routing."""

from __future__ import annotations

import logging
from typing import Any

import anyio
import typer
from rich.table import Table

from specweaver.infrastructure.llm.models import TaskType
from specweaver.infrastructure.llm.store import LlmRepository
from specweaver.interfaces.cli import _core
from specweaver.workspace.store import WorkspaceRepository

logger = logging.getLogger(__name__)


def _run_workspace_op(method_name: str, *args: Any) -> Any:
    db = _core.get_db()

    async def _action() -> Any:
        async with db.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            method = getattr(repo, method_name)
            return await method(*args)

    return anyio.run(_action)


# -- Config App -------------------------------------------------------------

config_app = typer.Typer(
    name="config",
    help="Manage per-project configuration and routing.",
    no_args_is_help=True,
)


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
    """Show the pipeline overrides a domain profile applies."""
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
    """Activate a domain profile for the active project."""
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
    """Deactivate the domain profile for the active project."""
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


# -- Routing App ------------------------------------------------------------

_ROUTABLE_TASK_TYPES: frozenset[str] = frozenset(t.value for t in TaskType if t != TaskType.UNKNOWN)

routing_app = typer.Typer(
    name="routing",
    help="Manage per-task-type LLM model routing.",
    no_args_is_help=True,
)


@routing_app.command("set")
def routing_set(
    task_type: str = typer.Argument(
        help=f"Task type ({', '.join(sorted(_ROUTABLE_TASK_TYPES))}).",
    ),
    profile_name: str = typer.Argument(help="Name of an existing LLM profile."),
) -> None:
    """Link a task type to a specific LLM profile for routing."""
    name = _core._require_active_project()
    task_lower = task_type.lower()

    if task_lower not in _ROUTABLE_TASK_TYPES:
        _core.console.print(
            f"[red]Error:[/red] Invalid task type '{task_type}'. "
            f"Valid: {', '.join(sorted(_ROUTABLE_TASK_TYPES))}",
        )
        raise typer.Exit(code=1)

    db = _core.get_db()

    async def _routing_set() -> None:
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            profile = await repo.get_llm_profile_by_name(profile_name)
            if profile is None:
                _core.console.print(
                    f"[red]Error:[/red] Profile '{profile_name}' not found. "
                    "Use 'sw config set-provider' to create one first.",
                )
                raise typer.Exit(code=1)

            try:
                await repo.link_project_profile(name, f"task:{task_lower}", profile.id)
            except ValueError as exc:
                _core.console.print(f"[red]Error:[/red] {exc}")
                raise typer.Exit(code=1) from exc

            _core.console.print(
                f"[green]\u2713[/green] Routing: [bold]{task_lower}[/bold] \u2192 "
                f"profile [bold]{profile_name}[/bold] "
                f"(provider={profile.provider}, model={profile.model}).",
            )

    anyio.run(_routing_set)


@routing_app.command("show")
def routing_show() -> None:
    """Show the routing table for the active project."""
    name = _core._require_active_project()
    db = _core.get_db()

    async def _routing_show() -> None:
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            entries = await repo.get_project_routing_entries(name)

            if not entries:
                _core.console.print(
                    "[dim]No routing configured. All tasks use the default profile.[/dim]",
                )
                return

            table = Table(title=f"Model Routing ({name})")
            table.add_column("Task Type", style="cyan")
            table.add_column("Profile")
            table.add_column("Provider")
            table.add_column("Model")
            table.add_column("Temperature", justify="right")

            for entry in entries:
                profile = await repo.get_llm_profile(entry["profile_id"])  # type: ignore
                if profile:
                    table.add_row(
                        str(entry["task_type"]),
                        str(entry["profile_name"]),
                        str(profile.provider),
                        str(profile.model),
                        str(profile.temperature),
                    )
                else:
                    table.add_row(
                        str(entry["task_type"]),
                        str(entry["profile_name"]),
                        "[red]\\[deleted][/red]",
                        "[red]\\[deleted][/red]",
                        "[dim]\u2014[/dim]",
                    )
            _core.console.print(table)

    anyio.run(_routing_show)


@routing_app.command("clear")
def routing_clear(
    task_type: str | None = typer.Argument(
        None,
        help="Task type to clear (omit to clear all).",
    ),
) -> None:
    """Clear routing entries for the active project."""
    name = _core._require_active_project()
    db = _core.get_db()

    async def _routing_clear() -> None:
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            if task_type is not None:
                task_lower = task_type.lower()
                if task_lower not in _ROUTABLE_TASK_TYPES:
                    _core.console.print(
                        f"[red]Error:[/red] Invalid task type '{task_type}'. "
                        f"Valid: {', '.join(sorted(_ROUTABLE_TASK_TYPES))}",
                    )
                    raise typer.Exit(code=1)

                removed = await repo.unlink_project_profile(name, f"task:{task_lower}")
                if removed:
                    _core.console.print(
                        f"[green]\u2713[/green] Cleared routing for [bold]{task_lower}[/bold].",
                    )
                else:
                    _core.console.print(
                        f"[dim]No routing entry for '{task_lower}' to clear.[/dim]",
                    )
            else:
                count = await repo.clear_all_project_routing(name)
                if count:
                    _core.console.print(
                        f"[green]\u2713[/green] Cleared all {count} routing entries.",
                    )
                else:
                    _core.console.print("[dim]No routing entries to clear.[/dim]")

    anyio.run(_routing_clear)


config_app.add_typer(routing_app, name="routing")
