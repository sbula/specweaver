# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The one way a CLI command gets its models: the router, from the active project's settings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.core.config.llm_settings import SettingsFileError
from specweaver.infrastructure.llm.router import build_router
from specweaver.interfaces.cli import _core

if TYPE_CHECKING:
    from collections.abc import Iterable

    from specweaver.core.config.settings import SpecWeaverSettings
    from specweaver.infrastructure.llm.models import TaskType
    from specweaver.infrastructure.llm.router import ModelRouter


def command_router(
    project: str, settings: SpecWeaverSettings, roles: Iterable[TaskType | str]
) -> ModelRouter:
    """The command's router with every role it uses checked; stops the command if one is unset."""
    files = _core.load_active_llm_settings(project)
    try:
        return build_router(
            files,
            project=project,
            roles=roles,
            spend_limit_usd=settings.llm.max_spend_usd,
            token_limit=settings.llm.max_tokens_per_run,
        )
    except SettingsFileError as err:
        _core.refuse_llm_settings(err)


def optional_command_router(
    project: str, settings: SpecWeaverSettings, roles: Iterable[TaskType | str]
) -> ModelRouter | None:
    """Like `command_router`, but a role nobody set means no router instead of a refusal.

    For commands whose model use is optional. A broken settings file still stops the command.
    """
    files = _core.load_active_llm_settings(project)
    try:
        return build_router(
            files,
            project=project,
            roles=roles,
            spend_limit_usd=settings.llm.max_spend_usd,
            token_limit=settings.llm.max_tokens_per_run,
        )
    except SettingsFileError as err:
        _core.console.print(f"No model used: {err.message}", style="dim", markup=False)
        return None
