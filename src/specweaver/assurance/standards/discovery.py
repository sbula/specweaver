# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""File discovery for standards analysis.

Implements a priority chain for finding analyzable source files:

1. ``git ls-files`` — if ``.git/`` exists and git is on PATH
2. ``.specweaverignore`` — additional excludes (always checked)
3. ``os.walk`` + hardcoded skips — fallback for non-git projects

Usage::

    from specweaver.assurance.standards.discovery import discover_files

    files = discover_files(project_path)
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Directories to skip unconditionally when walking (non-git fallback).
_SKIP_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        "venv",
        ".venv",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        "dist",
        "build",
        ".eggs",
        ".ruff_cache",
        ".nox",
    }
)


def discover_files(project_path: Path) -> list[Path]:
    """Discover source files using the priority chain.

    Priority:
    1. ``git ls-files`` if ``.git/`` directory exists
    2. ``os.walk`` with hardcoded skip patterns (fallback)

    In both cases, ``.specweaverignore`` patterns are applied on top.

    Args:
        project_path: Root directory of the project.

    Returns:
        Sorted list of absolute ``Path`` objects for discovered source files.
    """
    files: list[Path] | None = None

    # Try git ls-files if this looks like a git repo
    if (project_path / ".git").is_dir():
        files = _git_ls_files(project_path)

    # Fallback to os.walk
    if files is None:
        files = _walk_with_skips(project_path)

    # Apply .specweaverignore on top
    files = _apply_specweaverignore(files, project_path)

    return sorted(files)


def _git_ls_files(project_path: Path) -> list[Path] | None:
    """Try ``git ls-files``.  Returns None if git is unavailable.

    Uses ``--cached --others --exclude-standard`` to get tracked files
    plus untracked-but-not-ignored files.
    """
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(project_path),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        logger.debug("git not available or timed out, falling back to os.walk")
        return None

    if result.returncode != 0:
        logger.debug(
            "git ls-files failed (rc=%d), falling back to os.walk",
            result.returncode,
        )
        return None

    files: list[Path] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            full = (project_path / line).resolve()
            if full.is_file():
                files.append(full)

    logger.debug("git ls-files discovered %d files", len(files))
    return files


def _walk_with_skips(project_path: Path) -> list[Path]:
    """Fallback: ``os.walk`` with hardcoded skip patterns."""
    logger.debug("Using os.walk fallback for file discovery")
    files: list[Path] = []

    for root, dirs, filenames in os.walk(project_path):
        # Prune skipped directories in-place (modifies os.walk traversal)
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]

        for name in filenames:
            full = Path(root) / name
            files.append(full.resolve())

    return files


def _apply_specweaverignore(
    files: list[Path],
    project_path: Path,
) -> list[Path]:
    """Filter files through ``.specweaverignore`` patterns.

    Uses ``pathspec`` library for ``.gitignore``-compatible pattern matching.
    If ``.specweaverignore`` doesn't exist or ``pathspec`` is not installed,
    returns files unchanged.
    """
    ignore_file = project_path / ".specweaverignore"
    if not ignore_file.is_file():
        return files

    try:
        import pathspec
    except ImportError:
        logger.warning(
            ".specweaverignore found but 'pathspec' not installed — ignoring",
        )
        return files

    patterns = ignore_file.read_text(encoding="utf-8").splitlines()
    spec = pathspec.PathSpec.from_lines("gitignore", patterns)

    result: list[Path] = []
    for f in files:
        try:
            rel = f.relative_to(project_path.resolve())
        except ValueError:
            result.append(f)
            continue
        if not spec.match_file(str(rel)):
            result.append(f)

    return result
