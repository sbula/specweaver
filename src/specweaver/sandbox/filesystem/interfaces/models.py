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
# `TECH-037`: they used to be declared here as well, which made them two distinct classes --
# `isinstance` across them was False, and `AccessMode.READ == AccessMode.READ` held only because
# `StrEnum` compares by value. Production imported the `sandbox.security` copy while several tests
# built grants from this one and handed them over, which worked by duck typing alone.
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

ROLE_INTENTS: dict[str, frozenset[str]] = {
    "implementer": frozenset(
        {
            "read_file",
            "write_file",
            "edit_file",
            "create_file",
            "delete_file",
            "list_directory",
            "search_content",
            "find_placement",
            "grep",
            "find_files",
        }
    ),
    "reviewer": frozenset({"read_file", "list_directory", "search_content", "grep", "find_files"}),
    "planner": frozenset({"read_file", "list_directory", "search_content", "grep", "find_files"}),
    "scenario_agent": frozenset(
        {
            "read_file",
            "write_file",
            "create_file",
            "delete_file",
            "list_directory",
            "search_content",
            "find_placement",
            "grep",
            "find_files",
        }
    ),
    "drafter": frozenset(
        {
            "read_file",
            "write_file",
            "create_file",
            "delete_file",
            "list_directory",
            "search_content",
            "find_placement",
            "grep",
            "find_files",
        }
    ),
    "arbiter_agent": frozenset(
        {
            "read_file",
            "list_directory",
            "search_content",
            "grep",
            "find_files",
        }
    ),
}


@dataclass(frozen=True)
class ToolResult:
    """Result from a FileSystemTool intent execution."""

    status: str  # "success" or "error"
    message: str = ""
    data: Any = None


class FileSystemToolError(Exception):
    """Raised when a FileSystemTool operation is blocked by role or configuration."""
