# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The project settings an API run is built from; a broken or missing one refuses the run."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.core.config.bootstrap.autonomy_loader import load_autonomy
from specweaver.core.config.bootstrap.doc_policy_loader import load_doc_policy
from specweaver.core.config.bootstrap.implement_loader import load_implement
from specweaver.core.config.bootstrap.llm_settings_loader import load_llm_settings
from specweaver.core.config.llm_settings import SettingsFileError
from specweaver.core.flow.handlers.run_context import IsolationPolicy
from specweaver.interfaces.api.errors import SpecWeaverAPIError

if TYPE_CHECKING:
    from pathlib import Path


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
        doc_policy = load_doc_policy(project_root)
    except SettingsFileError as exc:
        raise SpecWeaverAPIError(detail=str(exc), error_code="DOC_POLICY", status_code=500) from exc
    try:
        autonomy = load_autonomy(project_root)
    except SettingsFileError as exc:
        raise SpecWeaverAPIError(
            detail=str(exc), error_code="AUTONOMY_POLICY", status_code=500
        ) from exc
    try:
        language = load_implement(project_root).language
    except SettingsFileError as exc:
        raise SpecWeaverAPIError(
            detail=str(exc), error_code="IMPLEMENT_POLICY", status_code=500
        ) from exc
    return IsolationPolicy(doc_policy=doc_policy, autonomy=autonomy, language=language)
