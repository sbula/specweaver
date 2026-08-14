#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Check roadmap dependency checkboxes against the capability registry.

The registry (capability_matrix.md + green story headers in the master roadmap) is
the source of truth for delivery status. Dependent stories reference capabilities
via checkbox lines; those references drift (2026-07-21: a sweep found 14 stale
boxes, e.g. `[ ]` B-VAL-02 although the Spec Rot Interceptor runs on every commit).

Checks:
  - ERROR  (stale-unchecked): a `[ ]` dep box whose capability is ✅ in the matrix,
           or whose `US-N Core` story header is 🟢 in the roadmap.
  - WARNING (over-checked): a `✅` capability dep box NOT ✅ in the matrix — a
           possible over-claim; verify against the Proof Mandate.
  - ERROR  (orphaned entry): an entry in a topic document with no entry in the master
           roadmap — the two registries disagree about what EXISTS, not merely about
           status. Delegated to `_registry_orphans.py`, which is ratcheted; see
           its docstring for why 10 are frozen. Added by `ADR-003` after a sweep removed
           63 roadmap lines and 20 of those ids still had real topic entries, with the
           whole doc gate green throughout.

Exit code 1 on any ERROR (blocks pre-commit Phase 5). Warnings do not block.

Usage: python scripts/check_roadmap_sync.py [roadmap_md] [matrix_md]
"""

from __future__ import annotations

import importlib.util
import io
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

ROADMAP = Path("docs/roadmap/master_story_roadmap.md")
MATRIX = Path("docs/roadmap/capability_matrix.md")
TOPIC_TECH = Path("docs/roadmap/topics/topic_07_technical_debt.md")

CAP_ID = r"[A-E]-(?:UI|SENS|FLOW|INTL|VAL|EXEC)-\d+"
UNCHECKED_CAP = re.compile(rf"`\[ \]` \*\*({CAP_ID}):")
CHECKED_CAP = re.compile(rf"`✅` \*\*({CAP_ID}):")
UNCHECKED_CORE = re.compile(r"`\[ \]` \*\*(US-\d+) Core\*\*")
GREEN_HEADER = re.compile(r"### \U0001f7e2 (US-\d+):")
#: A TECH ticket's status lives in three places with three spellings: `🟢` in the topic doc, `✅` in
#: the roadmap checkbox list, prose in the routing table. `TECH-017` stayed `[ ]` here after closing
#: because a sweep for `🔴` cannot see a `[ ]` two hundred lines away.
GREEN_TECH = re.compile(r"\*\*`(TECH-\d+)` \U0001f7e2")
UNCHECKED_TECH = re.compile(r"`\[ \]` \*\*(TECH-\d+):")


_orphan_spec = importlib.util.spec_from_file_location(
    "_registry_orphans", Path(__file__).parent / "_registry_orphans.py"
)
assert _orphan_spec is not None and _orphan_spec.loader is not None
_orphans = importlib.util.module_from_spec(_orphan_spec)
sys.modules["_registry_orphans"] = _orphans
_orphan_spec.loader.exec_module(_orphans)


def stale_tech_tickets(road: str, topic: str) -> list[str]:
    """TECH ids closed (`🟢`) in the topic doc but still unticked (`[ ]`) in the roadmap.

    The capability half of this check has existed for months; TECH tickets simply had no
    equivalent, which is why three stale markers were found by hand in two days. A ticket absent
    from the roadmap entirely is NOT reported here — that is existence drift and belongs to
    `_registry_orphans`. One checker, one question.
    """
    green = set(GREEN_TECH.findall(topic))
    return [t for t in UNCHECKED_TECH.findall(road) if t in green]


def _stale_tech_errors(road: str, line_of: Callable[[int], int]) -> list[str]:
    """Report every TECH id closed in the topic doc but still unticked in the roadmap."""
    topic_text = TOPIC_TECH.read_text(encoding="utf-8") if TOPIC_TECH.is_file() else ""
    stale = set(stale_tech_tickets(road, topic_text))
    return [
        f"  STALE:      line {line_of(m.start())}: `[ ]` {m.group(1)} — ticket is CLOSED "
        "(\U0001f7e2) in topic_07_technical_debt.md"
        for m in UNCHECKED_TECH.finditer(road)
        if m.group(1) in stale
    ]


def main(argv: list[str]) -> int:
    # ASCII/UTF-8 safe output on Windows cp1252 consoles.
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    roadmap_path = Path(argv[1]) if len(argv) > 1 else ROADMAP
    matrix_path = Path(argv[2]) if len(argv) > 2 else MATRIX
    road = roadmap_path.read_text(encoding="utf-8")
    matrix = matrix_path.read_text(encoding="utf-8")

    def line_of(pos: int) -> int:
        return road[:pos].count("\n") + 1

    done_in_matrix = set(re.findall(rf"✅ ({CAP_ID})`", matrix))
    closed_stories = set(GREEN_HEADER.findall(road))

    errors: list[str] = []
    warnings: list[str] = []

    for m in UNCHECKED_CAP.finditer(road):
        if m.group(1) in done_in_matrix:
            errors.append(
                f"  STALE:      line {line_of(m.start())}: `[ ]` {m.group(1)} — capability is DONE in the matrix"
            )
    for m in UNCHECKED_CORE.finditer(road):
        if m.group(1) in closed_stories:
            errors.append(
                f"  STALE:      line {line_of(m.start())}: `[ ]` {m.group(1)} Core — story is CLOSED (green header)"
            )
    errors.extend(_stale_tech_errors(road, line_of))

    for m in CHECKED_CAP.finditer(road):
        if m.group(1) not in done_in_matrix:
            warnings.append(
                f"  OVERCLAIM?: line {line_of(m.start())}: `✅` {m.group(1)} — NOT marked done in the matrix"
            )

    for msg in errors + warnings:
        print(msg)
    if errors or warnings:
        print(f"\nRoadmap sync check: {len(errors)} error(s), {len(warnings)} warning(s)")
    else:
        print("Roadmap sync check: dependency boxes fully in sync with the registry")

    # `ADR-003`: status agreement is not existence agreement. Runs even when the box checks fail,
    # so one kind of drift never hides the other.
    orphan_status = _orphans.main([])
    return 1 if (errors or orphan_status) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
