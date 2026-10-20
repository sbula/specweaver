# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reads a project's autonomy policy from its `specweaver.toml`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.core.config.autonomy_policy import AutonomyPolicy, parse_autonomy
from specweaver.core.config.bootstrap.llm_settings_loader import (
    PROJECT_FILE_NAME,
    read_settings_text,
)

if TYPE_CHECKING:
    from pathlib import Path


def load_autonomy(project_root: Path) -> AutonomyPolicy:
    """The project's `[autonomy]`; the empty policy when the file or the section is absent."""
    path = project_root / PROJECT_FILE_NAME
    return parse_autonomy(read_settings_text(path), str(path))
