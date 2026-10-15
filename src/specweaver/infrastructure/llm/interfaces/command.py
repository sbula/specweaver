# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The one way a CLI command gets its models: the router, from its target project's settings."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer
from pydantic import ValidationError

from specweaver.core.config.llm_settings import RoleEntry, SettingNotSetError, SettingsFileError
from specweaver.infrastructure.llm.router import build_router
from specweaver.interfaces.cli import _core

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from specweaver.infrastructure.llm.models import TaskType
    from specweaver.infrastructure.llm.router import ModelRouter


def run_model_option(value: str | None) -> RoleEntry | None:
    """The `--model <model@server>` value; a malformed one stops the command before any call."""
    if value is None:
        return None
    try:
        return RoleEntry.model_validate(value)
    except ValidationError as err:
        message = err.errors()[0]["msg"].removeprefix("Value error, ")
        _core.console.print(f"Error: --model {value}: {message}", style="red", markup=False)
        raise typer.Exit(code=1) from err


def command_router(
    project: str,
    roles: Iterable[TaskType | str],
    *,
    run_model: RoleEntry | None = None,
    project_root: Path | None = None,
) -> ModelRouter:
    """The command's router with every role it uses checked; stops the command if one is unset.

    `run_model` (`--model`) gives every role of this run but `scenario` that one model. `project_root` is the
    project the command works on; its own settings file decides, not the active project's.
    """
    if project_root is not None:
        files = _core.load_llm_settings_at(project_root)
    else:
        files = _core.load_active_llm_settings(project)
    try:
        return build_router(
            files,
            project=project,
            roles=roles,
            ask=_core.spend_asker(),
            run_model=run_model,
            db=_core.get_db(),
        )
    except SettingsFileError as err:
        _core.refuse_llm_settings(err)


def optional_command_router(project: str, roles: Iterable[TaskType | str]) -> ModelRouter | None:
    """Like `command_router`, but a model nobody set up means no router instead of a refusal.

    For commands whose model use is optional. A setting that is set but wrong still stops the
    command.
    """
    files = _core.load_active_llm_settings(project)
    try:
        return build_router(
            files,
            project=project,
            roles=roles,
            ask=_core.spend_asker(),
            db=_core.get_db(),
        )
    except SettingNotSetError as err:
        _core.console.print(f"No model used: {err.key}: {err.message}", style="dim", markup=False)
        return None
    except SettingsFileError as err:
        _core.refuse_llm_settings(err)
