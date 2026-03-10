# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""FileSystemTool — intent-based filesystem operations with boundary enforcement.

Mirrors the GitTool pattern: role-based intent gating + security enforcement.
Each intent method checks:
1. Role allows this intent (or raise FileSystemToolError)
2. Path is within a granted boundary (or return error result)
3. Grant mode permits the operation (READ vs WRITE vs FULL)
4. Protected patterns still enforced (context.yaml, .env, etc.)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from specweaver.loom.commons.filesystem.executor import ExecutorResult, FileExecutor


# ---------------------------------------------------------------------------
# Access models
# ---------------------------------------------------------------------------


class AccessMode(StrEnum):
    """Access level for a folder grant."""

    READ = "read"    # list, read, search
    WRITE = "write"  # read + write + edit
    FULL = "full"    # read + write + edit + create + delete


# Permission hierarchy: which modes allow which operations
_MODE_ALLOWS_READ: frozenset[AccessMode] = frozenset({
    AccessMode.READ, AccessMode.WRITE, AccessMode.FULL,
})
_MODE_ALLOWS_WRITE: frozenset[AccessMode] = frozenset({
    AccessMode.WRITE, AccessMode.FULL,
})
_MODE_ALLOWS_CREATE: frozenset[AccessMode] = frozenset({
    AccessMode.FULL,
})
_MODE_ALLOWS_DELETE: frozenset[AccessMode] = frozenset({
    AccessMode.FULL,
})


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


# ---------------------------------------------------------------------------
# Role → allowed intents
# ---------------------------------------------------------------------------


ROLE_INTENTS: dict[str, frozenset[str]] = {
    "implementer": frozenset({
        "read_file",
        "write_file",
        "edit_file",
        "create_file",
        "delete_file",
        "list_directory",
        "search_content",
        "find_placement",
    }),
    "reviewer": frozenset({
        "read_file",
        "list_directory",
        "search_content",
    }),
    "drafter": frozenset({
        "read_file",
        "write_file",
        "create_file",
        "delete_file",
        "list_directory",
        "search_content",
        "find_placement",
    }),
}


# ---------------------------------------------------------------------------
# Tool result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolResult:
    """Result from a FileSystemTool intent execution."""

    status: str  # "success" or "error"
    message: str = ""
    data: Any = None


# ---------------------------------------------------------------------------
# FileSystemTool
# ---------------------------------------------------------------------------


class FileSystemToolError(Exception):
    """Raised when a FileSystemTool operation is blocked by role or configuration."""


