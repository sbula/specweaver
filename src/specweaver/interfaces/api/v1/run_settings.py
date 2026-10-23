# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The project settings an API run is built from; a broken or missing one refuses the run."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.core.config.autonomy_policy import parse_autonomy
from specweaver.core.config.bootstrap.llm_settings_loader import load_llm_settings
from specweaver.core.config.bootstrap.project_settings import load_section
from specweaver.core.config.bootstrap.settings_loader import load_settings_async
from specweaver.core.config.doc_policy import parse_doc_policy
from specweaver.core.config.implement_policy import parse_implement
from specweaver.core.config.settings_file import SettingsFileError
from specweaver.core.flow.handlers.run_context import IsolationPolicy
from specweaver.interfaces.api.errors import SpecWeaverAPIError

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.config.database import Database
    from specweaver.core.config.settings import SpecWeaverSettings

logger = logging.getLogger(__name__)


def max_runs(project_root: Path) -> int:
    """`[serve] max_runs`, the runs the API takes at once; a run is refused while it is unset."""

    try:
        limit = load_llm_settings(project_root).machine.serve.max_runs
    except SettingsFileError as exc:
        raise SpecWeaverAPIError(
            detail=str(exc), error_code="LLM_SETTINGS", status_code=500
        ) from exc
    if limit is None:
        raise SpecWeaverAPIError(
            detail="serve.max_runs is not set in settings.toml — how many runs the API takes at "
            "once; there is no default",
            error_code="SETTING_NOT_SET",
            status_code=409,
        )
    return limit


def project_policy(project_root: Path) -> IsolationPolicy:
    """A run's isolation policy holding the project's `[docs]` and `[autonomy]`; a broken one refuses."""

    try:
        doc_policy = load_section(project_root, parse_doc_policy)
    except SettingsFileError as exc:
        raise SpecWeaverAPIError(detail=str(exc), error_code="DOC_POLICY", status_code=500) from exc
    try:
        autonomy = load_section(project_root, parse_autonomy)
    except SettingsFileError as exc:
        raise SpecWeaverAPIError(
            detail=str(exc), error_code="AUTONOMY_POLICY", status_code=500
        ) from exc
    try:
        language = load_section(project_root, parse_implement).language
    except SettingsFileError as exc:
        raise SpecWeaverAPIError(
            detail=str(exc), error_code="IMPLEMENT_POLICY", status_code=500
        ) from exc
    return IsolationPolicy(doc_policy=doc_policy, autonomy=autonomy, language=language)


async def isolation_settings(db: Database, project: str) -> SpecWeaverSettings | None:
    """The settings a run's isolation is built from; a broken file refuses with 500 naming it.

    Any other lookup failure is best-effort: None, and isolation keeps its defaults.
    """
    try:
        return await load_settings_async(db, project)
    except SettingsFileError as exc:
        raise SpecWeaverAPIError(
            detail=str(exc), error_code=_settings_code(exc), status_code=500
        ) from exc
    except Exception:  # best-effort by contract for anything but a broken settings file
        logger.debug("Could not resolve settings for '%s'; isolation defaults to off.", project)
        return None


def _settings_code(exc: SettingsFileError) -> str:
    """Which setting stopped the run: the DAL file, `[standards]`, else `[sandbox]`."""
    if exc.source.endswith("dal_definitions.yaml"):
        return "DAL_DEFINITIONS"
    if exc.key.split(".")[0] == "standards":
        return "STANDARDS_SETTINGS"
    return "SANDBOX_SETTINGS"
