# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Walking up a directory tree, bounded.

Genuinely generic traversal, with no knowledge of what is being looked for.
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
    Only folders inside project_path are listed, compared by component, so a spec outside the
    project gets [project_path] only.
    """
    project_resolved = project_path.resolve()

    if spec_path is None:
        return [project_resolved]

    directories: list[Path] = []
    current = spec_path.resolve().parent

    while current.is_relative_to(project_resolved):
        directories.append(current)
        if current == project_resolved:
            break
        current = current.parent

    # Ensure project_path is always in the list
    if project_resolved not in directories:
        directories.append(project_resolved)

    return directories
