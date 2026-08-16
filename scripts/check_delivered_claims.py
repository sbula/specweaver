#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A `✅` that nothing can verify. `TECH-053`.

Two claims in the registry are unfalsifiable today, and this makes both countable.

**A group flag that disagrees with its own children.** Nothing compares them, so an add-on group
can read *"zero requirements have been checked"* while every capability under it is `✅`, or the
reverse. Six were wrong on 2026-08-16, two of them saying `🟢` over capabilities whose own ledgers
fail. Zero-tolerance, because those six were corrected in `577744b3` and there is no backlog left
to excuse.

**A delivered capability `check_fr_sweep.py` cannot see.** That sweep counts *uncited FRs across
delivered designs*. A capability with **no design** contributes no design; one whose design
**declares no FRs** contributes no FRs. Both therefore score **zero uncited** and are
indistinguishable from perfect — not a flaw in the sweep, which counts what it says, but it leaves
a hole exactly where the claim is weakest.

Measured 2026-08-16 across the 62 capabilities marked `✅` in the matrix:

    39  declare FRs that nothing cites   <- already ratcheted by check_fr_sweep.py
    19  have no design document at all   <- invisible until now
     3  declare no FRs                   <- invisible until now
     1  clean

The 22 is the ratcheted figure. A first draft said 24: it read FR tables only, and `C-SENS-02` and
`D-SENS-03` declare theirs as bullets. Hence `_fr_reader()` below.

Ratcheted rather than blocking, deliberately: writing nineteen missing design documents is a
programme, not a commit boundary, and a gate that fails on its own backlog is switched off within a
day. The count may fall and never rise.

**What this does NOT do** is re-count the 39. Two gates for one number means two baselines to
freeze and two places to argue about the same capabilities.

Usage:
    python scripts/check_delivered_claims.py          # judge the registry
    python scripts/check_delivered_claims.py --list   # every finding, with its cause
    python scripts/check_delivered_claims.py --freeze # rewrite the baseline
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE = REPO_ROOT / "scripts" / "baselines" / "delivered_claims.json"

#: `✅ C-FLOW-01` inside one code span, which is how the matrix writes its cells.
_MATRIX_CELL = re.compile(r"`([^\s`]+)\s+([A-E]-[A-Z]+-\d+)`")

#: An add-on group heading in `master_story_roadmap.md`, and the capability lines beneath it.
_GROUP = re.compile(r"^    \*   ([🔴🟡🟢🔵]) \*\*(.+?):\*\*\s*$")
_CHILD = re.compile(r"^        \*   `(✅|\[ \])` ")


#: `🔵` is *on hold* — a statement about intent, not progress. Deriving it from children would
#: silently un-park anything with one delivered dependency, which is the decision the flag records.
_DERIVED_FLAGS = ("🔴", "🟡", "🟢")


@dataclass(frozen=True)
class GroupFinding:
    """An add-on group whose flag contradicts the capabilities listed under it."""

    group: str
    reason: str


@dataclass(frozen=True)
class CapabilityFinding:
    """A capability marked `✅` with nothing behind it that any gate can read."""

    capability: str
    reason: str


def _expected_flag(done: int, total: int) -> str:
    if done == total:
        return "🟢"
    return "🔴" if done == 0 else "🟡"


def group_flag_findings(roadmap_root: Path) -> list[GroupFinding]:
    """Every add-on group whose flag disagrees with its own children."""
    path = roadmap_root / "master_story_roadmap.md"
    if not path.is_file():
        return []

    lines = path.read_text(encoding="utf-8").splitlines()
    found: list[GroupFinding] = []
    index = 0
    while index < len(lines):
        match = _GROUP.match(lines[index])
        if not match:
            index += 1
            continue
        flag, name = match.groups()
        cursor, done, total = index + 1, 0, 0
        while cursor < len(lines) and (child := _CHILD.match(lines[cursor])):
            total += 1
            done += child.group(1) == "✅"
            cursor += 1
        if total and flag in _DERIVED_FLAGS:
            want = _expected_flag(done, total)
            if want != flag:
                found.append(GroupFinding(name, f"{done} of {total} done, so {want} not {flag}"))
        index = cursor
    return found


