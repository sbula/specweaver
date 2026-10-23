# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reads a project's `specweaver.toml`: any section, through that section's own parser."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

PROJECT_FILE_NAME = "specweaver.toml"

_T = TypeVar("_T")


def read_settings_text(path: Path | None) -> str:
    """A settings file's text; empty when it is missing."""
    if path is None or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8-sig")


def load_section(project_root: Path, parse: Callable[[str, str], _T]) -> _T:
    """`parse` applied to the project's settings text; a missing file is parsed as empty text."""
    path = project_root / PROJECT_FILE_NAME
    return parse(read_settings_text(path), str(path))
