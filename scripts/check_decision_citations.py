#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Ratchet designs that do not account for the must-not-guess triggers.

`PRINCIPLES.md` §2 names the decisions an agent may not take alone. Nothing read a design against
that list, so the list was advisory: an agent could settle a spend ceiling, a retention period or a
proven-verdict, write it into a design, and pass every gate here.

A design accounts for the list when a `Decisions taken with the user` section mentions every
trigger, each on a line carrying a marker:

    ## Decisions taken with the user

    - `T-SPEND`, `T-BOUNDARY`, `T-POSTURE`: not touched
    - `T-DEFAULT`: fired — chunk size 4096, set by the user

`not touched` needs nothing after it. `fired` must carry what was settled, which is what makes the
section evidence rather than a checklist. A trigger mentioned in a line the parser cannot read
counts as missing: an unreadable design goes red rather than quiet.

The trigger list is READ from `PRINCIPLES.md`, so adding or dropping one is a single-place edit and
this file cannot drift from it.

The ratchet holds the count of designs that do not account for the list. It may fall, never rise.
A missing or unreadable baseline fails closed — a ratchet nobody can read is not a ratchet.

Exit code 1 if the count exceeds the baseline.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PRINCIPLES_PATH = REPO_ROOT / ".agents" / "PRINCIPLES.md"
DESIGNS_ROOT = REPO_ROOT / "docs" / "roadmap" / "features"
BASELINE_PATH = REPO_ROOT / "scripts" / "baselines" / "decision_citations.json"

SECTION_TITLE = "decisions taken with the user"

_HEADING = re.compile(r"^#{1,6}\s+(?P<title>.+?)\s*$")
_TRIGGER = re.compile(r"`(T-[A-Z]+)`")
_TABLE_ROW = re.compile(r"^\|")
_MARKER = re.compile(r"\b(?P<marker>not touched|fired)\b(?P<rest>.*)$", re.IGNORECASE)


def triggers_from_principles(text: str) -> frozenset[str]:
    """Collect the trigger IDs from §2's table.

    Only table rows count. A `T-` token in prose elsewhere in the file is a mention, not an entry,
    and treating it as one would let a paragraph invent a trigger nobody agreed.
    """
    found: set[str] = set()
    for line in text.splitlines():
        if _TABLE_ROW.match(line):
            found.update(_TRIGGER.findall(line))
    return frozenset(found)


def _section_lines(text: str) -> list[str] | None:
    """Return the lines under the decisions heading, or None when there is no such heading."""
    lines = text.splitlines()
    start: int | None = None
    depth = 0
    for index, line in enumerate(lines):
        heading = _HEADING.match(line)
        if heading is None:
            continue
        title = heading.group("title").strip().strip("*_` ").lower()
        if start is None:
            if SECTION_TITLE in title:
                start = index + 1
                depth = len(line) - len(line.lstrip("#"))
            continue
        if len(line) - len(line.lstrip("#")) <= depth:
            return lines[start:index]
    return None if start is None else lines[start:]


def _logical_lines(lines: list[str]) -> list[str]:
    """Rejoin a markdown bullet with the lines it wraps onto.

    Authors wrap prose; a bullet listing eight trigger ids and its `not touched` marker routinely
    lands on two physical lines. Matching line by line reported those ids as unmarked, which is a
    false failure on correct prose -- and a gate that cries wolf is one somebody switches off.
    """
    joined: list[str] = []
    for line in lines:
        continuation = bool(joined) and line.startswith((" ", "\t")) and bool(line.strip())
        if continuation:
            joined[-1] = f"{joined[-1].rstrip()} {line.strip()}"
        else:
            joined.append(line)
    return joined


def audit_design(text: str, triggers: frozenset[str]) -> tuple[str, ...]:
    """Report why a design does not account for the triggers. Empty means it does."""
    lines = _section_lines(text)
    if lines is None:
        return ("no `Decisions taken with the user` section",)

    accounted: set[str] = set()
    reasons: list[str] = []
    for line in _logical_lines(lines):
        mentioned = set(_TRIGGER.findall(line)) & triggers
        if not mentioned:
            continue
        named = ", ".join(sorted(mentioned))
        marker = _MARKER.search(line)
        if marker is None:
            reasons.append(f"{named}: mentioned with no `not touched` or `fired` marker")
        elif marker.group("marker").lower() == "fired" and not marker.group("rest").strip(
            " \u2014\u2013-:"
        ):
            reasons.append(f"{named}: `fired` with nothing recording what was settled")
        else:
            accounted |= mentioned

    # One reason per trigger. A trigger already named in an unreadable-line reason does not also
    # get a "not mentioned" one -- two lines for one problem reads as two problems.
    for trigger in sorted(triggers - accounted):
        if not any(trigger in reason for reason in reasons):
            reasons.append(f"{trigger}: not mentioned")
    return tuple(reasons)


def over_baseline(count: int, baseline_path: Path) -> bool:
    """True when the count exceeds the recorded baseline, or the baseline cannot be read."""
    try:
        recorded = json.loads(baseline_path.read_text(encoding="utf-8"))["unaccounted"]
    except (OSError, ValueError, KeyError, TypeError):
        return True
    return count > int(recorded)


def main() -> int:
    triggers = triggers_from_principles(PRINCIPLES_PATH.read_text(encoding="utf-8"))
    if not triggers:
        print("ERROR: no triggers found in PRINCIPLES.md §2 — the list moved or the table changed")
        return 1

    unaccounted: list[tuple[Path, tuple[str, ...]]] = []
    for design in sorted(DESIGNS_ROOT.rglob("*_design.md")):
        reasons = audit_design(design.read_text(encoding="utf-8"), triggers)
        if reasons:
            unaccounted.append((design, reasons))

    count = len(unaccounted)
    if not over_baseline(count, BASELINE_PATH):
        print(f"Decision citations: {count} design(s) unaccounted, baseline holds")
        return 0

    print(f"D-CITE -- {count} design(s) do not account for the §2 triggers:\n")
    for design, reasons in unaccounted[:10]:
        print(f"  {design.relative_to(REPO_ROOT)}")
        for reason in reasons[:4]:
            print(f"      {reason}")
    if count > 10:
        print(f"\n  ... and {count - 10} more not listed")
    print(
        "\nA design accounts for the list when its `Decisions taken with the user` section names\n"
        "every trigger in `PRINCIPLES.md` §2. Group the quiet ones on one line:\n\n"
        "  - `T-SPEND`, `T-BOUNDARY`, `T-POSTURE`: not touched\n"
        "  - `T-DEFAULT`: fired — chunk size 4096, set by the user\n\n"
        "A `fired` trigger must record what was settled. The count may fall, never rise."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
