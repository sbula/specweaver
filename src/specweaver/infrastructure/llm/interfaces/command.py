# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The one way a CLI command gets its models: the router, from its target project's settings."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import click
import typer
from pydantic import ValidationError
from rich.console import Console

from specweaver.core.config.llm_settings import RoleEntry, SettingNotSetError, SettingsFileError
from specweaver.infrastructure.llm.router import build_router
from specweaver.interfaces.cli import _core

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from specweaver.infrastructure.llm.models import TaskType
    from specweaver.infrastructure.llm.router import ModelRouter

logger = logging.getLogger(__name__)


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


def _tell_missing_at_end(router: ModelRouter) -> ModelRouter:
    """At the command's end, also after an exit, say on stderr how many calls the ledger misses."""
    context = click.get_current_context(silent=True)
    if context is not None:
        context.call_on_close(lambda: _tell_missing(router))
    return router


def _tell_missing(router: ModelRouter) -> None:
    try:
        missing = router.unwritten()
    except Exception:
        logger.warning("Could not count the calls missing from the cost ledger")
        return
    if missing:
        calls = (
            "1 call of this command is" if missing == 1 else f"{missing} calls of this command are"
        )
        was = "was" if missing == 1 else "were"
        Console(stderr=True).print(
            f"{calls} missing from the cost ledger or {was} not closed in it; "
            "sw usage and sw costs do not show their full spend.",
            style="yellow",
            markup=False,
            highlight=False,
        )


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
        return _tell_missing_at_end(
            build_router(
                files,
                project=project,
                roles=roles,
                ask=_core.spend_asker(),
                run_model=run_model,
                db=_core.get_db(),
            )
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
        return _tell_missing_at_end(
            build_router(
                files,
                project=project,
                roles=roles,
                ask=_core.spend_asker(),
                db=_core.get_db(),
            )
        )
    except SettingNotSetError as err:
        _core.console.print(f"No model used: {err.key}: {err.message}", style="dim", markup=False)
        return None
    except SettingsFileError as err:
        _core.refuse_llm_settings(err)
