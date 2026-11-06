# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reads a project root for the one profile decision (`commons.project_profile`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.commons.project_profile import ProjectProfile, decide_profile

if TYPE_CHECKING:
    from pathlib import Path


def read_project_profile(
    root: Path, *, language: str | None = None, build_tool: str | None = None
) -> ProjectProfile:
    """The language and build tool of the project at `root`, with the `[implement]` pins.

    Lists the root once; only its regular files count. A file whose real path leaves the root
    reads as nothing. Raises `ProjectUndecidedError` when the root does not decide.
    """
    real_root = root.resolve()
    names = frozenset(entry.name for entry in root.iterdir() if entry.is_file())

    def read(name: str) -> str | None:
        path = (root / name).resolve()
        if not path.is_relative_to(real_root):
            return None
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):  # expected: unreadable, so its name alone decides
            return None

    return decide_profile(
        names,
        read,
        kotlin_sources=(root / "src" / "main" / "kotlin").is_dir(),
        language=language,
        build_tool=build_tool,
    )
