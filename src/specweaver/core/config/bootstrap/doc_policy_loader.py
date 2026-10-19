# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reads a project's doc policy from its `specweaver.toml`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.core.config.bootstrap.llm_settings_loader import (
    PROJECT_FILE_NAME,
    read_settings_text,
)
from specweaver.core.config.doc_policy import DocPolicy, parse_doc_policy

if TYPE_CHECKING:
    from pathlib import Path


def load_doc_policy(project_root: Path) -> DocPolicy:
    """The project's `[docs]` rules; an empty policy when the file or the section is absent."""
    path = project_root / PROJECT_FILE_NAME
    return parse_doc_policy(read_settings_text(path), str(path))
