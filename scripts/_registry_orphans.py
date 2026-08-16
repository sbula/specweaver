#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An entry must not exist in one registry and vanish from the other. `ADR-003`.

`check_roadmap_sync.py` compares **checkbox status** — a `[ ]` box whose capability is `✅` in the
matrix. It has never asked whether the two registries list the same **entries**, and its id pattern
covers capabilities only, excluding `INT-US-*` and `TECH-*`. So a topic-document entry could lose
its roadmap line and every gate stayed green.

**Measured the day this was written.** The `ADR-003` sweep removed 63 roadmap placeholder lines, and
**20 of those ids still had real entries in their topic documents** — scope, dependencies, blocking
notes, one of them minted the same morning. The `doc` gate passed throughout. That is the same shape
as `TECH-032`'s lesson and `TECH-019`'s: a check that never looks is indistinguishable from one that
passes.

**`RETIRED` is the sanctioned exit**, because it is precisely what `ADR-003` does to an integration
add-on: the roadmap line goes, the topic entry stays, carrying its scope and naming the capability
that now owns it. A retirement is a decision recorded in the open. An orphan is a decision nobody
took and nobody can see.

> [!IMPORTANT]
> **Ratcheted, because the debt predates the rule.** 10 entries are orphaned today and none came
> from `ADR-003`: nine capabilities were written into topic documents without ever reaching the
> master roadmap, and `INT-US-21-SUB` is `OQ-1`, the naming divergence accepted on 2026-07-25
> (the roadmap calls the same add-on `INT-US-21-SF01`) and deliberately left alone by `TECH-039`,
> which settled that a divergence stays legal where a collision does not.

Usage:
    python scripts/_registry_orphans.py            # judge against the baseline
    python scripts/_registry_orphans.py --list     # every orphan, with its file
    python scripts/_registry_orphans.py --freeze   # rewrite the baseline
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ROADMAP = REPO_ROOT / "docs" / "roadmap" / "master_story_roadmap.md"
TOPICS = REPO_ROOT / "docs" / "roadmap" / "topics"
BASELINE = REPO_ROOT / "scripts" / "baselines" / "registry_orphans.json"

_ID = r"(?:[A-E]-(?:UI|SENS|FLOW|INTL|VAL|EXEC)|INT-US|TECH)-\d+(?:-SF\d+|-SUB)?"

#: An ENTRY is a list item whose bold span carries the id — `**C-FLOW-11:**` in the roadmap,
#: ``**Autonomous DAG Execution (`C-FLOW-12`)**`` in a topic doc. Prose that merely cites an id
#: ("sequenced behind `C-EXEC-07`") is not an entry and must never be treated as one.
_ENTRY = re.compile(rf"^\s*[*-]\s+.{{0,8}}\*\*[^\n]*?\b({_ID})\b")

#: An entry ends at the next TOP-LEVEL list item or heading — never at the next blank line. Getting
#: this wrong is what produced the defect this checker exists for: consecutive single-line entries
#: carry no blank line between them, so a note appended at "the next blank line" landed under a
#: later entry and silently absolved every entry it skipped.
_ENDS_ENTRY = re.compile(r"^(?:[*-]\s|#{1,6}\s)")

#: The sanctioned exits, and the word boundary is load-bearing. A bare `"RETIRED" in body` also
#: matches **`UN-RETIRED`** — so withdrawing a retirement kept the entry absolved and its missing
#: roadmap line went unreported, which inverts the checker: a withdrawal is exactly when the
#: roadmap line has to come back. Found 2026-08-16 restoring `INT-US-03-SF01`.
#:
#: `CLOSED EMPTY` is the second exit, for an add-on that lost its roadmap line because nothing was
#: left to build rather than because the scope moved. `INT-US-25-SF01` is the case: three delivered
#: capabilities, all exercised by its own base contract, only a scope decision outstanding. Forcing
#: that to say `RETIRED` would make it claim a move that never happened.
_DISPOSITIONS = re.compile(r"(?<![-\w])(?:RETIRED|CLOSED EMPTY)\b")


def entry_ids(text: str) -> set[str]:
    """Every id that this text declares as an entry."""
    found: set[str] = set()
    for line in text.splitlines():
        match = _ENTRY.match(line)
        if match:
            found.add(match.group(1))
    return found


def orphans(roadmap: str, topics: dict[str, str]) -> list[tuple[str, str]]:
    """`(id, file)` for every topic entry with no roadmap entry and no recorded retirement."""
    known = entry_ids(roadmap)
    found: list[tuple[str, str]] = []
    for name in sorted(topics):
        lines = topics[name].splitlines()
        for index, line in enumerate(lines):
            match = _ENTRY.match(line)
            if not match or match.group(1) in known:
                continue
            end = index + 1
            while end < len(lines) and not _ENDS_ENTRY.match(lines[end]):
                end += 1
            if any(_DISPOSITIONS.search(body) for body in lines[index:end]):
                continue
            found.append((match.group(1), name))
    return found


def _read_topics() -> dict[str, str]:
    return {
        path.name: path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(TOPICS.rglob("*.md"))
    }


def load_baseline() -> int:
    if not BASELINE.exists():
        return 0
    data: dict[str, int] = json.loads(BASELINE.read_text(encoding="utf-8"))
    return int(data.get("orphans", 0))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="every orphan, with its file")
    parser.add_argument("--freeze", action="store_true", help="rewrite the baseline")
    args = parser.parse_args(argv)

    # A checker that cannot find its subject must say so, not pass — `TECH-032`'s lesson.
    if not ROADMAP.is_file() or not TOPICS.is_dir():
        print("could not run: roadmap or topics tree not found", file=sys.stderr)
        return 2

    live = orphans(ROADMAP.read_text(encoding="utf-8", errors="replace"), _read_topics())

    if args.freeze:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps({"orphans": len(live)}, indent=2) + "\n", "utf-8")
        print(f"froze {len(live)} orphaned registry entr(ies)")
        return 0

    if args.list:
        for identifier, name in live:
            print(f"  {identifier:<16} {name}")
        print(f"\n{len(live)} orphaned registry entr(ies)")
        return 0

    frozen = load_baseline()
    if len(live) > frozen:
        print(f"registry orphans: {len(live)}, was {frozen} — REGRESSION of {len(live) - frozen}\n")
        for identifier, name in live:
            print(f"  {identifier:<16} {name}")
        print(
            "\nEach exists as an entry in a topic document with no entry in the master roadmap, so "
            "the two registries disagree about what exists. Two legitimate answers:\n"
            "  * restore the roadmap entry, if the work is still planned;\n"
            "  * record the decision in the topic entry — a `RETIRED` note naming the capability "
            "that now owns the scope (`ADR-003`), which keeps the scope visible instead of "
            "deleting it.\n"
            "  * NOT: deleting the topic entry to make this number fall. That destroys the only "
            "record of the scope, which is the outcome this check exists to prevent."
        )
        return 1

    print(f"registry orphans: {len(live)}, none new")
    return 0


if __name__ == "__main__":
    sys.exit(main())
