# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Scope detection and resolution for multi-scope standards.

Detects scope boundaries in a project (up to 2 levels deep) and resolves
which scope a given file belongs to.

Usage::

    from specweaver.standards.scope_detector import detect_scopes, _resolve_scope

    scopes = detect_scopes(Path("/proj"))
    # [".", "backend/auth", "backend/payments", "frontend"]

    scope = _resolve_scope(Path("/proj/backend/auth/login.py"), Path("/proj"), scopes)
    # "backend/auth"
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.standards.discovery import _SKIP_DIRS

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

#: Source file extensions recognized for scope detection.
_SOURCE_EXTENSIONS: frozenset[str] = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".go", ".rs", ".java", ".kt", ".rb",
    ".c", ".cpp", ".h", ".hpp", ".cs",
    ".swift", ".scala", ".clj",
})


def detect_scopes(project_path: Path) -> list[str]:
    """Detect scope boundaries up to 2 levels deep.

    Scans top-level directories (L1) and their direct children (L2) for
    source files.  If an L1 directory has sub-directories (L2) with source
    files, only those L2 dirs are scopes (L1 is excluded to avoid
    double-counting).  If an L1 directory has source files but no L2
    sub-scopes, L1 itself is a scope.

    Always includes ``"."`` (root scope).

    Args:
        project_path: Absolute path to the project root.

    Returns:
        Sorted list of scope names.
    """
    scopes: list[str] = ["."]

    for entry in sorted(project_path.iterdir()):
        if not entry.is_dir():
            continue
        name = entry.name

        # Skip hidden dirs and well-known non-source dirs
        if name.startswith(".") or name in _SKIP_DIRS:
            continue

        # Check L2 (sub-directories of this L1 dir)
        l2_scopes = _detect_l2_scopes(entry, name)

        if l2_scopes:
            # L1 has sub-scopes → only sub-scopes are scopes (not L1 itself)
            scopes.extend(l2_scopes)
        elif _has_source_files(entry):
            # L1 has source files but no sub-scopes → L1 is a scope
            scopes.append(name)

    return sorted(scopes)


def _detect_l2_scopes(entry: Path, parent_name: str) -> list[str]:
    """Detect L2 sub-scopes within an L1 directory."""
    l2_scopes: list[str] = []
    try:
        for sub in sorted(entry.iterdir()):
            if not sub.is_dir():
                continue
            sub_name = sub.name
            if sub_name.startswith(".") or sub_name in _SKIP_DIRS:
                continue
            if _has_source_files(sub):
                l2_scopes.append(f"{parent_name}/{sub_name}")
    except PermissionError:
        logger.debug("Permission denied: %s", entry)
    return l2_scopes


def _has_source_files(directory: Path) -> bool:
    """Check if a directory contains source files (non-recursive).

    Only checks direct children, not subdirectories.

    Args:
        directory: Directory to check.

    Returns:
        True if at least one file has a recognized source extension.
    """
    try:
        for entry in directory.iterdir():
            if entry.is_file() and entry.suffix in _SOURCE_EXTENSIONS:
                return True
    except PermissionError:
        logger.debug("Permission denied: %s", directory)
    return False


def _resolve_scope(
    target_path: Path,
    project_path: Path,
    known_scopes: list[str],
) -> str:
    """Resolve which scope a file belongs to via walk-up.

    Walks up from *target_path* toward *project_path*, checking at each
    level whether the relative path prefix matches a known scope.
    Longest-prefix match wins.

    Args:
        target_path: Absolute path to the file being reviewed/generated.
        project_path: Absolute path to the project root.
        known_scopes: List of known scope names from the DB.

    Returns:
        The matching scope name, or ``"."`` if no specific scope matches.
    """
    try:
        rel = target_path.relative_to(project_path)
    except ValueError:
        return "."

    # Build all parent prefixes from longest to shortest
    # e.g., for "backend/auth/handlers/login.py":
    #   → ["backend/auth/handlers", "backend/auth", "backend"]
    parts = rel.parts[:-1]  # Exclude the filename itself

    for i in range(len(parts), 0, -1):
        prefix = "/".join(parts[:i])
        if prefix in known_scopes:
            return prefix

    return "."
