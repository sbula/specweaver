# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw config show` — every effective LLM setting, and the file and line it came from."""

from __future__ import annotations

import typer

from specweaver.core.config.llm_settings import SettingsFileError, resolve_roles, settings_report
from specweaver.interfaces.cli import _core


def config_show() -> None:
    """Show every LLM setting in effect for the active project, with where each came from."""
    files = _core.load_active_llm_settings()
    try:
        rows = settings_report(files, resolve_roles(files))
    except SettingsFileError as err:
        _core.console.print("Error:", str(err), style="red", markup=False, highlight=False)
        raise typer.Exit(code=1) from err
    for key, value, origin in rows:
        _core.console.print(f"{key} = {value}   ({origin})", markup=False, highlight=False)
