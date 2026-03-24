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

import posixpath
import re
from typing import TYPE_CHECKING, Any

from specweaver.loom.tools.filesystem.models import (
    MODE_ALLOWS_CREATE,
    MODE_ALLOWS_DELETE,
    MODE_ALLOWS_READ,
    MODE_ALLOWS_WRITE,
    ROLE_INTENTS,
    AccessMode,
    FileSystemToolError,
    FolderGrant,
    ToolResult,
)

if TYPE_CHECKING:
    from specweaver.loom.commons.filesystem.executor import ExecutorResult, FileExecutor


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

    # Intent methods

    def read_file(self, path: str) -> ToolResult:
        """Read a file's contents."""
        self._require_intent("read_file")
        err = self._check_grant(path, MODE_ALLOWS_READ)
        if err:
            return err
        result = self._executor.read(path)
        return self._wrap(result)

    def write_file(self, path: str, content: str) -> ToolResult:
        """Overwrite a file's contents."""
        self._require_intent("write_file")
        err = self._check_grant(path, MODE_ALLOWS_WRITE)
        if err:
            return err
        result = self._executor.write(path, content)
        return self._wrap(result)

    def create_file(self, path: str, content: str) -> ToolResult:
        """Create a new file (fails if exists)."""
        self._require_intent("create_file")
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

    def list_directory(self, path: str) -> ToolResult:
        """List directory contents."""
        self._require_intent("list_directory")
        err = self._check_grant(path, MODE_ALLOWS_READ)
        if err:
            return err
        result = self._executor.list_dir(path)
        return self._wrap(result)

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
        self._require_intent("grep")
        err = self._check_grant(path, MODE_ALLOWS_READ)
        if err:
            return err
        resolved = self._executor.cwd / path
        if not resolved.is_dir():
            return ToolResult(status="error", message=f"Not a directory: {path}")
        from specweaver.loom.commons.filesystem.search import grep_content
        results = grep_content(
            resolved.resolve(), pattern,
            context_lines=context_lines,
            case_sensitive=case_sensitive,
            max_results=max_results,
        )
        return ToolResult(status="success", data=results)

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
        self._require_intent("find_files")
        err = self._check_grant(path, MODE_ALLOWS_READ)
        if err:
            return err
        resolved = self._executor.cwd / path
        if not resolved.is_dir():
            return ToolResult(status="error", message=f"Not a directory: {path}")
        from specweaver.loom.commons.filesystem.search import find_by_glob
        results = find_by_glob(
            resolved.resolve(), pattern,
            file_type=file_type,
            max_results=max_results,
        )
        return ToolResult(status="success", data=results)

    def search_content(
        self,
        path: str,
        regex: str,
        *,
        recursive: bool = False,
    ) -> ToolResult:
        """Search for a regex pattern across files in a directory.

        Args:
            path: Directory to search in.
            regex: Regex pattern to match against each line.
            recursive: If True, search subdirectories recursively.

        Returns:
            ToolResult with data=list of {file, line, content} matches.
        """
        self._require_intent("search_content")
        err = self._check_grant(path, MODE_ALLOWS_READ)
        if err:
            return err

        try:
            pattern = re.compile(regex, re.MULTILINE)
        except re.error as exc:
            return ToolResult(status="error", message=f"Invalid regex: {exc}")

        matches: list[dict[str, Any]] = []

        if recursive:
            self._search_recursive(path, pattern, matches)
        else:
            self._search_flat(path, pattern, matches)

        return ToolResult(status="success", data=matches)

    def _search_flat(
        self,
        path: str,
        pattern: re.Pattern[str],
        matches: list[dict[str, Any]],
    ) -> None:
        """Search direct children of a directory."""
        list_result = self._executor.list_dir(path)
        if list_result.status != "success":
            return

        for name in list_result.data:
            file_path = f"{path}/{name}" if path else name
            read_result = self._executor.read(file_path)
            if read_result.status != "success":
                continue
            for i, line in enumerate(read_result.data.splitlines(), 1):
                if pattern.search(line):
                    matches.append({"file": name, "line": i, "content": line.strip()})

    def _search_recursive(
        self,
        path: str,
        pattern: re.Pattern[str],
        matches: list[dict[str, Any]],
    ) -> None:
        """Search directory and all subdirectories recursively."""
        import os

        base = self._executor._cwd / path
        if not base.is_dir():
            return

        for dirpath, _dirnames, filenames in os.walk(base):
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                rel = os.path.relpath(full, self._executor._cwd).replace("\\", "/")
                read_result = self._executor.read(rel)
                if read_result.status != "success":
                    continue
                for i, line in enumerate(read_result.data.splitlines(), 1):
                    if pattern.search(line):
                        matches.append({"file": rel, "line": i, "content": line.strip()})

    def find_placement(self, description: str) -> ToolResult:
        """Semantic search over context.yaml purpose fields.

        MVP: Keyword matching — splits description into words, scores each
        context.yaml boundary by how many keywords appear in its purpose.
        Results sorted by score descending.

        Args:
            description: What the new code does.

        Returns:
            ToolResult with data=list of matching boundaries (path, name, purpose, score).
        """
        self._require_intent("find_placement")

        # Extract keywords (lowercase, 3+ chars to skip noise like 'a', 'to')
        keywords = [w.lower() for w in re.split(r"\s+", description.strip()) if len(w) >= 3]
        if not keywords:
            return ToolResult(status="success", data=[])

        # Walk all context.yaml files in the project
        import os

        from ruamel.yaml import YAML

        yaml = YAML()
        scored: list[dict[str, Any]] = []

        for dirpath, _dirnames, filenames in os.walk(self._executor._cwd):
            if "context.yaml" not in filenames:
                continue
            ctx_file = os.path.join(dirpath, "context.yaml")
            try:
                with open(ctx_file, encoding="utf-8") as fh:
                    data = yaml.load(fh)
            except Exception:
                continue
            if data is None:
                continue

            purpose = str(data.get("purpose", "")).lower()
            name = str(data.get("name", ""))
            if not purpose:
                continue

            # Score: count how many keywords appear as substrings in purpose
            score = sum(1 for kw in keywords if kw in purpose)
            if score == 0:
                continue

            rel_path = os.path.relpath(dirpath, self._executor._cwd).replace("\\", "/")
            if rel_path == ".":
                rel_path = ""

            scored.append(
                {
                    "path": rel_path,
                    "name": name,
                    "purpose": data.get("purpose", ""),
                    "score": score,
                }
            )

        # Sort by score descending
        scored.sort(key=lambda x: x["score"], reverse=True)

        return ToolResult(status="success", data=scored)

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
        """Normalize a path for grant matching.

        Resolves .., strips trailing slashes, normalizes backslashes.
        This is CRITICAL for security — without it, agents can bypass
        grants using paths like 'src/domain/billing/../../shared/secret.py'.
        """
        # Normalize separators
        forward = path.replace("\\", "/")
        # Resolve .. and . segments
        normalized = posixpath.normpath(forward)
        # normpath returns '.' for empty string, keep it consistent
        if normalized == ".":
            return ""
        return normalized

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
        """Find the most permissive mode that covers this path.

        Returns None if no grant covers the path.
        """
        # Mode priority for "most permissive"
        mode_priority = {AccessMode.READ: 0, AccessMode.WRITE: 1, AccessMode.FULL: 2}
        best: AccessMode | None = None

        for grant in self._grants:
            grant_path = grant.path.replace("\\", "/").rstrip("/")

            if self._path_matches_grant(normalized_path, grant_path, grant.recursive) and (
                best is None or mode_priority[grant.mode] > mode_priority[best]
            ):
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

    # Internal: result wrapping

    @staticmethod
    def _wrap(result: ExecutorResult) -> ToolResult:
        """Convert an ExecutorResult to a ToolResult."""
        if result.status == "success":
            return ToolResult(status="success", data=result.data)
        return ToolResult(status="error", message=result.error)
