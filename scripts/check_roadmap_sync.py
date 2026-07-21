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

Exit code 1 on any ERROR (blocks pre-commit Phase 5). Warnings do not block.

Usage: python scripts/check_roadmap_sync.py [roadmap_md] [matrix_md]
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROADMAP = Path("docs/roadmap/master_story_roadmap.md")
MATRIX = Path("docs/roadmap/capability_matrix.md")

CAP_ID = r"[A-E]-(?:UI|SENS|FLOW|INTL|VAL|EXEC)-\d+"
UNCHECKED_CAP = re.compile(rf"`\[ \]` \*\*({CAP_ID}):")
CHECKED_CAP = re.compile(rf"`✅` \*\*({CAP_ID}):")
UNCHECKED_CORE = re.compile(r"`\[ \]` \*\*(US-\d+) Core\*\*")
GREEN_HEADER = re.compile(r"### \U0001f7e2 (US-\d+):")


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
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
