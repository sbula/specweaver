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
remedy is simply wrapping, which markdown renders identically. Either way nothing is dropped. A throwaway checker
(`check_entry_orphans.py`, 2026-08-13) listed facts present in an entry and absent from every
deeper document; it found 21 real ones across 39 entries and was deleted by its own test once the
R-ENTRY backlog reached zero.

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
import math
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Every markdown document in the repo. One line-length rule for all of them, which is why
#: `R-LENGTH` was deleted from `check_roadmap_placement.py` when this widened — it capped the same
#: 200 characters on a strict subset (roadmap entries only), so keeping both meant two rules, one
#: number, and one of them doing nothing the other did not.
#:
#: Design docs are in scope even though there is no level below them: their remedy is wrapping
#: rather than redistribution, but an unreadable, undiffable line is a defect there too.
TREE = Path(".")

#: Not ours to wrap.
_SKIP_DIRS = frozenset({".venv", "node_modules", ".git", "__pycache__", "site-packages"})

BASELINE = REPO_ROOT / "scripts" / "baselines" / "entry_depth.json"
ENTRY_BASELINE = REPO_ROOT / "scripts" / "baselines" / "entry_lines.json"

#: R-ENTRY. An L2 topic entry is at most this many lines' worth of content.
#:
#: Chosen from pre-drift practice, not invented: capability entries across topics 01-06 have a
#: median of 247 characters and a p90 of 493; the oldest TECH cohort (`TECH-001..013`, before the
#: inflation that began around `TECH-014`) sits at a median of 588. So a TECH entry is legitimately
#: ~2.4x a capability entry — and not the 10x the recent cohorts measure. One number covers both.
MAX_ENTRY_LINES = 4

#: Only L2 documents have entries. In a feature folder the FILE is the unit, so there is nothing
#: here for L3/L4 — a different rule would be needed and none exists yet.
_TOPIC_DOC = "topic_*.md"

#: `* **`ID` …**` followed by its `>` blockquote, however many physical lines that spans.
_ENTRY_BLOCK = re.compile(r"^\* \*\*`([A-Z][\w-]*-\d+)`.*$\n((?:\s*>.*\n?)*)", re.M)

#: Same number as `R-LENGTH`. One rule, one limit — a second threshold would only invite arguing
#: about which applies where.
MAX_LINE = 200

#: A line whose length comes from one unbreakable token cannot be wrapped or redistributed, so
#: flagging it teaches nothing and would be worked around rather than fixed.
_UNBREAKABLE = re.compile(r"\S{120,}")

#: A markdown table row has **no legal wrap point** — a newline ends the row. Flagging one leaves
#: only bad options: destroy the table, or split a cell across rows that no longer align. Found by
#: this rule firing on five rows moved into `TECH-035`'s build record during the first
#: redistribution it was written to enable.
#:
#: Honest limitation, stated rather than hidden: a 379-character row IS too much detail in a cell,
#: and this exemption cannot say so. It is not an invitation to write prose as a one-column table —
#: that is a review question, not a mechanical one.
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")


def _violating_lines(text: str) -> int:
    return sum(
        1
        for line in text.splitlines()
        if len(line) > MAX_LINE and not _UNBREAKABLE.search(line) and not _TABLE_ROW.match(line)
    )


def census(root: Path) -> dict[str, int]:
    """Map `path relative to root` -> number of over-long lines. Clean files are omitted."""
    found: dict[str, int] = {}
    for path in sorted(root.rglob("*.md")):
        if _SKIP_DIRS.intersection(path.parts):
            continue
        count = _violating_lines(path.read_text(encoding="utf-8", errors="replace"))
        if count:
            found[path.relative_to(root).as_posix()] = count
    return found


