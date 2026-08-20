#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Read a (sub)story's path document to find which capabilities it spans.

Split out of `scripts/tests.py` (2026-08-08), which had no headroom left under the file-size
ceiling. The seam is real rather than convenient: this is markdown archaeology over
`docs/roadmap/stories/`, while `tests.py` selects and runs pytest tiers. The
sibling `_refactor_diff_safety.py` was split off the same file for the same reason.

The scoping in `story_scope_text` is the whole correctness of the DAL derivation — read its
docstring before touching it.

`UsageError` is defined HERE and re-exported by `tests.py`, not declared in both. Two classes of
the same name are two different exceptions, and the caller's `except UsageError` would miss one.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

CAPABILITY_ID = re.compile(r"\b([A-E])-(UI|SENS|FLOW|INTL|VAL|EXEC)-\d{2}\b")


class UsageError(Exception):
    """The caller asked for something the matrix cannot answer."""


BASE_SECTION = "## Base Story"
SUBSTORY_SECTION = "## Sub-Story Add-Ons"
INTEGRATION_DESCRIPTION = "**Integration Description:**"


def _bullet_at(lines: list[str], start: int) -> str:
    """One markdown bullet, including any continuation lines beneath it."""
    collected = [lines[start]]
    for line in lines[start + 1 :]:
        if line.lstrip().startswith(("* ", "## ", "# ")):
            break
        collected.append(line)
    return "\n".join(collected)


def story_scope_text(story_id: str, doc_text: str) -> str:
    """The passage naming what THIS story spans — nothing more.

    Scoping this precisely is the whole correctness of the DAL derivation. Scanning the entire
    document reads `US-09` as DAL-A, because its **Sub-Story Add-Ons** section mentions `A-EXEC-01`
    — a capability its add-on is BLOCKED ON, which the base story does not span and which is not
    built. A base story spans the Core-Required MVS capabilities named in its
    Integration Description; an add-on group is separate scope, and pulling its capabilities into
    the base over-escalates every gate for work that has not happened.

    `ADR-005` removed the add-on's own identifier, so an add-on is no longer addressable here. Run
    its work under the capability it ships (`tests.py cb C-FLOW-12`), which carries its own DAL in
    its prefix and needs no document to derive it.
    """
    lines = doc_text.splitlines()

    start = next((i for i, line in enumerate(lines) if line.startswith(BASE_SECTION)), None)
    end = next((i for i, line in enumerate(lines) if line.startswith(SUBSTORY_SECTION)), len(lines))
    if start is None:
        raise UsageError(f"{story_id}: path document has no '{BASE_SECTION}' section")

    for i in range(start, end):
        if INTEGRATION_DESCRIPTION in lines[i]:
            return _bullet_at(lines, i)
    raise UsageError(f"{story_id}: no '{INTEGRATION_DESCRIPTION}' bullet in the base story")


def spanned_capabilities(story_id: str) -> list[str]:
    """Capability IDs a (sub)story spans, read from its path document."""
    number = f"{int(story_id.upper().removeprefix('US-')):02d}"
    doc = REPO_ROOT / "docs" / "roadmap" / "stories" / f"US-{number}.md"
    if not doc.is_file():
        raise UsageError(
            f"no path document for {story_id} at {doc.relative_to(REPO_ROOT).as_posix()} — "
            "cannot derive DAL; pass --dal explicitly"
        )
    scope_text = story_scope_text(story_id, doc.read_text(encoding="utf-8", errors="replace"))
    return sorted({m.group(0) for m in CAPABILITY_ID.finditer(scope_text)})
