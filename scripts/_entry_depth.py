#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""R-DEPTH: a registry line that runs long is content sitting at the wrong depth. `TECH-017`.

`R-LENGTH` caps `master_story_roadmap.md` entries at 200 characters and works — 1.6% of that file
exceeds it, the longest is 363. Its stated rationale was *"detail lives in the topic doc and the
design"*, and **nothing then checked the topic doc**. Measured 2026-08-13:

    master_story_roadmap.md   1.6% over 200   max   363
    topic_*.md               33.5% over 200   max  5624
    US-*_integration.md       9.6% over 200   max  1909
    features/**/*_design.md   7.6% over 200   max  1830

All ten worst lines in the roadmap tree are `TECH` entries. The rule pushed the detail one level
down and stopped there, so the level below grew 5624-character lines.

**The remedy is redistribution, never deletion.** A topic entry that long is holding design-doc
content — measurements, approach tables, out-of-scope lists — which belongs in `<ID>_design.md`
while the topic entry keeps the summary. Where the content is already at the right depth, the
remedy is simply wrapping, which markdown renders identically. Either way nothing is dropped:
`scripts/check_entry_orphans.py` exists to prove that, listing facts present in an entry and absent
from its design so they are moved before the entry is cut.

**Ratcheted per FILE, not per line.** Line numbers shift under every edit, so a baseline keyed on
them would report false regressions constantly and be re-frozen until nobody read it — the same
reasoning that made the duplication ratchet key on content.

Usage:
    python scripts/_entry_depth.py            # judge the tree against the baseline
    python scripts/_entry_depth.py --list     # print the census
    python scripts/_entry_depth.py --freeze   # rewrite the baseline
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The registry tree. Design docs are included: there is no level below them, so their remedy is
#: wrapping rather than redistribution — but an unreadable, undiffable line is a defect there too.
TREE = Path("docs/roadmap")

BASELINE = REPO_ROOT / "scripts" / "baselines" / "entry_depth.json"

#: Same number as `R-LENGTH`. One rule, one limit — a second threshold would only invite arguing
#: about which applies where.
MAX_LINE = 200

#: A line whose length comes from one unbreakable token cannot be wrapped or redistributed, so
#: flagging it teaches nothing and would be worked around rather than fixed.
_UNBREAKABLE = re.compile(r"\S{120,}")


def _violating_lines(text: str) -> int:
    return sum(
        1 for line in text.splitlines() if len(line) > MAX_LINE and not _UNBREAKABLE.search(line)
    )


def census(root: Path) -> dict[str, int]:
    """Map `path relative to root` -> number of over-long lines. Clean files are omitted."""
    found: dict[str, int] = {}
    for path in sorted(root.rglob("*.md")):
        count = _violating_lines(path.read_text(encoding="utf-8", errors="replace"))
        if count:
            found[path.relative_to(root).as_posix()] = count
    return found


def load_baseline() -> dict[str, int]:
    if not BASELINE.exists():
        return {}
    data: dict[str, int] = json.loads(BASELINE.read_text(encoding="utf-8"))
    return data


def write_baseline(counts: dict[str, int]) -> None:
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(json.dumps(counts, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def regressions(live: dict[str, int], baseline: dict[str, int]) -> list[tuple[str, int, int]]:
    """`(file, was, now)` for every file that grew. Falling counts are the point of the ratchet."""
    return sorted(
        (path, baseline.get(path, 0), count)
        for path, count in live.items()
        if count > baseline.get(path, 0)
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="print the census")
    ap.add_argument("--freeze", action="store_true", help="rewrite the baseline from the tree")
    args = ap.parse_args(argv)

    root = REPO_ROOT / TREE
    # A checker that cannot find its subject must say so rather than pass — `TECH-032`'s lesson.
    if not root.is_dir():
        print(f"could not run: registry tree not found: {root}", file=sys.stderr)
        return 2

    live = census(root)

    if args.freeze:
        write_baseline(live)
        print(f"froze {sum(live.values())} over-long line(s) across {len(live)} file(s)")
        return 0

    if args.list:
        for path, count in sorted(live.items(), key=lambda kv: -kv[1]):
            print(f"  {count:4}  {path}")
        print(f"\n{sum(live.values())} over-long line(s) in {len(live)} file(s)")
        return 0

    grown = regressions(live, load_baseline())
    if grown:
        print(f"R-DEPTH -- registry lines over {MAX_LINE} chars ({len(grown)} file(s)):\n")
        for path, was, now in grown:
            print(f"  {path}: {was} -> {now}")
        print(
            "\nA line this long is usually content at the wrong depth: move the detail into the "
            "feature's `<ID>_design.md` and leave the summary in the topic doc. Run "
            "`python scripts/check_entry_orphans.py` first — it names the facts that would be lost "
            "so they are moved rather than dropped. Where the content is already at the right "
            "depth, wrap it; markdown renders that identically. The count may fall, never rise."
        )
        return 1

    print(f"R-DEPTH: {sum(live.values())} over-long line(s), none new")
    return 0


if __name__ == "__main__":
    sys.exit(main())
