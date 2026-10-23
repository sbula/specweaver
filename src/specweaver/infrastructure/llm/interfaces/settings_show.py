# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw config show` — every LLM setting in effect, what a call sends, and where each came from."""

from __future__ import annotations

from specweaver.core.config.llm_roles import resolve_roles, settings_report
from specweaver.core.config.settings_file import SettingsFileError
from specweaver.infrastructure.llm.catalogue import shipped_catalogue
from specweaver.infrastructure.llm.settings_view import role_rows
from specweaver.interfaces.cli import _core


def config_show() -> None:
    """Show every LLM setting in effect for the active project, with where each came from."""
    files = _core.load_active_llm_settings()
    try:
        roles = resolve_roles(files)
        rows = settings_report(files, roles, role_rows(files, roles, shipped_catalogue()))
    except SettingsFileError as err:
        _core.refuse_settings(err)
    for key, value, origin in rows:
        _core.console.print(f"{key} = {value}   ({origin})", markup=False, highlight=False)
