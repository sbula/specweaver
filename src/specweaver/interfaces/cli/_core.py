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

import typer
from rich.console import Console

from specweaver._version import __version__

logger = logging.getLogger(__name__)


app = typer.Typer(
    name="sw",
    help="SpecWeaver \u2014 Specification-driven development lifecycle tool.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()

logger = logging.getLogger(__name__)

from specweaver.core.config.cli_db_utils import get_db


def _require_active_project() -> str:
    """Get the active project name or exit with error."""
    from specweaver.interfaces.cli._helpers import _run_workspace_op

    db = get_db()
    name = _run_workspace_op("get_active_project")
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
