# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A path from outside, resolved inside the project or refused.

The API may not import `sandbox`, so it reaches `WorkspaceBoundary` through this function.
"""

from __future__ import annotations

from pathlib import Path

from specweaver.sandbox.security import WorkspaceBoundary


class ProjectPathError(ValueError):
    """A path leaves the project. The message names the path as given, never as resolved."""


def project_file(project_root: Path, relative: str) -> Path:
    """Resolve `relative` against the project root; links are followed before the check."""
    boundary = WorkspaceBoundary([project_root])
    # `Path("")` is `.`, which is inside: a blank path must be refused here.
    if not relative.strip() or not boundary.contains(Path(relative)):
        raise ProjectPathError(f"Path is outside the project: '{relative}'")
    return boundary.validate_path(Path(relative))