def _fr_reader():
    """`check_fr_coverage`'s own declaration grammar, loaded rather than re-implemented.

    **A second parser was written first and was wrong twice.** A table-row regex missed
    `C-SENS-02` (5 FRs) and `D-SENS-03` (7 FRs), which declare theirs as bullets — reporting two
    capabilities as having no requirements when they have twelve between them. One reader of a
    design document, not two: this loads the module that already answers the question.

    `scripts/` is not a package, so it comes in by path, the shape `quality.py` and
    `check_roadmap_sync.py` already use.
    """
    import importlib.util

    path = Path(__file__).resolve().parent / "check_fr_coverage.py"
    spec = importlib.util.spec_from_file_location("check_fr_coverage", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_fr_coverage"] = module
    spec.loader.exec_module(module)
    return module


def unverifiable_findings(roadmap_root: Path) -> list[CapabilityFinding]:
    """Every capability marked `✅` that declares nothing a gate could check it against."""
    matrix = roadmap_root / "capability_matrix.md"
    if not matrix.is_file():
        return []

    delivered = sorted(
        {
            cap
            for glyph, cap in _MATRIX_CELL.findall(matrix.read_text(encoding="utf-8"))
            if glyph == "✅"
        }
    )
    reader = _fr_reader()
    features_root = roadmap_root / "features"
    found: list[CapabilityFinding] = []
    for capability in delivered:
        design = reader.find_design_doc(features_root, capability)
        if design is None:
            found.append(CapabilityFinding(capability, "no design document"))
            continue
        frs, _error = reader.declared_frs_from_text(design.read_text(encoding="utf-8"), design.name)
        if not frs:
            found.append(CapabilityFinding(capability, "design declares no FRs"))
    return found


def load_baseline() -> int:
    if not BASELINE.exists():
        return 0
    data: dict[str, int] = json.loads(BASELINE.read_text(encoding="utf-8"))
    return int(data.get("unverifiable", 0))


def write_baseline(count: int) -> None:
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(json.dumps({"unverifiable": count}, indent=2) + "\n", encoding="utf-8")


def _report(groups: list[GroupFinding], caps: list[CapabilityFinding], baseline: int) -> None:
    if groups:
        print(f"Add-on group flags that contradict their own children ({len(groups)}):\n")
        for finding in groups:
            print(f"  {finding.group}\n        {finding.reason}")
        print(
            "\nThe flag is derived from the capabilities beneath it — 🟢 iff all are ✅, 🔴 iff "
            "none are. Six were wrong on 2026-08-16, two of them claiming 🟢 over capabilities whose "
            "own ledgers fail. Correct the flag, or correct the checkbox that is lying.\n"
        )
    if caps:
        print(f"Capabilities marked ✅ with nothing to verify: {len(caps)}, was {baseline}\n")
        for finding in caps:
            print(f"  {finding.capability:14} {finding.reason}")
        print(
            "\n`check_fr_sweep.py` cannot see these: no design means no FRs to be uncited, so they "
            "score zero and read as perfect. The remedy is the cause — write the design, or declare "
            "the FRs the delivered code already satisfies. The count may fall, never rise."
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=str(REPO_ROOT), help="repository root to judge")
    ap.add_argument("--baseline", type=int, default=None, help="override the frozen count")
    ap.add_argument("--list", action="store_true", help="print every finding")
    ap.add_argument("--freeze", action="store_true", help="rewrite the baseline")
    args = ap.parse_args(argv)

    roadmap_root = Path(args.root) / "docs" / "roadmap"
    if not (roadmap_root / "capability_matrix.md").is_file():
        print(f"could not run: no capability matrix under {roadmap_root}", file=sys.stderr)
        return 2

    groups = group_flag_findings(roadmap_root)
    caps = unverifiable_findings(roadmap_root)
    baseline = args.baseline if args.baseline is not None else load_baseline()

    if args.freeze:
        write_baseline(len(caps))
        print(f"froze {len(caps)} unverifiable delivered capability claim(s)")
        return 0

    if args.list:
        _report(groups, caps, baseline)
        return 0

    if groups or len(caps) > baseline:
        _report(groups, caps, baseline)
        return 1

    print(
        f"Delivered claims: group flags agree with their children; "
        f"{len(caps)} unverifiable capability claim(s), none new."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