def entry_census(root: Path) -> dict[str, int]:
    """Map `<topic file>::<ID>` -> effective lines, for entries over `MAX_ENTRY_LINES`.

    **Effective** lines: content length divided by the line limit, NOT physical newlines. A rule
    counting newlines is evaded by not wrapping — 187 of 191 entries are a single physical line
    today, several of them thousands of characters, so a newline rule finds 4 offenders where there
    are 41.
    """
    found: dict[str, int] = {}
    for path in sorted(root.rglob(_TOPIC_DOC)):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in _ENTRY_BLOCK.finditer(text):
            body = " ".join(
                line.strip().lstrip(">").strip()
                for line in match.group(2).splitlines()
                if line.strip()
            )
            lines = math.ceil(len(body) / MAX_LINE)
            if lines > MAX_ENTRY_LINES:
                found[f"{path.name}::{match.group(1)}"] = lines
    return found


def load_entry_baseline() -> dict[str, int]:
    if not ENTRY_BASELINE.exists():
        return {}
    data: dict[str, int] = json.loads(ENTRY_BASELINE.read_text(encoding="utf-8"))
    return data


def entry_regressions(live: dict[str, int], baseline: dict[str, int]) -> list[tuple[str, int, int]]:
    """`(entry, allowed, now)` for entries that grew — or that are NEW and already over.

    A new entry gets no free first offence: absent from the baseline, its allowance is the limit
    itself. Freezing on sight is how a ratchet becomes a rubber stamp.
    """
    return sorted(
        (key, baseline.get(key, MAX_ENTRY_LINES), count)
        for key, count in live.items()
        if count > baseline.get(key, MAX_ENTRY_LINES)
    )


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
        print(f"could not run: tree not found: {root}", file=sys.stderr)
        return 2

    live = census(root)
    entries = entry_census(root / "docs" / "roadmap" / "topics")

    if args.freeze:
        write_baseline(live)
        ENTRY_BASELINE.write_text(
            json.dumps(entries, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(
            f"froze {sum(live.values())} over-long line(s) across {len(live)} file(s), "
            f"and {len(entries)} over-long entr(y/ies)"
        )
        return 0

    if args.list:
        for path, count in sorted(live.items(), key=lambda kv: -kv[1]):
            print(f"  {count:4}  {path}")
        print(f"\n{sum(live.values())} over-long line(s) in {len(live)} file(s)")
        for key, count in sorted(entries.items(), key=lambda kv: -kv[1]):
            print(f"  {count:4}  {key}")
        print(f"{len(entries)} entr(y/ies) over {MAX_ENTRY_LINES} lines")
        return 0

    grown = regressions(live, load_baseline())
    if grown:
        print(f"R-DEPTH -- registry lines over {MAX_LINE} chars ({len(grown)} file(s)):\n")
        for path, was, now in grown:
            print(f"  {path}: {was} -> {now}")
        print(
            "\nA line this long is usually content at the wrong depth. The spine has FOUR layers, "
            "so 'move it to the design' is rarely the whole answer: roadmap line -> topic entry "
            "-> design -> build record (plan / walkthrough / review). Separately, and NOT deeper: "
            "docs/analysis/, 06_lessons_and_future/, 07_architectural_decision_records/ and "
            "dev_guides/ hold what outlives the ticket — a different audience, not more detail.\n"
            "Move the detail down and leave the summary, or — where it is already at the right "
            "depth — simply wrap it; markdown renders that identically. Never delete: check that "
            "each fact survives somewhere deeper before cutting it. See `TECH-044` for the layer "
            "map. The count may fall, never rise."
        )
        return 1

    grown_entries = entry_regressions(entries, load_entry_baseline())
    if grown_entries:
        print(f"R-ENTRY -- topic entries over {MAX_ENTRY_LINES} lines ({len(grown_entries)}):\n")
        for key, allowed, now in grown_entries:
            print(f"  {key}: {allowed} -> {now} lines")
        print(
            f"\nAn L2 topic entry is a SUMMARY: what, why, how sequenced, in about "
            f"{MAX_ENTRY_LINES} lines. Pre-drift practice is a median of 247 characters for a "
            "capability and 588 for a TECH ticket; anything near ten times that is carrying a "
            "deeper layer's content. Move it into the design or the delivery record — run "
            "each fact survives somewhere deeper before cutting it. Measured "
            "as content length, so wrapping does not change the verdict."
        )
        return 1

    print(
        f"R-DEPTH: {sum(live.values())} over-long line(s), none new. "
        f"R-ENTRY: {len(entries)} over-long entr(y/ies), none new."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
