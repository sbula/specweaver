# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Filesystem tool models — access controls, grants, and result types.

Extracted from tool.py to keep it under the 500-line limit.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class AccessMode(StrEnum):
    """Access level for a folder grant."""

    READ = "read"  # list, read, search
    WRITE = "write"  # read + write + edit
    FULL = "full"  # read + write + edit + create + delete


# Permission hierarchy: which modes allow which operations
MODE_ALLOWS_READ: frozenset[AccessMode] = frozenset({AccessMode.READ, AccessMode.WRITE, AccessMode.FULL})  # fmt: skip
MODE_ALLOWS_WRITE: frozenset[AccessMode] = frozenset({AccessMode.WRITE, AccessMode.FULL})  # fmt: skip
MODE_ALLOWS_CREATE: frozenset[AccessMode] = frozenset({AccessMode.FULL})  # fmt: skip
MODE_ALLOWS_DELETE: frozenset[AccessMode] = frozenset({AccessMode.FULL})  # fmt: skip


@dataclass(frozen=True)
class FolderGrant:
    """A single folder access grant.

    Args:
        path: Relative path from project root (e.g., "src/domain/billing").
        mode: Access level (READ, WRITE, or FULL).
        recursive: If True, grant covers all subdirectories.
    """

    path: str
    mode: AccessMode
    recursive: bool


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
}


@dataclass(frozen=True)
class ToolResult:
    """Result from a FileSystemTool intent execution."""

    status: str  # "success" or "error"
    message: str = ""
    data: Any = None


class FileSystemToolError(Exception):
    """Raised when a FileSystemTool operation is blocked by role or configuration."""
