#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Read an INT story's integration doc to find which capabilities it integrates.

Split out of `scripts/tests.py` (2026-08-08), which had no headroom left under the file-size
ceiling. The seam is real rather than convenient: this is markdown archaeology over
`docs/roadmap/topics/topic_08_integration/`, while `tests.py` selects and runs pytest tiers. The
sibling `_refactor_diff_safety.py` was split off the same file for the same reason.

The scoping in `integration_scope_text` is the whole correctness of the DAL derivation — read its
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


BASE_SECTION = "## Base Story Contract"
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


def integration_scope_text(story_id: str, doc_text: str) -> str:
    """The passage naming what THIS story integrates — nothing more.

    Scoping this precisely is the whole correctness of the DAL derivation. Scanning the entire
    document reads `INT-US-09` as DAL-A, because its **Sub-Story Add-Ons** section mentions
    `A-EXEC-01` and `A-EXEC-03` — capabilities those add-ons are BLOCKED ON, which the base
    contract does not integrate and which are not built. A base INT story integrates the
    Core-Required MVS capabilities named in its Integration Description; `INT-US-NN-SFxx` add-ons
    are separate stories with separate scope, and pulling theirs into the base over-escalates
    every gate for work that has not happened.
    """
    lines = doc_text.splitlines()
    upper = story_id.upper()

    if "-SF" in upper:
        # Only the bullet that DEFINES the add-on, and only inside the add-ons section. The base
        # contract's Status bullet also mentions sub-story IDs in passing ("container add-on =
        # `INT-US-09-SF01`"), and matching that reads the wrong scope entirely.
        section_start = next(
            (i for i, line in enumerate(lines) if line.startswith(SUBSTORY_SECTION)), None
        )
        if section_start is None:
            raise UsageError(f"{story_id}: integration doc has no '{SUBSTORY_SECTION}' section")
        defines = re.compile(r"^\*\s+\*\*[`'\"]?" + re.escape(upper), re.I)
        for i in range(section_start, len(lines)):
            if defines.match(lines[i]):
                return _bullet_at(lines, i)
        raise UsageError(
            f"{story_id}: no defining bullet under '{SUBSTORY_SECTION}' in the integration doc"
        )

    start = next((i for i, line in enumerate(lines) if line.startswith(BASE_SECTION)), None)
    end = next((i for i, line in enumerate(lines) if line.startswith(SUBSTORY_SECTION)), len(lines))
    if start is None:
        raise UsageError(f"{story_id}: integration doc has no '{BASE_SECTION}' section")

    for i in range(start, end):
        if INTEGRATION_DESCRIPTION in lines[i]:
            return _bullet_at(lines, i)
    raise UsageError(f"{story_id}: no '{INTEGRATION_DESCRIPTION}' bullet in the base contract")


def integrated_capabilities(story_id: str) -> list[str]:
    """Capability IDs an INT story integrates, read from its integration doc."""
    base_id = re.sub(r"-SF\d+$", "", story_id.upper())
    number = base_id.removeprefix("INT-US-")
    doc = (
        REPO_ROOT
        / "docs"
        / "roadmap"
        / "topics"
        / "topic_08_integration"
        / f"US-{number}_integration.md"
    )
    if not doc.is_file():
        raise UsageError(
            f"no integration doc for {story_id} at {doc.relative_to(REPO_ROOT).as_posix()} — "
            "cannot derive DAL; pass --dal explicitly"
        )
    scope_text = integration_scope_text(story_id, doc.read_text(encoding="utf-8", errors="replace"))
    return sorted({m.group(0) for m in CAPABILITY_ID.finditer(scope_text)})
