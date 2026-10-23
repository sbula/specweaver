# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""How many runs the API takes at once; an unset or broken setting refuses the run."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.core.config.bootstrap.llm_settings_loader import load_llm_settings
from specweaver.core.config.settings_file import SettingsFileError
from specweaver.interfaces.api.errors import SpecWeaverAPIError

if TYPE_CHECKING:
    from pathlib import Path


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