class FileSystemTool:
    """Intent-based filesystem operations with boundary enforcement.

    Args:
        executor: The FileExecutor instance (configured with cwd).
        role: The agent's role (determines which intents are allowed).
        grants: List of FolderGrants defining the agent's access boundaries.
    """

    def __init__(
        self,
        executor: FileExecutor,
        role: str,
        grants: list[FolderGrant],
    ) -> None:
        if role not in ROLE_INTENTS:
            msg = f"Unknown role: {role!r}. Known roles: {sorted(ROLE_INTENTS)}"
            raise ValueError(msg)
        self._executor = executor
        self._role = role
        self._grants = list(grants)

    @property
    def role(self) -> str:
        """The agent's role."""
        return self._role

    @property
    def allowed_intents(self) -> frozenset[str]:
        """Intents available for this role."""
        return ROLE_INTENTS[self._role]

    # -------------------------------------------------------------------
    # Intent methods
    # -------------------------------------------------------------------

    def read_file(self, path: str) -> ToolResult:
        """Read a file's contents."""
        self._require_intent("read_file")
        err = self._check_grant(path, _MODE_ALLOWS_READ)
        if err:
            return err
        result = self._executor.read(path)
        return self._wrap(result)

    def write_file(self, path: str, content: str) -> ToolResult:
        """Overwrite a file's contents."""
        self._require_intent("write_file")
        err = self._check_grant(path, _MODE_ALLOWS_WRITE)
        if err:
            return err
        result = self._executor.write(path, content)
        return self._wrap(result)

    def create_file(self, path: str, content: str) -> ToolResult:
        """Create a new file (fails if exists)."""
        self._require_intent("create_file")
        err = self._check_grant(path, _MODE_ALLOWS_CREATE)
        if err:
            return err
        # Check existence first
        exists_result = self._executor.exists(path)
        if exists_result.status == "success" and exists_result.data is True:
            return ToolResult(status="error", message=f"File already exists: {path}")
        result = self._executor.write(path, content)
        return self._wrap(result)

    def delete_file(self, path: str) -> ToolResult:
        """Delete a file."""
        self._require_intent("delete_file")
        err = self._check_grant(path, _MODE_ALLOWS_DELETE)
        if err:
            return err
        result = self._executor.delete(path)
        return self._wrap(result)

    def edit_file(self, path: str, *, old: str, new: str) -> ToolResult:
        """Patch-based edit: replace old content with new.

        Args:
            path: Relative path to file.
            old: Exact string to find.
            new: Replacement string.
        """
        self._require_intent("edit_file")
        err = self._check_grant(path, _MODE_ALLOWS_WRITE)
        if err:
            return err

        # Read current content
        read_result = self._executor.read(path)
        if read_result.status != "success":
            return ToolResult(status="error", message=read_result.error)

        content = read_result.data
        if old not in content:
            return ToolResult(
                status="error",
                message=f"Target content not found in {path}",
            )

        patched = content.replace(old, new, 1)
        write_result = self._executor.write(path, patched)
        return self._wrap(write_result)

    def list_directory(self, path: str) -> ToolResult:
        """List directory contents."""
        self._require_intent("list_directory")
        err = self._check_grant(path, _MODE_ALLOWS_READ)
        if err:
            return err
        result = self._executor.list_dir(path)
        return self._wrap(result)

    def search_content(self, path: str, regex: str) -> ToolResult:
        """Search for a regex pattern across files in a directory.

        Args:
            path: Directory to search in.
            regex: Regex pattern to match against each line.

        Returns:
            ToolResult with data=list of {file, line, content} matches.
        """
        self._require_intent("search_content")
        err = self._check_grant(path, _MODE_ALLOWS_READ)
        if err:
            return err

        try:
            pattern = re.compile(regex, re.MULTILINE)
        except re.error as exc:
            return ToolResult(status="error", message=f"Invalid regex: {exc}")

        # List files in directory
        list_result = self._executor.list_dir(path)
        if list_result.status != "success":
            return ToolResult(status="error", message=list_result.error)

        matches: list[dict[str, Any]] = []
        for name in list_result.data:
            file_path = f"{path}/{name}" if path else name
            read_result = self._executor.read(file_path)
            if read_result.status != "success":
                continue  # skip directories, binary files, etc.
            for i, line in enumerate(read_result.data.splitlines(), 1):
                if pattern.search(line):
                    matches.append({"file": name, "line": i, "content": line.strip()})

        return ToolResult(status="success", data=matches)

    def find_placement(self, description: str) -> ToolResult:
        """Semantic search over context.yaml purpose fields.

        MVP: Simple keyword matching on purpose fields.

        Args:
            description: What the new code does.

        Returns:
            ToolResult with data=list of matching boundaries.
        """
        self._require_intent("find_placement")
        # Placeholder — will be implemented in Phase 4
        return ToolResult(
            status="success",
            message="find_placement not yet implemented (Phase 4)",
            data=[],
        )

    # -------------------------------------------------------------------
    # Internal: role gating
    # -------------------------------------------------------------------

    def _require_intent(self, intent: str) -> None:
        """Raise if the current role doesn't have this intent."""
        if intent not in ROLE_INTENTS[self._role]:
            msg = (
                f"Intent {intent!r} is not allowed for role {self._role!r}. "
                f"Allowed: {sorted(ROLE_INTENTS[self._role])}"
            )
            raise FileSystemToolError(msg)

    # -------------------------------------------------------------------
    # Internal: boundary enforcement
    # -------------------------------------------------------------------

    def _check_grant(
        self,
        path: str,
        required_modes: frozenset[AccessMode],
    ) -> ToolResult | None:
        """Check if any grant allows the operation on this path.

        Returns None if allowed, or an error ToolResult if blocked.
        """
        normalized = path.replace("\\", "/")

        best_mode = self._resolve_mode(normalized)

        if best_mode is None:
            return ToolResult(
                status="error",
                message=f"No grant covers path: {path}",
            )

        if best_mode not in required_modes:
            return ToolResult(
                status="error",
                message=f"Insufficient permissions ({best_mode}) for path: {path}",
            )

        return None

    def _resolve_mode(self, normalized_path: str) -> AccessMode | None:
        """Find the most permissive mode that covers this path.

        Returns None if no grant covers the path.
        """
        # Mode priority for "most permissive"
        mode_priority = {AccessMode.READ: 0, AccessMode.WRITE: 1, AccessMode.FULL: 2}
        best: AccessMode | None = None

        for grant in self._grants:
            grant_path = grant.path.replace("\\", "/").rstrip("/")

            if self._path_matches_grant(normalized_path, grant_path, grant.recursive):
                if best is None or mode_priority[grant.mode] > mode_priority[best]:
                    best = grant.mode

        return best

    def _path_matches_grant(
        self,
        target: str,
        grant_path: str,
        recursive: bool,
    ) -> bool:
        """Check if target path falls under a grant.

        For a file path like "src/domain/billing/calc.py":
        - Grant "src/domain/billing" (recursive=True) → matches
        - Grant "src/domain/billing" (recursive=False) → matches (direct child)
        - Grant "src/domain" (recursive=True) → matches
        - Grant "src/domain" (recursive=False) → does NOT match (calc.py is in billing/)
        """
        target_parts = target.replace("\\", "/").split("/")
        grant_parts = grant_path.split("/")

        # Target must start with grant path
        if len(target_parts) < len(grant_parts):
            return False

        # Check the grant path is a prefix
        for i, part in enumerate(grant_parts):
            if i >= len(target_parts) or target_parts[i] != part:
                return False

        if recursive:
            # Recursive: all descendants match
            return True

        # Exclusive: only direct children (one level deeper = direct child of grant dir)
        depth = len(target_parts) - len(grant_parts)
        if depth == 0:
            # Target IS the grant directory itself — match for list operations
            return True
        return depth == 1

    # -------------------------------------------------------------------
    # Internal: result wrapping
    # -------------------------------------------------------------------

    @staticmethod
    def _wrap(result: ExecutorResult) -> ToolResult:
        """Convert an ExecutorResult to a ToolResult."""
        if result.status == "success":
            return ToolResult(status="success", data=result.data)
        return ToolResult(status="error", message=result.error)
