# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""FileSystemTool — intent-based filesystem operations with boundary enforcement.

Mirrors the GitTool pattern: role-based intent gating + security enforcement.
Each intent method checks:
1. Role allows this intent (or raise FileSystemToolError)
2. Path is within a granted boundary (or return error result)
3. Grant mode permits the operation (READ vs WRITE vs FULL)
4. Protected patterns still enforced (context.yaml, .env, etc.)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.sandbox.base import BaseTool
from specweaver.sandbox.filesystem.interfaces.models import (
    ROLE_INTENTS,
    FileSystemToolError,
    ToolResult,
)
from specweaver.sandbox.security import (
    MODE_ALLOWS_CREATE,
    MODE_ALLOWS_DELETE,
    MODE_ALLOWS_READ,
    MODE_ALLOWS_WRITE,
    AccessMode,
    FolderGrant,
    grant_mode_for,
    normalize_grant_path,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.infrastructure.llm.models import ToolDefinition
    from specweaver.sandbox.filesystem.core.executor import ExecutorResult, FileExecutor


class FileSystemTool(BaseTool):
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
        exclude_dirs: set[str] | None = None,
        exclude_patterns: set[str] | None = None,
    ) -> None:
        if role not in ROLE_INTENTS:
            msg = f"Unknown role: {role!r}. Known roles: {sorted(ROLE_INTENTS)}"
            raise ValueError(msg)
        self._executor = executor
        self._role = role
        self._grants = list(grants)
        self._exclude_dirs = exclude_dirs or set()
        self._exclude_patterns = exclude_patterns or set()

    @property
    def role(self) -> str:
        """The agent's role."""
        return self._role

    @property
    def allowed_intents(self) -> frozenset[str]:
        """Intents available for this role."""
        return ROLE_INTENTS[self._role]

    def definitions(self) -> list[ToolDefinition]:
        from specweaver.sandbox.filesystem.interfaces.definitions import INTENT_DEFINITIONS

        return [d for name, d in INTENT_DEFINITIONS.items() if name in self.allowed_intents]

    # Intent methods

    def read_file(
        self, path: str, start_line: int | None = None, end_line: int | None = None
    ) -> ToolResult:
        """A file's contents, or only lines `start_line` to `end_line` (1-based, inclusive).

        A range reads a file of any size; the size limit applies to the lines returned.
        """
        self._require_intent("read_file")
        err = self._check_grant(path, MODE_ALLOWS_READ)
        if err:
            return err
        if start_line is None and end_line is None:
            return self._wrap(self._executor.read(path))
        start = 1 if start_line is None else start_line
        if start < 1 or (end_line is not None and end_line < start):
            return ToolResult(
                status="error", message=f"lines {start} to {end_line} are not a range"
            )
        read = self._executor.read_lines(path, start, end_line)
        if read.status != "success":
            return self._wrap(read)
        text, count = read.data
        if start > count:
            return ToolResult(
                status="error", message=f"{path} has {count} lines; line {start} does not exist"
            )
        return ToolResult(status="success", data=text)

    def write_file(self, path: str, content: str) -> ToolResult:
        """Overwrite a file's contents."""
        self._require_intent("write_file")
        logger.debug("FileSystemTool.write_file: checking grant for %s", path)
        err = self._check_grant(path, MODE_ALLOWS_WRITE)
        if err:
            return err
        result = self._executor.write(path, content)
        return self._wrap(result)

    def create_file(self, path: str, content: str) -> ToolResult:
        """Create a new file (fails if exists)."""
        self._require_intent("create_file")
        logger.debug("FileSystemTool.create_file: checking grant for %s", path)
        err = self._check_grant(path, MODE_ALLOWS_CREATE)
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
        logger.debug("FileSystemTool.delete_file: checking grant for %s", path)
        err = self._check_grant(path, MODE_ALLOWS_DELETE)
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
        logger.debug("FileSystemTool.edit_file: checking grant for %s", path)
        err = self._check_grant(path, MODE_ALLOWS_WRITE)
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

    def list_directory(self, path: str = ".", depth: int = 2, max_entries: int = 50) -> ToolResult:
        """The tree under `path`, `depth` levels deep, at most `max_entries` entries.

        Entries are paths from the project root; a directory ends in `/`. A symlink, an excluded folder or a
        folder no grant covers is listed but never entered; an entry no grant covers is left out.
        """
        self._require_intent("list_directory")
        err = self._check_grant(path, MODE_ALLOWS_READ)
        if err:
            return err
        listed = self._executor.dir_kinds(path)
        if listed.status != "success":
            return self._wrap(listed)
        entries: list[str] = []
        self._walk(
            self._from_root(path), "", listed.data, max(depth, 1), entries, max(max_entries, 1)
        )
        return ToolResult(status="success", data=entries)

    def _walk(
        self,
        root: str,
        prefix: str,
        kinds: list[tuple[str, str]],
        depth: int,
        entries: list[str],
        cap: int,
    ) -> bool:
        """Add `kinds` under `prefix` to `entries`; False once `cap` is reached."""
        for name, kind in kinds:
            full = _joined(root, prefix + name)
            if self._check_grant(full, MODE_ALLOWS_READ) is not None:
                continue
            if len(entries) == cap:
                entries.append(f"… more entries; list a subfolder or raise max_entries ({cap})")
                return False
            entries.append(full + ("/" if kind == "dir" else ""))
            if self._enters(kind, name, depth) and not self._descend(
                root, f"{prefix}{name}/", full, depth, entries, cap
            ):
                return False
        return True

    def _enters(self, kind: str, name: str, depth: int) -> bool:
        """A real folder, not excluded, with levels left; never a link."""
        return kind == "dir" and depth > 1 and name not in self._exclude_dirs

    def _descend(
        self, root: str, prefix: str, full: str, depth: int, entries: list[str], cap: int
    ) -> bool:
        inner = self._executor.dir_kinds(full)
        return inner.status != "success" or self._walk(
            root, prefix, inner.data, depth - 1, entries, cap
        )

    def grep(
        self,
        path: str,
        pattern: str,
        *,
        context_lines: int = 3,
        case_sensitive: bool = False,
        max_results: int = 20,
    ) -> ToolResult:
        """Search for a pattern in file contents using ripgrep or Python fallback.

        Args:
            path: Relative directory path to search.
            pattern: Search pattern (string or regex).
            context_lines: Lines of context before/after each match.
            case_sensitive: Whether to perform case-sensitive search.
            max_results: Maximum number of matches to return.
        """
        resolved = self._search_root("grep", path)
        if isinstance(resolved, ToolResult):
            return resolved
        from specweaver.sandbox.filesystem.core.search import grep_content

        results = grep_content(
            resolved,
            pattern,
            context_lines=context_lines,
            case_sensitive=case_sensitive,
            max_results=max_results,
            exclude_dirs=self._exclude_dirs,
        )
        return ToolResult(status="success", data=_rooted(results, self._from_root(path), "file"))

    def find_files(
        self,
        path: str,
        pattern: str,
        *,
        file_type: str = "any",
        max_results: int = 30,
    ) -> ToolResult:
        """Find files matching a glob pattern.

        Args:
            path: Relative directory path to search.
            pattern: Glob pattern (e.g., '*.py', 'context.yaml').
            file_type: Filter: 'file', 'directory', or 'any'.
            max_results: Maximum number of results.
        """
        resolved = self._search_root("find_files", path)
        if isinstance(resolved, ToolResult):
            return resolved
        from specweaver.sandbox.filesystem.core.search import find_by_glob

        results = find_by_glob(
            resolved,
            pattern,
            file_type=file_type,
            max_results=max_results,
            exclude_dirs=self._exclude_dirs,
        )
        return ToolResult(status="success", data=_rooted(results, self._from_root(path), "path"))

    # Internal: role gating

    def _require_intent(self, intent: str) -> None:
        """Raise if the current role doesn't have this intent."""
        if intent not in ROLE_INTENTS[self._role]:
            msg = (
                f"Intent {intent!r} is not allowed for role {self._role!r}. "
                f"Allowed: {sorted(ROLE_INTENTS[self._role])}"
            )
            raise FileSystemToolError(msg)

    # Internal: boundary enforcement

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Normalise a path for grant matching (see `normalize_grant_path`)."""
        return normalize_grant_path(path)

    def _from_root(self, path: str) -> str:
        """`path` as the executor resolves it, from the project root; "" for the root."""
        resolved = self._executor.contained(path)
        if resolved is None:
            return path.strip("/")
        rel = resolved.relative_to(self._executor.cwd).as_posix()
        return "" if rel == "." else rel

    def _search_root(self, intent: str, path: str) -> Path | ToolResult:
        """The folder a search starts from, or the error that refuses it."""
        self._require_intent(intent)
        err = self._check_grant(path, MODE_ALLOWS_READ)
        if err:
            return err
        resolved = self._executor.contained(path)
        if resolved is None or not resolved.is_dir():
            return ToolResult(status="error", message=f"Not a directory: {path}")
        return resolved

    def _check_grant(
        self,
        path: str,
        required_modes: frozenset[AccessMode],
    ) -> ToolResult | None:
        """Check if any grant allows the operation on this path.

        Returns None if allowed, or an error ToolResult if blocked.
        """
        normalized = self._normalize_path(path)

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
        """The most permissive grant covering this path (see `grant_mode_for`)."""
        return grant_mode_for(normalized_path, self._grants, self._executor.cwd)

    @staticmethod
    def _wrap(result: ExecutorResult) -> ToolResult:
        """Convert an ExecutorResult to a ToolResult."""
        if result.status == "success":
            return ToolResult(status="success", data=result.data)
        return ToolResult(status="error", message=result.error)


def _joined(root: str, relative: str) -> str:
    """`relative` under the listed `root`, as a path from the project root."""
    return relative if root in ("", ".") else f"{root.rstrip('/')}/{relative}"


def _rooted(results: list[dict[str, Any]], base: str, key: str) -> list[dict[str, Any]]:
    """Search results with `key` turned into a path from the project root."""
    return [{**r, key: _joined(base, r[key])} if key in r else r for r in results]
