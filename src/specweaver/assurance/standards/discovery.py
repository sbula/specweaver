# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""File discovery for standards analysis.

One walk, with no process run, so a project gives the same files with or without git:

1. ``os.walk`` from the project root, skipping ``.git``, hidden folders and the analyzers' build
   and cache folders.
2. The project's ``.gitignore`` files, root and nested, each scoped to its own folder.
3. ``.specweaverignore`` and the analyzers' binary patterns, on top.

Usage::

    from specweaver.assurance.standards.discovery import discover_files

    files = discover_files(project_path, AnalyzerFactory)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pathspec

if TYPE_CHECKING:
    from specweaver.workspace.context.analyzer_protocols import AnalyzerFactoryProtocol

logger = logging.getLogger(__name__)


def discover_files(project_path: Path, analyzer_factory: AnalyzerFactoryProtocol) -> list[Path]:
    """The project's source files, as ``git ls-files --cached --others --exclude-standard`` would
    list them, minus the built-in skips and ``.specweaverignore``.

    Git's global excludes and ``.git/info/exclude`` are not read.

    Args:
        project_path: Root directory of the project.
        analyzer_factory: injected provider for polyglot bounds.

    Returns:
        Sorted list of absolute ``Path`` objects for discovered source files.
    """
    files = _walk(project_path, analyzer_factory)
    files = _apply_specweaverignore(files, project_path, analyzer_factory)
    return sorted(files)


#: The ``.gitignore`` files in force for a folder, root first: each with the folder it is relative to.
_Rules = list[tuple[Path, pathspec.PathSpec]]


def _walk(project_path: Path, analyzer_factory: AnalyzerFactoryProtocol) -> list[Path]:
    """Every file not skipped, ignored by a ``.gitignore``, or under an ignored folder."""
    skip_dirs = {".git"}
    for analyzer in analyzer_factory.get_all_analyzers():
        for ign in analyzer.get_default_directory_ignores():
            skip_dirs.add(ign.rstrip("/"))

    files: list[Path] = []
    rules_of: dict[Path, _Rules] = {}
    for root, dirs, filenames in os.walk(project_path):
        here = Path(root)
        rules = rules_of.pop(here, []) + _gitignore(here)
        # Git does not enter an ignored folder, so nothing under it can be re-included.
        dirs[:] = [
            d
            for d in dirs
            if d not in skip_dirs and not d.startswith(".") and not _ignored(rules, here / d, True)
        ]
        for d in dirs:
            rules_of[here / d] = rules
        files += [
            (here / name).resolve() for name in filenames if not _ignored(rules, here / name, False)
        ]
    return files


def _gitignore(folder: Path) -> _Rules:
    """The ``.gitignore`` in ``folder``, if one can be read."""
    path = folder / ".gitignore"
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Standards discovery skipped %s: %s", path.as_posix(), exc)
        return []
    return [(folder, pathspec.PathSpec.from_lines("gitignore", lines))]


def _ignored(rules: _Rules, path: Path, is_dir: bool) -> bool:
    """Git's verdict: the last pattern that matches decides, and a deeper file comes later."""
    verdict = False
    for base, spec in rules:
        rel = path.relative_to(base).as_posix() + ("/" if is_dir else "")
        include = spec.check_file(rel).include
        if include is not None:
            verdict = include
    return verdict


def _apply_specweaverignore(
    files: list[Path],
    project_path: Path,
    analyzer_factory: AnalyzerFactoryProtocol,
) -> list[Path]:
    """Filter files through ``.specweaverignore`` and AnalyzerFactory binary patterns.

    Uses ``pathspec`` library for ``.gitignore``-compatible pattern matching.
    """
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
        except ValueError:  # expected: a file outside the project is never ignored
            result.append(f)
            continue
        if not spec.match_file(str(rel)):
            result.append(f)

    return result
