# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reads a project's `[implement]` section from its `specweaver.toml`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.core.config.bootstrap.llm_settings_loader import (
    PROJECT_FILE_NAME,
    read_settings_text,
)
from specweaver.core.config.implement_policy import ImplementPolicy, parse_implement

if TYPE_CHECKING:
    from pathlib import Path


def load_implement(project_root: Path) -> ImplementPolicy:
    """The project's `[implement]`; nothing named when the file or the section is absent."""
    path = project_root / PROJECT_FILE_NAME
    return parse_implement(read_settings_text(path), str(path))
