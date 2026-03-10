# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""MCP-like role interfaces for filesystem operations.

Each interface class exposes ONLY the intents allowed for its role.
The LLM agent receives one of these — it physically cannot call
methods that don't exist on its interface.

The grants come from the Engine (derived from context.yaml boundaries).

Usage:
    interface = create_filesystem_interface("implementer", project_path, grants)
    result = interface.read_file("src/main.py")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.loom.commons.filesystem.executor import FileExecutor
from specweaver.loom.tools.filesystem.tool import (
    FileSystemTool,
    FolderGrant,
    ToolResult,
)

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Role-specific interfaces
# ---------------------------------------------------------------------------


class ImplementerFileInterface:
    """Filesystem interface for the Implementer role.

    Allowed intents: read_file, write_file, edit_file, create_file,
                     delete_file, list_directory, search_content, find_placement.
    """

    def __init__(self, tool: FileSystemTool) -> None:
        self._tool = tool

    def read_file(self, path: str) -> ToolResult:
        """Read a file's contents."""
        return self._tool.read_file(path)

    def write_file(self, path: str, content: str) -> ToolResult:
        """Overwrite a file's contents."""
        return self._tool.write_file(path, content)

    def edit_file(self, path: str, *, old: str, new: str) -> ToolResult:
        """Patch-based edit: replace old content with new."""
        return self._tool.edit_file(path, old=old, new=new)

    def create_file(self, path: str, content: str) -> ToolResult:
        """Create a new file (fails if exists)."""
        return self._tool.create_file(path, content)

    def delete_file(self, path: str) -> ToolResult:
        """Delete a file."""
        return self._tool.delete_file(path)

    def list_directory(self, path: str) -> ToolResult:
        """List directory contents."""
        return self._tool.list_directory(path)

    def search_content(self, path: str, regex: str) -> ToolResult:
        """Search for regex pattern in files."""
        return self._tool.search_content(path, regex)

    def find_placement(self, description: str) -> ToolResult:
        """Find where new code should go based on context.yaml purposes."""
        return self._tool.find_placement(description)


class ReviewerFileInterface:
    """Filesystem interface for the Reviewer role.

    Allowed intents: read_file, list_directory, search_content.
    All read-only.
    """

    def __init__(self, tool: FileSystemTool) -> None:
        self._tool = tool

    def read_file(self, path: str) -> ToolResult:
        """Read a file's contents."""
        return self._tool.read_file(path)

    def list_directory(self, path: str) -> ToolResult:
        """List directory contents."""
        return self._tool.list_directory(path)

    def search_content(self, path: str, regex: str) -> ToolResult:
        """Search for regex pattern in files."""
        return self._tool.search_content(path, regex)


class DrafterFileInterface:
    """Filesystem interface for the Drafter role.

    Allowed intents: read_file, write_file, create_file, delete_file,
                     list_directory, search_content, find_placement.
    """

    def __init__(self, tool: FileSystemTool) -> None:
        self._tool = tool

    def read_file(self, path: str) -> ToolResult:
        """Read a file's contents."""
        return self._tool.read_file(path)

    def write_file(self, path: str, content: str) -> ToolResult:
        """Overwrite a file's contents."""
        return self._tool.write_file(path, content)

    def create_file(self, path: str, content: str) -> ToolResult:
        """Create a new file (fails if exists)."""
        return self._tool.create_file(path, content)

    def delete_file(self, path: str) -> ToolResult:
        """Delete a file."""
        return self._tool.delete_file(path)

    def list_directory(self, path: str) -> ToolResult:
        """List directory contents."""
        return self._tool.list_directory(path)

    def search_content(self, path: str, regex: str) -> ToolResult:
        """Search for regex pattern in files."""
        return self._tool.search_content(path, regex)

    def find_placement(self, description: str) -> ToolResult:
        """Find where new code should go based on context.yaml purposes."""
        return self._tool.find_placement(description)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_ROLE_INTERFACE_MAP = {
    "implementer": ImplementerFileInterface,
    "reviewer": ReviewerFileInterface,
    "drafter": DrafterFileInterface,
}

FileInterface = (
    ImplementerFileInterface
    | ReviewerFileInterface
    | DrafterFileInterface
)


def create_filesystem_interface(
    role: str,
    cwd: Path,
    grants: list[FolderGrant],
) -> FileInterface:
    """Create a role-specific filesystem interface.

    The cwd and grants are set by the Engine — the agent cannot change them.

    Args:
        role: The agent's role ("implementer", "reviewer", "drafter").
        cwd: The target project's working directory (from config, not agent).
        grants: List of FolderGrants defining accessibility boundaries.

    Returns:
        A role-specific interface with only the allowed methods.

    Raises:
        ValueError: If the role is unknown.
    """
    if role not in _ROLE_INTERFACE_MAP:
        msg = f"Unknown role: {role!r}. Known roles: {sorted(_ROLE_INTERFACE_MAP)}"
        raise ValueError(msg)

    executor = FileExecutor(cwd=cwd)
    tool = FileSystemTool(executor=executor, role=role, grants=grants)

    interface_cls = _ROLE_INTERFACE_MAP[role]
    return interface_cls(tool)
