# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The one way an API endpoint gets its models: the router, from the project's settings files."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.core.config.bootstrap.llm_settings_loader import load_llm_settings
from specweaver.core.config.llm_settings import SettingsFileError
from specweaver.infrastructure.llm.router import build_router
from specweaver.interfaces.api.errors import SpecWeaverAPIError

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from specweaver.core.config.settings import SpecWeaverSettings
    from specweaver.infrastructure.llm.models import TaskType
    from specweaver.infrastructure.llm.router import ModelRouter


def api_router(
    project_root: Path, project: str, settings: SpecWeaverSettings, roles: Iterable[TaskType]
) -> ModelRouter:
    """The endpoint's router with every role it uses checked, or a 500 naming the settings error."""
    try:
        return build_router(
            load_llm_settings(project_root),
            project=project,
            roles=roles,
            spend_limit_usd=settings.llm.max_spend_usd,
            token_limit=settings.llm.max_tokens_per_run,
        )
    except SettingsFileError as exc:
        raise SpecWeaverAPIError(
            detail=str(exc), error_code="LLM_SETTINGS", status_code=500
        ) from exc
