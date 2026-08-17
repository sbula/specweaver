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

#: A story header, its Core Required (MVS) heading, and an MVS item — which is a
#: **4-space** list line. 8 spaces is a sub-story add-on and belongs to the group rule above;
#: indentation is the only thing separating the two planes.
_STORY = re.compile(r"^### ([🔴🟡🟢🔵]) (US-\d+)")
_MVS_HEAD = re.compile(r"^\*   \*\*Core Required \(MVS\):\*\*")
_MVS_ITEM = re.compile(r"^    \*   `(✅|\[ \])` \*\*([\w-]+):")


#: `🔵` is *on hold* — a statement about intent, not progress. Deriving it from children would
#: silently un-park anything with one delivered dependency, which is the decision the flag records.
_DERIVED_FLAGS = ("🔴", "🟡", "🟢")


@dataclass(frozen=True)
class GroupFinding:
    """An add-on group whose flag contradicts the capabilities listed under it."""

    group: str
    reason: str


@dataclass(frozen=True)
class StoryFinding:
    """A story flagged `🟢` whose Core Required (MVS) list still holds unbuilt work."""

    story: str
    reason: str


@dataclass(frozen=True)
class UnprovenGreenFinding:
    """A green story or add-on group holding closed features with no integration contract at all."""

    unit: str
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


def story_flag_findings(roadmap_root: Path) -> list[StoryFinding]:
    """Every `🟢` story with an undelivered item in its own Core Required (MVS) list.

    The roadmap's legend says `🟢` means *"Core MVS is 100% delivered"*, and nothing checked it.
    `group_flag_findings` compares an add-on **group** with its children and never a **story** with
    its MVS, so appending one `[ ]` to a completed story's Core Required list makes the flag false
    in a way no gate can see — which is how `C-FLOW-13` un-completed `US-4` for a day.

    Reads only the 4-space plane. A completed story routinely carries unfinished add-ons at 8
    spaces; that is what an add-on is, and reading them here would report every `🟢` story in the
    file.
    """
    path = roadmap_root / "master_story_roadmap.md"
    if not path.is_file():
        return []

    found: list[StoryFinding] = []
    story: str | None = None
    in_mvs = False
    pending: list[str] = []

    def close() -> None:
        if story and pending:
            found.append(
                StoryFinding(story=story, reason="🟢 but Core MVS holds " + ", ".join(pending))
            )

    for line in path.read_text(encoding="utf-8").splitlines():
        header = _STORY.match(line)
        if header:
            close()
            story = header.group(2) if header.group(1) == "🟢" else None
            in_mvs, pending = False, []
            continue
        if _MVS_HEAD.match(line):
            in_mvs = True
            continue
        if line.startswith("*   **"):
            in_mvs = False
            continue
        item = _MVS_ITEM.match(line) if in_mvs else None
        if item and item.group(1) != "✅":
            pending.append(item.group(2))
    close()
    return found


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


#: A capability id, as opposed to a dependency reference (`US-4 Core`) or a bootstrap step.
_CAPABILITY_ID = re.compile(r"^[A-E]-[A-Z]+-\d+$")

#: An integration contract id. `-MIG` is DELIBERATELY excluded: a migration entry is the task of
#: building the inventory, not the proof it produces, so a green unit citing only its `-MIG` still
#: owes a contract.
_CONTRACT_ID = re.compile(r"^INT-US-\d+(?:-(?:SF\d+|SUB))?$")

#: Any checkbox item on either plane, with its indent, so one walk can judge both.
_ANY_ITEM = re.compile(r"^( {4,})\*   `(✅|\[ \])` \*\*([\w-]+)")


def unproven_green_findings(roadmap_root: Path) -> list[UnprovenGreenFinding]:
    """`ADR-004` clause 5: a green unit holding closed features must have a delivered contract.

    The distinctive word is **absence**. `group_flag_findings` and `story_flag_findings` compare a
    flag with the children present, so an UNCHECKED integration entry already forces `🟡` and needs
    no new rule. Neither can see a child nobody wrote — and a check that never looks is
    indistinguishable from one that passes, which is the argument this whole module rests on.

    Zero-tolerance. The design expected this to fire on all 27 migration entries; measured once they
    were registered it fires on none, because those units are `🟡` or their contracts are `[ ]`.
    """
    roadmap = (roadmap_root / "master_story_roadmap.md").read_text(encoding="utf-8")

    findings: list[UnprovenGreenFinding] = []
    unit: str | None = None
    flag: str | None = None
    depth = 4
    closed: list[str] = []
    contract_done = False

    def judge() -> None:
        if unit is not None and flag == "🟢" and closed and not contract_done:
            findings.append(
                UnprovenGreenFinding(
                    unit,
                    f"🟢 over {', '.join(closed)} with no delivered integration contract",
                )
            )

    for line in roadmap.splitlines():
        story = _STORY.match(line)
        group = _GROUP.match(line)
        if story or group:
            judge()
            unit = story.group(2) if story else group.group(2)
            flag = (story or group).group(1)
            depth = 4 if story else 8
            closed, contract_done = [], False
            continue
        item = _ANY_ITEM.match(line)
        if item is None or unit is None:
            continue
        if len(item.group(1)) != depth:
            continue
        state, ident = item.group(2), item.group(3)
        if _CONTRACT_ID.match(ident):
            contract_done = contract_done or state == "✅"
        elif _CAPABILITY_ID.match(ident) and state == "✅":
            closed.append(ident)
    judge()
    return findings


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


def _report(
    groups: list[GroupFinding],
    caps: list[CapabilityFinding],
    baseline: int,
    stories: list[StoryFinding] | None = None,
    unproven: list[UnprovenGreenFinding] | None = None,
) -> None:
    if unproven:
        print(
            f"Green units holding closed features with no integration contract ({len(unproven)}):\n"
        )
        for finding in unproven:
            print(f"  {finding.unit}\n        {finding.reason}")
        print(
            "\n`ADR-004` clause 5: a (sub)story may not go green while the integration and e2e proof "
            "for its closed features is missing, even when every feature task beneath it is green. "
            "Mint the contract, or correct the flag.\n"
        )
    for finding in stories or []:
        print(f"  {finding.story:8} {finding.reason}")
    if stories:
        print(
            "\nThe legend says 🟢 means Core MVS is 100% delivered. An unbuilt item in that list "
            "makes the flag false — move it to a Sub-Story Add-On (8 spaces, not 4) or deliver it "
            "\n"
        )
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

    stories = story_flag_findings(roadmap_root)
    groups = group_flag_findings(roadmap_root)
    unproven = unproven_green_findings(roadmap_root)
    caps = unverifiable_findings(roadmap_root)
    baseline = args.baseline if args.baseline is not None else load_baseline()

    if args.freeze:
        write_baseline(len(caps))
        print(f"froze {len(caps)} unverifiable delivered capability claim(s)")
        return 0

    if args.list:
        _report(groups, caps, baseline, stories, unproven)
        return 0

    if stories or groups or unproven or len(caps) > baseline:
        _report(groups, caps, baseline, stories, unproven)
        return 1

    print(
        f"Delivered claims: group flags agree with their children; "
        f"{len(caps)} unverifiable capability claim(s), none new."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
