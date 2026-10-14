# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The filesystem interface a model gets: read, list and search, and nothing that writes.

A model physically cannot call a method the interface does not have.

The grants come from the Engine (derived from context.yaml boundaries).

Usage:
    interface = create_filesystem_interface("implementer", project_path, grants)
    result = interface.read_file("src/main.py")
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.sandbox.base import BaseTool
from specweaver.sandbox.filesystem.core.executor import FileExecutor
from specweaver.sandbox.filesystem.interfaces.tool import FileSystemTool

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.infrastructure.llm.models import ToolDefinition
    from specweaver.sandbox.filesystem.interfaces.models import ToolResult
    from specweaver.sandbox.security import FolderGrant


class FileReadInterface(BaseTool):
    """What a model may do with files: read, list, search. Every role gets this one."""

    def __init__(self, tool: FileSystemTool) -> None:
        self._tool = tool

    @property
    def role(self) -> str:
        return self._tool.role

    def definitions(self) -> list[ToolDefinition]:
        return self._tool.definitions()

    def read_file(
        self, path: str, start_line: int | None = None, end_line: int | None = None
    ) -> ToolResult:
        """Read a file, or lines `start_line` to `end_line` of it."""
        return self._tool.read_file(path, start_line, end_line)

    def list_directory(self, path: str = ".", depth: int = 2, max_entries: int = 50) -> ToolResult:
        """The tree under `path`, `depth` levels deep, at most `max_entries` entries."""
        return self._tool.list_directory(path, depth, max_entries)

    def grep(self, pattern: str, path: str = ".", **kwargs: object) -> ToolResult:
        """Search for a pattern in file contents."""
        return self._tool.grep(path, pattern, **kwargs)  # type: ignore[arg-type]

    def find_files(
        self, pattern: str, path: str = ".", type: str = "any", **kwargs: object
    ) -> ToolResult:
        """Find files matching a glob pattern; `type` is the definition's name for `file_type`."""
        return self._tool.find_files(path, pattern, file_type=type, **kwargs)  # type: ignore[arg-type]


def create_filesystem_interface(
    role: str,
    cwd: Path,
    grants: list[FolderGrant],
    exclude_dirs: set[str] | None = None,
    exclude_patterns: set[str] | None = None,
) -> FileReadInterface:
    """Create a role's filesystem interface: the same read tools for every role.

    The cwd and grants are set by the Engine — the agent cannot change them.

    Args:
        role: The agent's role ("implementer", "reviewer", "drafter").
        cwd: The target project's working directory (from config, not agent).
        grants: List of FolderGrants defining accessibility boundaries.
        exclude_dirs: Optional set of directory names to prune from deep scans.
        exclude_patterns: Optional set of glob patterns to exclude.

    Returns:
        The read interface, over the role's grants.

    Raises:
        ValueError: If the role is unknown.
    """
    executor = FileExecutor(cwd=cwd)
    tool = FileSystemTool(
        executor=executor,
        role=role,
        grants=grants,
        exclude_dirs=exclude_dirs,
        exclude_patterns=exclude_patterns,
    )

    return FileReadInterface(tool)
