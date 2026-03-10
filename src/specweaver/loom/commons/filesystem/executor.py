# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""FileExecutor — low-level filesystem operations with security controls.

All operations are constrained to the project directory set at construction time.
The working directory is set by setup/config — the agent cannot change it.

Security controls:
- Path traversal prevention (resolve + startswith check)
- Symlink blocking (prevent escape via symlink chains)
- Protected file patterns (context.yaml, .env, .git/, .specweaver/)
- Atomic writes (temp file + os.replace)
- Windows ADS blocking (alternate data streams)
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExecutorResult:
    """Standardized result from a file operation.

    Attributes:
        status: "success" or "error".
        data: Operation-specific data (file content, stat info, etc.).
        error: Error message if status is "error".
    """

    status: str
    data: Any = None
    error: str = ""


class FileExecutorError(Exception):
    """Raised when a FileExecutor operation is blocked or misconfigured."""


class FileExecutor:
    """Low-level filesystem operations with security controls.

    Args:
        cwd: Working directory (the target project root).
             Set by setup/config — the agent cannot change this.

    Security:
        - Protected patterns block write/delete/move on sensitive files.
        - Path traversal is always prevented (agent stays inside cwd).
        - Symlinks are blocked (prevent escape via symlink chains).
        - Writes are atomic (temp file + os.replace).
    """

    # Files/directories that are NEVER writable by standard agents.
    _PROTECTED_PATTERNS: frozenset[str] = frozenset({
        "context.yaml",
        ".env",
        ".git",
        ".specweaver",
    })

    def __init__(self, cwd: Path) -> None:
        if not cwd.exists():
            msg = f"Working directory does not exist: {cwd}"
            raise FileExecutorError(msg)
        if not cwd.is_dir():
            msg = f"Working directory is not a directory: {cwd}"
            raise FileExecutorError(msg)
        self._cwd = cwd.resolve()

    @property
    def cwd(self) -> Path:
        """The project root directory (read-only)."""
        return self._cwd

    # -------------------------------------------------------------------
    # Public operations
    # -------------------------------------------------------------------

    def read(self, path: str, *, max_bytes: int = 100 * 1024) -> ExecutorResult:
        """Read a file's contents (UTF-8).

        Args:
            path: Relative path within cwd.
            max_bytes: Maximum file size allowed (default: 100KB).

        Returns:
            ExecutorResult with data=file contents or error.
        """
        resolved = self._validate_path(path)
        if resolved is None:
            return ExecutorResult(status="error", error=f"Path validation failed: {path}")

        if not resolved.exists():
            return ExecutorResult(status="error", error=f"File not found: {path}")

        if not resolved.is_file():
            return ExecutorResult(status="error", error=f"Not a file: {path}")

        try:
            size = resolved.stat().st_size
        except OSError as exc:
            return ExecutorResult(status="error", error=f"Cannot stat file: {exc}")

        if size > max_bytes:
            return ExecutorResult(
                status="error",
                error=f"File exceeds max_bytes ({size} > {max_bytes})",
            )

        try:
            content = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return ExecutorResult(status="error", error=f"File is not valid UTF-8: {path}")
        except OSError as exc:
            return ExecutorResult(status="error", error=f"Read failed: {exc}")

        return ExecutorResult(status="success", data=content)

    def write(self, path: str, content: str) -> ExecutorResult:
        """Write content to a file (atomic).

        Creates parent directories if needed. Uses atomic temp file + rename.

        Args:
            path: Relative path within cwd.
            content: UTF-8 text to write.
        """
        resolved = self._validate_path(path)
        if resolved is None:
            return ExecutorResult(status="error", error=f"Path validation failed: {path}")

        if self._is_protected(path):
            return ExecutorResult(status="error", error=f"Protected file: {path}")

        tmp_path = resolved.with_suffix(f".tmp.{uuid.uuid4()}")
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_text(content, encoding="utf-8")
            os.replace(tmp_path, resolved)
        except OSError as exc:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            return ExecutorResult(status="error", error=f"Write failed: {exc}")

        return ExecutorResult(status="success", data=str(resolved))

    def delete(self, path: str) -> ExecutorResult:
        """Delete a file.

        Refuses to delete directories — use explicit directory removal.

        Args:
            path: Relative path within cwd.
        """
        resolved = self._validate_path(path)
        if resolved is None:
            return ExecutorResult(status="error", error=f"Path validation failed: {path}")

        if self._is_protected(path):
            return ExecutorResult(status="error", error=f"Protected file: {path}")

        if not resolved.exists():
            return ExecutorResult(status="error", error=f"File not found: {path}")

        if resolved.is_dir():
            return ExecutorResult(status="error", error=f"Cannot delete directory: {path}")

        try:
            resolved.unlink()
        except OSError as exc:
            return ExecutorResult(status="error", error=f"Delete failed: {exc}")

        return ExecutorResult(status="success")

    def mkdir(self, path: str) -> ExecutorResult:
        """Create a directory (and parents).

        Idempotent — does not error if directory already exists.

        Args:
            path: Relative path within cwd.
        """
        resolved = self._validate_path(path)
        if resolved is None:
            return ExecutorResult(status="error", error=f"Path validation failed: {path}")

        if self._is_protected(path):
            return ExecutorResult(status="error", error=f"Protected path: {path}")

        try:
            resolved.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return ExecutorResult(status="error", error=f"Mkdir failed: {exc}")

        return ExecutorResult(status="success")

    def list_dir(self, path: str) -> ExecutorResult:
        """List directory contents.

        Args:
            path: Relative path within cwd. Empty string for project root.

        Returns:
            ExecutorResult with data=list of entry names.
        """
        if path == "":
            resolved = self._cwd
        else:
            resolved = self._validate_path(path)
            if resolved is None:
                return ExecutorResult(status="error", error=f"Path validation failed: {path}")

        if not resolved.exists():
            return ExecutorResult(status="error", error=f"Directory not found: {path}")

        if not resolved.is_dir():
            return ExecutorResult(status="error", error=f"Not a directory: {path}")

        try:
            entries = sorted(p.name for p in resolved.iterdir())
        except OSError as exc:
            return ExecutorResult(status="error", error=f"List failed: {exc}")

        return ExecutorResult(status="success", data=entries)

    def exists(self, path: str) -> ExecutorResult:
        """Check if a path exists.

        Args:
            path: Relative path within cwd.

        Returns:
            ExecutorResult with data=True/False.
        """
        resolved = self._validate_path(path)
        if resolved is None:
            return ExecutorResult(status="error", error=f"Path validation failed: {path}")

        return ExecutorResult(status="success", data=resolved.exists())

    def stat(self, path: str) -> ExecutorResult:
        """Get file/directory metadata.

        Args:
            path: Relative path within cwd.

        Returns:
            ExecutorResult with data=dict containing size, is_file, is_dir, mtime.
        """
        resolved = self._validate_path(path)
        if resolved is None:
            return ExecutorResult(status="error", error=f"Path validation failed: {path}")

        if not resolved.exists():
            return ExecutorResult(status="error", error=f"Path not found: {path}")

        try:
            st = resolved.stat()
        except OSError as exc:
            return ExecutorResult(status="error", error=f"Stat failed: {exc}")

        return ExecutorResult(
            status="success",
            data={
                "size": st.st_size,
                "is_file": resolved.is_file(),
                "is_dir": resolved.is_dir(),
                "mtime": st.st_mtime,
            },
        )

    def move(self, src: str, dst: str) -> ExecutorResult:
        """Move/rename a file or directory.

        Creates destination parent directories if needed.

        Args:
            src: Source relative path.
            dst: Destination relative path.
        """
        resolved_src = self._validate_path(src)
        if resolved_src is None:
            return ExecutorResult(status="error", error=f"Source path validation failed: {src}")

        resolved_dst = self._validate_path(dst)
        if resolved_dst is None:
            return ExecutorResult(status="error", error=f"Destination path validation failed: {dst}")

        if self._is_protected(src):
            return ExecutorResult(status="error", error=f"Protected source: {src}")

        if self._is_protected(dst):
            return ExecutorResult(status="error", error=f"Protected destination: {dst}")

        if not resolved_src.exists():
            return ExecutorResult(status="error", error=f"Source not found: {src}")

        try:
            resolved_dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(resolved_src, resolved_dst)
        except OSError as exc:
            return ExecutorResult(status="error", error=f"Move failed: {exc}")

        return ExecutorResult(status="success")

    # -------------------------------------------------------------------
    # Path validation & security
    # -------------------------------------------------------------------

    def _validate_path(self, path: str) -> Path | None:
        """Resolve and validate a relative path.

        Returns None if the path fails security checks:
        - Absolute paths rejected
        - Path traversal (../) rejected
        - Symlinks rejected
        - Windows ADS rejected

        Returns:
            Resolved Path, or None if validation fails.
        """
        if not path:
            return None

        # Block absolute paths
        if os.path.isabs(path):
            return None

        # Block Windows Alternate Data Streams (colon in path segment)
        if os.name == "nt" and ":" in path:
            return None
        elif os.name != "nt" and ":" in path.split("/")[-1]:
            # Also catch ADS-like notation on non-Windows
            # "file.txt:stream" pattern
            for segment in path.replace("\\", "/").split("/"):
                if ":" in segment:
                    return None

        try:
            candidate = (self._cwd / path).resolve()
        except (OSError, ValueError):
            return None

        # Must be inside cwd (traversal check)
        try:
            candidate.relative_to(self._cwd)
        except ValueError:
            return None

        # Check for symlinks anywhere in the path
        check_path = self._cwd / path
        if self._has_symlink(check_path):
            return None

        return candidate

    def _has_symlink(self, path: Path) -> bool:
        """Check if any component of the path is a symlink."""
        # Walk up from the target to cwd, checking each component
        parts = path.relative_to(self._cwd).parts
        current = self._cwd
        for part in parts:
            current = current / part
            if current.is_symlink():
                return True
        return False

    def _is_protected(self, path: str) -> bool:
        """Check if a path matches any protected pattern.

        Protected patterns block write/delete/move but not read.
        """
        normalized = path.replace("\\", "/")
        parts = normalized.split("/")

        for part in parts:
            if part in self._PROTECTED_PATTERNS:
                return True

        return False


class EngineFileExecutor(FileExecutor):
    """FileExecutor for engine/atom use — bypasses protected patterns.

    Path traversal and symlink blocking are still enforced (always a security risk).
    Only protected file patterns are bypassed.
    """

    _PROTECTED_PATTERNS: frozenset[str] = frozenset()  # No protected patterns
