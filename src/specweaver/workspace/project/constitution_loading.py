# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Finding a project's CONSTITUTION.md and reading it safely.

Split out of `_helpers.py` by `TECH-015`. The size ceiling and the filename are part of this
contract — a constitution is read into an LLM prompt, so "how big may it be" belongs beside "how do
we load it" rather than in a file named for being a leftover.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

CONSTITUTION_FILENAME = "CONSTITUTION.md"
DEFAULT_MAX_CONSTITUTION_SIZE = 5120  # 5 KB


@dataclass(frozen=True)
class ConstitutionInfo:
    """Result of loading a constitution.

    Attributes:
        content: Raw markdown content (BOM-stripped).
        path: Absolute path to the file.
        size: File size in bytes.
        is_override: True if this is not the root-level constitution
            (i.e. found in a subdirectory, overriding the root).
    """

    content: str
    path: Path
    size: int
    is_override: bool


def load_constitution(
    path: Path,
    *,
    is_override: bool,
    max_size: int = DEFAULT_MAX_CONSTITUTION_SIZE,
) -> ConstitutionInfo:
    """Load a constitution file with BOM stripping and size warning."""
    raw = path.read_text(encoding="utf-8-sig")  # auto-strips BOM

    # Strip BOM if present
    if raw.startswith("\ufeff"):
        raw = raw[1:]

    size = path.stat().st_size

    if size > max_size:
        logger.warning(
            "Constitution %s size (%d bytes) exceeds recommended limit "
            "(%d bytes). Consider trimming.",
            path,
            size,
            max_size,
        )

    return ConstitutionInfo(
        content=raw,
        path=path,
        size=size,
        is_override=is_override,
    )
