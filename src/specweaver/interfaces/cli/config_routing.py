# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI commands for routing configuration."""

from __future__ import annotations

import logging

import anyio
import typer
from rich.table import Table

from specweaver.infrastructure.llm.models import TaskType
from specweaver.infrastructure.llm.store import LlmRepository
from specweaver.interfaces.cli import _core

logger = logging.getLogger(__name__)


# Derive valid values from the single source of truth (TaskType enum).
# Exclude UNKNOWN — it is not user-configurable.
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
