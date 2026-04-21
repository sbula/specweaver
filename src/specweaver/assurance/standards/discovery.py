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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.workspace.context.analyzer_protocols import AnalyzerFactoryProtocol

logger = logging.getLogger(__name__)


def discover_files(project_path: Path, analyzer_factory: AnalyzerFactoryProtocol) -> list[Path]:
    """Discover source files using the priority chain.

    Priority:
    1. ``git ls-files`` if ``.git/`` directory exists
    2. ``os.walk`` with hardcoded skip patterns (fallback)

    In both cases, ``.specweaverignore`` patterns are applied on top.

    Args:
        project_path: Root directory of the project.
        analyzer_factory: injected provider for polyglot bounds.

    Returns:
        Sorted list of absolute ``Path`` objects for discovered source files.
    """
    files: list[Path] | None = None

    # Try git ls-files if this looks like a git repo
    if (project_path / ".git").is_dir():
        files = _git_ls_files(project_path)

    # Fallback to os.walk
    if files is None:
        files = _walk_with_skips(project_path, analyzer_factory)

    # Apply .specweaverignore on top
    files = _apply_specweaverignore(files, project_path, analyzer_factory)

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


def _walk_with_skips(project_path: Path, analyzer_factory: AnalyzerFactoryProtocol) -> list[Path]:
    """Fallback: ``os.walk`` with dynamic AnalyzerFactory skip patterns."""

    logger.debug("Using os.walk fallback for file discovery")
    files: list[Path] = []

    skip_dirs = {".git"}
    for analyzer in analyzer_factory.get_all_analyzers():
        for ign in analyzer.get_default_directory_ignores():
            skip_dirs.add(ign.rstrip("/"))

    for root, dirs, filenames in os.walk(project_path):
        # Prune skipped directories in-place (modifies os.walk traversal)
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]

        for name in filenames:
            full = Path(root) / name
            files.append(full.resolve())

    return files


def _apply_specweaverignore(
    files: list[Path],
    project_path: Path,
    analyzer_factory: AnalyzerFactoryProtocol,
) -> list[Path]:
    """Filter files through ``.specweaverignore`` and AnalyzerFactory binary patterns.

    Uses ``pathspec`` library for ``.gitignore``-compatible pattern matching.
    If ``pathspec`` is not installed, returns files unchanged.
    """
    try:
        import pathspec
    except ImportError:
        logger.warning(
            "pathspec not installed — ignoring AnalyzerFactory binary patterns and .specweaverignore",
        )
        return files

    patterns: list[str] = []
    ignore_file = project_path / ".specweaverignore"
    if ignore_file.is_file():
        patterns.extend(ignore_file.read_text(encoding="utf-8").splitlines())

    for analyzer in analyzer_factory.get_all_analyzers():
        patterns.extend(analyzer.get_binary_ignore_patterns())
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
