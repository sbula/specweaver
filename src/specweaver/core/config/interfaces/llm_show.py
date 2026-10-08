# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw config set-role` — set which model a role uses, in its settings file."""

from __future__ import annotations

import typer

from specweaver.core.config.bootstrap.llm_settings_writer import set_role
from specweaver.core.config.llm_settings import SettingsFileError
from specweaver.interfaces.cli import _core


def config_set_role(
    role: str = typer.Argument(help="draft, review, plan, implement, validate, check or default."),
    model: str = typer.Argument(help="model@server, e.g. qwen3-coder-next@gb10."),
    project: bool = typer.Option(
        False, "--project", help="Set it for the active project only, in its specweaver.toml."
    ),
) -> None:
    """Set which model a role uses — on this machine, or for the active project with --project."""
    root = _core.project_root(_core._require_active_project()) if project else None
    if project and root is None:
        _core.console.print("[red]Error:[/red] the active project has no root directory.")
        raise typer.Exit(code=1)
    try:
        path = set_role(role, model, project_root=root)
    except SettingsFileError as err:
        _core.refuse_llm_settings(err)
    _core.console.print(f"roles.{role} = {model}   ({path})", markup=False, highlight=False)
