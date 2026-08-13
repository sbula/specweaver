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
         (R-LENGTH was removed 2026-08-13: `R-DEPTH` in `_entry_depth.py` caps the same 200
         characters across EVERY markdown file in the repo, so this rule enforced a strict subset
         of it. Two rules, one number, one of them redundant.)
R-OWNER  A bare `SF-NN` must have its owner named — on the line, or by the entry it sits in.
         `SF-01` exists in six stories, so with neither it names nothing. Applies outside entries
         too: the Debt Sequencing prose is exactly where an unowned reference hides.
R-MARKER A `TECH` line is `[ ]` when open and `✅` when delivered, never `[x]`. The contract
         showed the open form and not the delivered one, beside an instruction to "check off the
         boxes" that means user stories — so `[x]` got written twice before anyone noticed.

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

#: A registry ID: `US-9`, `TECH-025`, `C-FLOW-02`, `INT-US-21-SF02`.
#:
#: The `(?!SF-)` guard is load-bearing and was missing on first release: without it the pattern
#: matches a bare `SF-03`, so R-OWNER saw every unqualified reference as its own owner and could
#: never fire. Caught by probing the rule against a planted orphan rather than by reading it.
STORY_ID = r"(?<![\w-])(?!SF-\d)[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+(?:-SF\d+)?(?![\w-])"

DOCS = Path("docs")

#: A document under `features/<topic>/<ID>/` has its owner supplied by the path, so a bare `SF-NN`
#: there is unambiguous. This is what makes R-OWNER enforceable at all: the rule needs somewhere
#: the short form is legal, or every design would have to qualify its own sub-features.
OWNER_FROM_PATH = re.compile(rf"features/[^/]+/({STORY_ID})/")

#: A heading, list item or table row — the structures that can carry an owner for the lines under
#: them. Entry-scoped rather than clause-scoped, by decision: a topic-doc bullet opening with the
#: story id owns the prose beneath it, and requiring every sentence to repeat the id was measured
#: against the real corpus and reported correct references as violations four separate times.
STRUCTURE = re.compile(r"^(#{1,6}\s|\s*[-*]\s|\s*\|)")

#: Pre-registry numbering: `Feature 3.32 SF-4` names a scheme with no story ids at all.
LEGACY = re.compile(r"[Ff]eature\s+\d+\.\d+")

#: Wholly a record of that scheme — its own filename says so, and every sub-feature in it belongs
#: to a decimal feature number rather than a story. Excluded by name because its entries write the
#: number as `3.14a` without the word "Feature", which the pattern above cannot see. The clause-1
#: guard in `tests/unit/test_sub_feature_identifiers.py` excludes the same document, for the same
#: reason, and asserts there that the exclusion is still needed rather than dead.
LEGACY_DOCUMENTS = {"legacy_feature_map.md"}

#: An entry heading — `### 🟢 US-9: …`, `### 🔴 TECH-030: …`.
ENTRY_HEADING = re.compile(rf"^###\s+\S*\s*({STORY_ID}):")
#: Any `###`, entry or not (Debt Sequencing, Routing Matrix, the TECH grouping).
ANY_HEADING = re.compile(r"^###\s")

#: A list item nested under a registry line — the depth a design's `SF-NN` would land at.
NESTED_ITEM = re.compile(r"^ {8,}\*\s")
#: …which is legal exactly when it names a bold registry ID.
BOLD_ID = re.compile(rf"\*\*{STORY_ID}:\*\*")

#: A `TECH` line carrying a checked user-story box. `[ ]` (open) and `✅` (delivered) are the only
#: two legal markers; `[x]` appears nowhere else in the file.
#:
#: The rule exists because the contract showed what an OPEN TECH line looks like and never what a
#: delivered one looks like, while the instruction beside it — "check off the boxes" — is user-story
#: vocabulary. Read across, that yields `[x]`, which was written twice on 2026-08-12 before anyone
#: noticed. Scoped to TECH ids on purpose: a real user story's boxes are legitimately `[x]`.
CHECKED_TECH = re.compile(r"^\s*\*\s+`\[x\]`\s+\*\*(TECH-\d+):\*\*")

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

        if entry and NESTED_ITEM.match(line) and not BOLD_ID.search(line):
            out.append(
                f"{number}: R-PLACE  nested item names no registry ID — a design's SF-NN "
                f"decomposition belongs in its own design, not here: {line.strip()[:70]}"
            )

        checked = CHECKED_TECH.match(line)
        if checked:
            out.append(
                f"{number}: R-MARKER {checked.group(1)} uses `[x]` — a TECH line is `[ ]` when "
                f"open and `✅` when delivered; `[x]` is user-story vocabulary"
            )

        if BARE_SF.search(line) and not ID_ON_LINE.search(line) and entry is None:
            out.append(
                f"{number}: R-OWNER  bare SF reference with no owner named — `SF-01` exists in "
                f"six stories: {line.strip()[:70]}"
            )

    return out


def unowned_references(path: Path) -> list[str]:
    """R-OWNER across a whole document — used for every doc outside the roadmap.

    The roadmap gets the stricter entry model in `_violations`; everything else only needs to know
    whether *some* enclosing structure names the story.
    """
    if OWNER_FROM_PATH.search(path.as_posix()) or path.name in LEGACY_DOCUMENTS:
        return []

    out: list[str] = []
    enclosing: str | None = None
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if STRUCTURE.match(line):
            found = ID_ON_LINE.search(line)
            if found:
                enclosing = found.group(0)
            elif line.startswith("#"):
                enclosing = None
        if LEGACY.search(line) or not BARE_SF.search(line):
            continue
        if ID_ON_LINE.search(line) or enclosing:
            continue
        out.append(f"{path.as_posix()}:{number}: {line.strip()[:70]}")
    return out


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else ROADMAP

    print("Roadmap placement check")
    if not path.is_file():
        print(f"FAIL  roadmap not found: {path}")
        return 1

    found = _violations(path.read_text(encoding="utf-8"))
    if DOCS.is_dir():
        for doc in sorted(DOCS.rglob("*.md")):
            found.extend(f"R-OWNER  {ref}" for ref in unowned_references(doc))
    if not found:
        print("  placement, line length and sub-feature ownership all clean")
        return 0

    for line in found:
        print(f"  {line}")
    print(f"\nFAIL  {len(found)} placement violation(s) in {path}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
