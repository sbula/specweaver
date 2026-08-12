#!/usr/bin/env python
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Placement rules for `master_story_roadmap.md` — one walk, three rules.

The master roadmap is an overview. What belongs in it was never written down, so every agent
derived the convention from whatever it happened to grep — and Topic 07 is where it grepped, where
the convention was broken in four of twenty-four entries. Precedent in the artifact beat the rule
because the rule existed nowhere.

Three rules, applied to different line classes in a single pass:

R-PLACE  A list item at the entry's nesting depth must name a **bold registry ID**. A design
         document's `SF-NN` decomposition has no registry ID and so cannot appear.
R-LENGTH A line inside an entry is at most `MAX_ENTRY_LINE` characters. Detail lives in the topic
         doc and the design; this file carries names and prerequisites.
R-OWNER  A bare `SF-NN` in prose must have its owning story named — adjacently, or by the entry it
         sits in. `SF-01` exists in six stories, so outside its own folder it names nothing.

**Structural, not lexical, and that distinction is the whole design.** An earlier attempt at
R-PLACE tried to tell legal text from illegal text — `INT-US-NN-SFxx` good, bare `SF-NN` bad — and
flagged fifteen ordinary sentences while ignoring the ~89 capability lines at the same depth.
Asking instead *what kind of line is this* separates 168 legal items from exactly the illegal ones
with no allowlist. R-OWNER exists at all only because that split leaves the prose plane free.

Usage: python scripts/check_roadmap_placement.py [roadmap_md]
Exit 0 when clean, 1 on any violation.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROADMAP = Path("docs/roadmap/master_story_roadmap.md")

#: Lines inside an entry may not exceed this. Chosen from the file's own distribution (median
#: 58-96, p90 ~190), so the rule ratifies existing practice instead of imposing a new one — the
#: same reasoning that set the two-digit sub-feature format.
MAX_ENTRY_LINE = 200

#: A registry ID: `US-9`, `TECH-025`, `C-FLOW-02`, `INT-US-21-SF02`.
STORY_ID = r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+(?:-SF\d+)?"

#: An entry heading — `### 🟢 US-9: …`, `### 🔴 TECH-030: …`.
ENTRY_HEADING = re.compile(rf"^###\s+\S*\s*({STORY_ID}):")
#: Any `###`, entry or not (Debt Sequencing, Routing Matrix, the TECH grouping).
ANY_HEADING = re.compile(r"^###\s")

#: A list item nested under a registry line — the depth a design's `SF-NN` would land at.
NESTED_ITEM = re.compile(r"^ {8,}\*\s")
#: …which is legal exactly when it names a bold registry ID.
BOLD_ID = re.compile(rf"\*\*{STORY_ID}:\*\*")

#: A sub-feature reference.
BARE_SF = re.compile(r"(?<![\w-])SF-\d+")
#: Any registry id appearing on the line. Its presence is what makes an `SF-NN` on that line
#: owned — including `INT-US-04-SF05`, whose own section heading is legitimately written `SF-05`
#: in the link beside it.
#:
#: Line-scoped rather than clause-scoped, deliberately. Requiring the id *adjacent* to every
#: reference was measured against the real file and reported correct references as violations four
#: separate times, each time for a different reason. A checker that cries wolf gets disabled, and
#: takes the rule it protects with it.
ID_ON_LINE = re.compile(STORY_ID)


def _violations(text: str) -> list[str]:
    out: list[str] = []
    entry: str | None = None

    for number, line in enumerate(text.split("\n"), 1):
        if ANY_HEADING.match(line):
            match = ENTRY_HEADING.match(line)
            entry = match.group(1) if match else None
            continue
        if entry is None:
            continue

        if NESTED_ITEM.match(line) and not BOLD_ID.search(line):
            out.append(
                f"{number}: R-PLACE  nested item names no registry ID — a design's SF-NN "
                f"decomposition belongs in its own design, not here: {line.strip()[:70]}"
            )

        if len(line) > MAX_ENTRY_LINE:
            out.append(
                f"{number}: R-LENGTH line is {len(line)} chars (max {MAX_ENTRY_LINE}) — the "
                f"detail belongs in the topic doc: {line.strip()[:60]}"
            )

        if BARE_SF.search(line) and not ID_ON_LINE.search(line) and entry not in line:
            out.append(
                f"{number}: R-OWNER  bare SF reference with no owner named — `SF-01` exists in "
                f"six stories: {line.strip()[:70]}"
            )

    return out


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else ROADMAP

    print("Roadmap placement check")
    if not path.is_file():
        print(f"FAIL  roadmap not found: {path}")
        return 1

    found = _violations(path.read_text(encoding="utf-8"))
    if not found:
        print("  placement, line length and sub-feature ownership all clean")
        return 0

    for line in found:
        print(f"  {line}")
    print(f"\nFAIL  {len(found)} placement violation(s) in {path}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
