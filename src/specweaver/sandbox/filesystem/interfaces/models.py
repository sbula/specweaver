# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Filesystem tool models — access controls, grants, and result types.

Extracted from tool.py to keep it under the 500-line limit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

# `AccessMode`, `FolderGrant` and the `MODE_ALLOWS_*` sets are re-exported, NOT redefined.
#
# Declaring them here as well would make them two distinct classes -- `isinstance` across them
# false, and `AccessMode.READ == AccessMode.READ` true only because `StrEnum` compares by value.
# Code holding one copy and code holding the other would interoperate by duck typing alone.
#
# The security consequence is recorded on `FolderGrant.__post_init__`: a guard added to one copy
# leaves the hole open through the other. One definition, one guard.
from specweaver.sandbox.security import (
    MODE_ALLOWS_CREATE,
    MODE_ALLOWS_DELETE,
    MODE_ALLOWS_READ,
    MODE_ALLOWS_WRITE,
    AccessMode,
    FolderGrant,
)

#: Re-exported names, declared so the intent is explicit rather than suppressed.
__all__ = [
    "MODE_ALLOWS_CREATE",
    "MODE_ALLOWS_DELETE",
    "MODE_ALLOWS_READ",
    "MODE_ALLOWS_WRITE",
    "ROLE_INTENTS",
    "AccessMode",
    "FileSystemToolError",
    "FolderGrant",
    "ToolResult",
]

logger = logging.getLogger(__name__)


# Role → allowed intents

#: Agents read files; they change code through the code-structure tools, and the engine writes
#: whole files [agreed 2026-10-13].
_READ = frozenset({"read_file", "list_directory", "grep", "find_files"})

ROLE_INTENTS: dict[str, frozenset[str]] = {
    role: _READ
    for role in ("implementer", "reviewer", "planner", "scenario_agent", "drafter", "arbiter_agent")
}


@dataclass(frozen=True)
class ToolResult:
    """Result from a FileSystemTool intent execution."""

    status: str  # "success" or "error"
    message: str = ""
    data: Any = None


class FileSystemToolError(Exception):
    """Raised when a FileSystemTool operation is blocked by role or configuration."""
