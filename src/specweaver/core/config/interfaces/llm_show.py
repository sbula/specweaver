# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw config show` — every effective LLM setting, and the file and line it came from."""

from __future__ import annotations

from pathlib import Path

import typer

from specweaver.core.config.bootstrap.llm_settings_loader import load_llm_settings
from specweaver.core.config.llm_settings import SettingsFileError, resolve_roles, settings_report
from specweaver.interfaces.cli import _core


def config_show() -> None:
    """Show every LLM setting in effect for the active project, with where each came from."""
    name = _core._require_active_project()
    project = _core.run_repo_op(lambda repo: repo.get_project(name))
    root = project.get("root_path") if project else None
    try:
        files = load_llm_settings(Path(str(root)) if root else None)
        rows = settings_report(files, resolve_roles(files))
    except SettingsFileError as err:
        _core.console.print("Error:", str(err), style="red", markup=False, highlight=False)
        raise typer.Exit(code=1) from err
    for key, value, origin in rows:
        _core.console.print(f"{key} = {value}   ({origin})", markup=False, highlight=False)
