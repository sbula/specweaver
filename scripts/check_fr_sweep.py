#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Sweep every design's FR ledger and ratchet the number of uncited requirements. `TECH-047`.

`check_fr_coverage.py` works, is correct, and takes a story ID — so it fires only when a human
remembers a story, and nobody remembers 61. It is the third check in this repo to be right and
silent: `check_story_preconditions.py` would have caught `INT-US-25` any day, and
`check_class_health.py` reported *"nothing in scope"* for a whole session while 23 classes failed.

**The sweep is the easy part. What to do with its output is the decision.** Turning the per-story
gate on repo-wide produces 45 blocked capabilities, and freezing those in a list means the ratchet
says "45 unverified capabilities is fine" — a ratchet nobody can act on is one nobody reads.

**So the ratchet counts REQUIREMENTS, not capabilities.** "265 FRs are cited by no test" is a live
number: any story that adds one real test moves it, and any new FR shipped without a test raises
it. A list of 45 names moves only when a whole capability is finished, which is never.

> [!IMPORTANT]
> **What a falling number does and does not mean.** This measures *attribution* — whether some test
> file cites the requirement. It cannot see whether that test proves anything; an `assert True`
> carrying a citation counts. So:
>
> * **An increase is a real signal** and blocks: a requirement shipped with no test at all.
> * **A decrease is not evidence of quality.** Bulk-adding citations to existing tests would move
>   this number without improving a single test, and doing that is gaming the gate rather than
>   using it.
>
> Strength is only answerable by mutation testing (`A-VAL-03`). See
> `.claude/skills/specweaver-ticket/references/closure-contract.md`.

Usage:
    python scripts/check_fr_sweep.py            # judge against the baseline
    python scripts/check_fr_sweep.py --list     # per-design breakdown, worst first
    python scripts/check_fr_sweep.py --freeze   # rewrite the baseline
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES = REPO_ROOT / "docs" / "roadmap" / "features"
BASELINE = REPO_ROOT / "scripts" / "baselines" / "fr_uncited.json"
ROADMAP = REPO_ROOT / "docs" / "roadmap" / "master_story_roadmap.md"

#: A story counts only once it is DELIVERED. An unbuilt capability's requirements are correctly
#: uncited — there is nothing to test yet — so counting them would punish the one thing this repo
#: most wants: writing requirements down before building. Found immediately: adding the fan-out
#: requirement to `C-FLOW-12` (unbuilt, and the new owner of `C-INTL-01`'s descoped `FR-3`) raised
#: the total and the ratchet blocked the commit that improved the specification.
_DELIVERED = re.compile(r"`(?:✅|🟢)`?\s*\*\*([A-Z][\w-]*-\d+(?:-SF\d+)?):")


def delivered_stories() -> set[str]:
    """Story ids the master roadmap marks delivered."""
    if not ROADMAP.is_file():
        return set()
    return set(_DELIVERED.findall(ROADMAP.read_text(encoding="utf-8", errors="replace")))


_spec = importlib.util.spec_from_file_location(
    "check_fr_coverage", Path(__file__).parent / "check_fr_coverage.py"
)
assert _spec is not None and _spec.loader is not None
_fr = importlib.util.module_from_spec(_spec)
sys.modules["check_fr_coverage"] = _fr
_spec.loader.exec_module(_fr)


def uncited(story: str) -> tuple[int, int]:
    """`(uncited, declared)` for one story. `(0, 0)` when it declares no FRs — a stub, not a gap."""
    design = next(FEATURES.rglob(f"{story}/{story}_design.md"), None)
    if design is None:
        return 0, 0
    text = design.read_text(encoding="utf-8", errors="replace")
    frs, error = _fr.declared_frs_from_text(text, design.name)
    if error is not None or not frs:
        return 0, 0
    cited = set(_fr.cited_frs_in_tests(REPO_ROOT / "tests", story))
    return len(set(frs) - cited), len(frs)


def census() -> dict[str, int]:
    """`story -> uncited FR count`, for DELIVERED stories with something uncited."""
    delivered = delivered_stories()
    found: dict[str, int] = {}
    for design in sorted(FEATURES.rglob("*_design.md")):
        story = design.parent.name
        if story not in delivered:
            continue
        count, _ = uncited(story)
        if count:
            found[story] = count
    return found


def load_baseline() -> int:
    if not BASELINE.exists():
        return 0
    data: dict[str, int] = json.loads(BASELINE.read_text(encoding="utf-8"))
    return int(data.get("uncited_frs", 0))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="per-design breakdown, worst first")
    ap.add_argument("--freeze", action="store_true", help="rewrite the baseline")
    args = ap.parse_args(argv)

    # A checker that cannot find its subject must say so, not pass — `TECH-032`'s lesson.
    if not FEATURES.is_dir():
        print(f"could not run: features tree not found: {FEATURES}", file=sys.stderr)
        return 2

    live = census()
    total = sum(live.values())

    if args.freeze:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(
            json.dumps({"uncited_frs": total, "designs": len(live)}, indent=2) + "\n", "utf-8"
        )
        print(f"froze {total} uncited FR(s) across {len(live)} design(s)")
        return 0

    if args.list:
        for story, count in sorted(live.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"  {count:3}  {story}")
        print(f"\n{total} uncited FR(s) across {len(live)} design(s)")
        return 0

    frozen = load_baseline()
    if total > frozen:
        print(
            f"FR sweep: {total} uncited requirement(s), was {frozen} — REGRESSION of {total - frozen}\n"
        )
        for story, count in sorted(live.items(), key=lambda kv: (-kv[1], kv[0]))[:10]:
            print(f"  {count:3}  {story}")
        print(
            "\nA requirement with no test is a promise nothing checks. Three legitimate answers, "
            "and one that is not:\n"
            "  * write the test;\n"
            "  * delete the FR row, so the descope is visible;\n"
            "  * cite an existing test — but ONLY after reading it and confirming it proves this "
            "requirement.\n"
            "  * NOT: adding citations in bulk without reading them. That moves this number "
            "without improving a single test, which is gaming the gate rather than using it."
        )
        return 1

    print(f"FR sweep: {total} uncited requirement(s) across {len(live)} design(s), none new")
    return 0


if __name__ == "__main__":
    sys.exit(main())
