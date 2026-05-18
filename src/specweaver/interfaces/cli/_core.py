# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Core shared objects for the CLI package.

All submodules import this module (not individual names) so that
``monkeypatch.setattr("specweaver.interfaces.cli._core.get_db", ...)`` works
in tests — the lookup goes through the module attribute, not a
local binding.
"""

from __future__ import annotations

import logging
from typing import TypeVar

import anyio
import typer
from rich.console import Console

from specweaver._version import __version__
from specweaver.core.config.db_bootstrap import get_db

logger = logging.getLogger(__name__)
app = typer.Typer(
    name="sw",
    help="SpecWeaver \u2014 Specification-driven development lifecycle tool.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()

_T = TypeVar("_T")

__all__ = ["_require_active_project", "app", "console", "get_db", "logger", "run_repo_op"]


def run_repo_op(fn):
    """Run a typed WorkspaceRepository operation synchronously (CLI only).

    Replaces the string-dispatched ``_run_workspace_op`` anti-pattern.
    Each caller passes a typed coroutine function (lambda or async def),
    giving IDE autocomplete and grep-ability.

    Example::

        active = run_repo_op(lambda r: r.get_active_project())
        proj = run_repo_op(lambda r: r.get_project(name))

    Warning: This is CLI-only infrastructure. API handlers must use
    async sessions directly via FastAPI dependency injection.
    """
    from specweaver.workspace.store import WorkspaceRepository

    db = get_db()

    async def _action():
        async with db.async_session_scope() as session:
            return await fn(WorkspaceRepository(session))

    return anyio.run(_action)


def _require_active_project() -> str:
    """Get the active project name or exit with error."""
    logger.debug("Executing _require_active_project")
    get_db()
    name_raw = run_repo_op(lambda r: r.get_active_project())
    if not name_raw:
        console.print(
            "[red]Error:[/red] No active project. "
            "Run [bold]sw init <name>[/bold] or [bold]sw use <name>[/bold].",
        )
        raise typer.Exit(code=1)
    return str(name_raw)


def _version_callback(value: bool) -> None:
    logger.debug("Executing _version_callback (value=%s)", value)
    if value:
        console.print(f"SpecWeaver v{__version__}")
        raise typer.Exit()

