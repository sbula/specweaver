#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Before shortening a topic entry, name the facts that would be lost. `TECH-017`.

`R-DEPTH` says an over-long registry line is content at the wrong depth, and the remedy is to move
it down rather than delete it. This is the tool that makes "move" verifiable instead of hopeful:
for each topic-doc entry it lists the distinctive facts present there and **absent from the linked
design doc**. Anything printed must be moved first; anything not printed already lives at design
depth and the entry can be trimmed with nothing lost.

Measured on first run (2026-08-13): 39 over-long entries in `topic_07`, and **62 facts a naive trim
would have dropped** — among them `engine/runner.py:404-406`, `handlers/decompose.py:238-241`,
`GraphBuildAtom` and `status=running / result=None`. So the risk this guards against is real, not
hypothetical; trimming by eye would have lost them.

It is an ADVISORY tool, not a gate. Its notion of a "fact" is a heuristic — backticked spans, dotted
filenames, line references, short numbers — which over-reports (a bare year reads as a fact) and can
under-report a claim made only in prose. A gate built on that would be argued with rather than
obeyed; a checklist you run before editing is honest about what it is.

Usage:
    python scripts/check_entry_orphans.py                 # every over-long entry
    python scripts/check_entry_orphans.py TECH-035        # one ticket
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOPICS = REPO_ROOT / "docs" / "roadmap" / "topics"
FEATURES = REPO_ROOT / "docs" / "roadmap" / "features"

#: Only entries past this are worth checking — a short entry has nothing to redistribute.
MIN_ENTRY = 250

#: What counts as a distinctive fact: a backticked span, a dotted filename with optional line
#: reference, or a bare 2-5 digit number (counts and measurements are the easiest thing to lose).
_FACT = re.compile(
    r"`([^`]{3,80})`|\b([a-z_][\w/]*\.(?:py|md|yaml|toml)(?::[\d\-]+)?)\b|\b(\d{2,5})\b"
)

#: Entry lines look like `> [Description](../features/<topic>/<ID>/<ID>_design.md) | ...`.
_ENTRY = re.compile(
    r"^\s*> \[Description\]\((\.\./features/[^)]*?/([A-Z][\w-]*-\d+)/[^)]*)\).*$", re.M
)


def facts(text: str) -> set[str]:
    found = set()
    for match in _FACT.finditer(text):
        value = next(g for g in match.groups() if g).strip()
        if len(value) >= 2:
            found.add(value)
    return found


def orphans(entry: str, design: str) -> list[str]:
    """Facts in the entry that do not appear anywhere in the design doc."""
    return sorted(f for f in facts(entry) if f not in design)


def scan(only: str | None = None) -> list[tuple[str, str, int, list[str]]]:
    out: list[tuple[str, str, int, list[str]]] = []
    for topic in sorted(TOPICS.glob("topic_*.md")):
        text = topic.read_text(encoding="utf-8", errors="replace")
        for match in _ENTRY.finditer(text):
            entry, rel, ticket = match.group(0), match.group(1), match.group(2)
            if only and ticket != only:
                continue
            if len(entry) <= MIN_ENTRY and not only:
                continue
            design_path = (topic.parent / rel).resolve()
            design = (
                design_path.read_text(encoding="utf-8", errors="replace")
                if design_path.is_file()
                else ""
            )
            out.append((topic.name, ticket, len(entry), orphans(entry, design)))
    return sorted(out, key=lambda row: -row[2])


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    only = args[0].upper() if args else None

    rows = scan(only)
    if not rows:
        print(f"no entry found for {only}" if only else "no over-long entries")
        return 0

    total = 0
    for topic, ticket, size, missing in rows:
        total += len(missing)
        verdict = "SAFE TO TRIM" if not missing else f"MOVE {len(missing)} FACT(S) FIRST"
        print(f"{ticket}  ({topic}, entry {size} chars) — {verdict}")
        for fact in missing:
            print(f"    - {fact}")

    print(
        f"\n{len(rows)} entr(y/ies) checked; {total} fact(s) present in a topic entry and absent "
        "from its design. Move those into the design doc BEFORE shortening the entry — R-DEPTH's "
        "remedy is redistribution, never deletion."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
