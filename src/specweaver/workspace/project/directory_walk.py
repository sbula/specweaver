# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Walking up a directory tree, bounded.

Split out of `_helpers.py` by `TECH-015`. Genuinely generic traversal, with no knowledge of what is
being looked for — which is exactly why it kept company it had nothing to do with.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


def walk_up_dirs(
    project_path: Path,
    spec_path: Path | None,
) -> list[Path]:
    """Build ordered list of directories to search for constitution.

    Starts at spec_path's parent, walks up to project_path (inclusive).
    Returns [project_path] if spec_path is None.
    """
    project_resolved = project_path.resolve()

    if spec_path is None:
        return [project_resolved]

    directories: list[Path] = []
    current = spec_path.resolve().parent

    while True:
        directories.append(current)
        if current == project_resolved:
            break
        parent = current.parent
        if parent == current:
            # Reached filesystem root without finding project_path
            break
        # Don't walk above project_path
        if not str(current).startswith(str(project_resolved)):
            break
        current = parent

    # Ensure project_path is always in the list
    if project_resolved not in directories:
        directories.append(project_resolved)

    return directories
