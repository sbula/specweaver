# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Core shared objects for the CLI package.

All submodules import this module (not individual names) so that
``monkeypatch.setattr("specweaver.cli._core.get_db", ...)`` works
in tests — the lookup goes through the module attribute, not a
local binding.
"""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console

from specweaver import __version__
from specweaver.config.database import Database

app = typer.Typer(
    name="sw",
    help="SpecWeaver \u2014 Specification-driven development lifecycle tool.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path.home() / ".specweaver" / "specweaver.db"


def get_db() -> Database:
    """Get the global SpecWeaver database (creates if needed)."""
    return Database(_DEFAULT_DB_PATH)


def _require_active_project() -> str:
    """Get the active project name or exit with error."""
    db = get_db()
    name = db.get_active_project()
    if not name:
        console.print(
            "[red]Error:[/red] No active project. "
            "Run [bold]sw init <name>[/bold] or [bold]sw use <name>[/bold].",
        )
        raise typer.Exit(code=1)
    return name


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"SpecWeaver v{__version__}")
        raise typer.Exit()
