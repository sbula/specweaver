# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Project path discovery.

Resolution priority:
1. Explicit --project flag
2. SW_PROJECT environment variable
3. Current working directory
"""

from __future__ import annotations

import os
from pathlib import Path


def resolve_project_path(
    project_arg: str | None = None,
    *,
    cwd: Path | None = None,
) -> Path:
    """Resolve the target project directory.

    Args:
        project_arg: Value from the --project CLI flag, or None.
        cwd: Override for current working directory (used in tests
            when the path might be relative).

    Returns:
        Absolute, resolved Path to the project directory.

    Raises:
        FileNotFoundError: If the resolved path does not exist.
        NotADirectoryError: If the resolved path is a file, not a directory.
    """
    if project_arg is not None:
        raw_path = project_arg
    elif "SW_PROJECT" in os.environ:
        raw_path = os.environ["SW_PROJECT"]
    else:
        # Default to current working directory
        return (cwd or Path.cwd()).resolve()

    # Resolve relative to cwd if provided, otherwise absolute
    path = Path(raw_path)
    if not path.is_absolute() and cwd is not None:
        path = cwd / path

    resolved = path.resolve()

    if not resolved.exists():
        msg = f"Project path does not exist: {resolved}"
        raise FileNotFoundError(msg)

    if not resolved.is_dir():
        msg = f"Project path is not a directory: {resolved}"
        raise NotADirectoryError(msg)

    return resolved
