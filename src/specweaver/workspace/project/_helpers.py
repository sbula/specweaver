# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Constitution internal helpers — walk-up, loading, standards building."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

CONSTITUTION_FILENAME = "CONSTITUTION.md"
DEFAULT_MAX_CONSTITUTION_SIZE = 5120  # 5 KB


@dataclass(frozen=True)
class ConstitutionInfo:
    """Result of loading a constitution.

    Attributes:
        content: Raw markdown content (BOM-stripped).
        path: Absolute path to the file.
        size: File size in bytes.
        is_override: True if this is not the root-level constitution
            (i.e. found in a subdirectory, overriding the root).
    """

    content: str
    path: Path
    size: int
    is_override: bool


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


def load_constitution(
    path: Path,
    *,
    is_override: bool,
    max_size: int = DEFAULT_MAX_CONSTITUTION_SIZE,
) -> ConstitutionInfo:
    """Load a constitution file with BOM stripping and size warning."""
    raw = path.read_text(encoding="utf-8-sig")  # auto-strips BOM

    # Strip BOM if present
    if raw.startswith("\ufeff"):
        raw = raw[1:]

    size = path.stat().st_size

    if size > max_size:
        logger.warning(
            "Constitution %s size (%d bytes) exceeds recommended limit "
            "(%d bytes). Consider trimming.",
            path,
            size,
            max_size,
        )

    return ConstitutionInfo(
        content=raw,
        path=path,
        size=size,
        is_override=is_override,
    )


def build_tech_stack_rows(languages: list[str]) -> str:
    """Build markdown table rows for the Tech Stack section."""
    if not languages:
        return "| Language | TODO | TODO | TODO |"

    lang_info = {
        "python": ("Python", "3.11+", "Primary language"),
        "javascript": ("JavaScript", "ES2022+", "Frontend / Node.js"),
        "typescript": ("TypeScript", "5.x+", "Type-safe JavaScript"),
    }

    rows: list[str] = []
    for lang in languages:
        info = lang_info.get(lang.lower(), (lang.capitalize(), "TODO", "TODO"))
        rows.append(f"| Language | {info[0]} | {info[1]} | {info[2]} |")

    return "\n".join(rows)


def build_standards_section(standards: list[dict[str, Any]]) -> str:
    """Build markdown bullet list from confirmed standards."""
    import json

    if not standards:
        return (
            "- TODO: Naming conventions\n"
            "- TODO: Error handling patterns\n"
            "- TODO: Documentation requirements"
        )

    lines: list[str] = []
    # Group by category
    by_category: dict[str, list[dict[str, Any]]] = {}
    for s in standards:
        cat = s.get("category", "unknown")
        by_category.setdefault(cat, []).append(s)

    category_labels = {
        "naming": "Naming Conventions",
        "error_handling": "Error Handling",
        "type_hints": "Type Annotations",
        "docstrings": "Documentation Style",
        "import_patterns": "Import Organization",
        "test_patterns": "Testing Conventions",
        "async_patterns": "Async Patterns",
        "jsdoc": "JSDoc Documentation",
        "tsdoc": "TSDoc Documentation",
    }

    for category, items in sorted(by_category.items()):
        label = category_labels.get(category, category.replace("_", " ").title())
        lines.append(f"### {label}")
        lines.append("")
        for item in items:
            data = json.loads(item["data"]) if isinstance(item["data"], str) else item["data"]
            scope = item.get("scope", ".")
            lang = item.get("language", "unknown")
            conf = item.get("confidence", 0.0)
            prefix = f"[{scope}/{lang}]" if scope != "." else f"[{lang}]"
            lines.append(f"**{prefix}** (confidence: {conf:.0%})")
            for k, v in data.items():
                lines.append(f"- {k.replace('_', ' ').title()}: `{v}`")
            lines.append("")

    return "\n".join(lines).rstrip()
