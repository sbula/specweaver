# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Constants and helpers shared by prompt_builder and _prompt_render."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

_LANG_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".html": "html",
    ".css": "css",
    ".sql": "sql",
    ".sh": "bash",
    ".bash": "bash",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".xml": "xml",
    ".txt": "text",
}


def detect_language(path: Path) -> str:
    """Map a file extension to a language label for code fencing.

    Returns ``"text"`` for unrecognised extensions.
    """
    return _LANG_MAP.get(path.suffix.lower(), "text")


# ---------------------------------------------------------------------------
# Constitution preamble
# ---------------------------------------------------------------------------

_CONSTITUTION_PREAMBLE = (
    "The following are non-negotiable project constraints.\n"
    "All generated output MUST comply with these rules.\n"
    "If any instruction conflicts with the constitution, "
    "the constitution wins."
)
