# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Standards content loader for prompt injection.

Extracted from ``cli/_helpers.py`` so that both the CLI and the REST API
can load standards content without depending on Typer/Rich.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.config.database import Database

logger = logging.getLogger(__name__)


def load_standards_content(
    db: Database,
    project_name: str,
    project_path: Path,
    target_path: Path | None = None,
    *,
    max_chars: int = 2000,
) -> str | None:
    """Load formatted standards from DB for prompt injection.

    When *target_path* is provided, resolves which scope the file belongs
    to and loads scope-specific + root (``"."``) standards.  Applies a
    ``max_chars`` cap, prioritising scope-specific over root.

    Args:
        db: Database instance.
        project_name: Name of the active project.
        project_path: Absolute path to the project root.
        target_path: Path to the spec/code file being reviewed/generated.
            If ``None``, all standards are loaded (backward-compatible).
        max_chars: Maximum output length in characters.

    Returns:
        Formatted standards text for prompt injection, or ``None``
        if no standards exist.
    """
    from specweaver.standards.scope_detector import _resolve_scope

    logger.debug(
        "load_standards_content: project=%s, target=%s, max_chars=%d",
        project_name,
        target_path,
        max_chars,
    )
    if target_path is not None:
        known_scopes = db.list_scopes(project_name)
        scope = _resolve_scope(target_path, project_path, known_scopes)
        # Load scope-specific standards
        scope_standards = db.get_standards(project_name, scope=scope)
        # Load root cross-cutting standards (if scope != ".")
        root_standards = db.get_standards(project_name, scope=".") if scope != "." else []
    else:
        scope_standards = db.get_standards(project_name)
        root_standards = []

    all_standards = scope_standards + root_standards
    if not all_standards:
        return None

    lines: list[str] = [
        "The following coding standards were auto-discovered from this project.",
        "Generated code SHOULD follow these conventions.\n",
    ]

    def _format_standard(s: dict[str, object]) -> list[str]:
        data: dict[str, object] = (
            json.loads(s["data"])
            if isinstance(s["data"], str)
            else cast("dict[str, object]", s["data"])
        )
        conf = s["confidence"]
        result = [f"[{s['scope']}/{s['language']}/{s['category']}] (confidence={conf:.0%})"]
        for k, v in data.items():
            result.append(f"  {k}: {v}")
        return result

    # Scope-specific first (higher priority for cap)
    for s in scope_standards:
        lines.extend(_format_standard(s))

    # Root standards second
    for s in root_standards:
        lines.extend(_format_standard(s))

    text = "\n".join(lines)

    # Apply token cap — truncate from the end (root standards trimmed first)
    if len(text) > max_chars:
        text = text[: max_chars - 15] + "\n[... truncated]"

    return text
