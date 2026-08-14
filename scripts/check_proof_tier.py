#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A delivered integration contract must cite integration or e2e tests. `TECH-017`, Approach 3.

**The rule.** An `INT-US-NN` story is an integration contract, so its proof must be integration and
e2e tests. Unit tests are the right tool for TDD of a *unit*, and belong inside an integration
story only to fix a specific behaviour or fill a narrow gap found while integrating — so a proof
naming BOTH passes here. Only a proof that names unit tests and nothing else fails.

**Why it takes no arguments.** `check_story_preconditions.py` already carries a check that fails an
`INT-US-NN` marked delivered whose Verifiable Proof is `[Pending]`. It would have caught
`INT-US-25` from the day it was written. It never did — it only runs when a human passes that
story ID, and nobody ever passed `INT-US-25`; the contradiction sat in the roadmap until it was
found by hand on 2026-08-13. This checker therefore judges **every** contract in the tree on every
`doc` gate run, because in this repo a check that must be invoked to fire is a check that reports
success by not running.

**Two failure shapes, both real, found by the first sweep:**

* `unit_only` — the proof names test files, all of them under `tests/unit/`. The exact tier
  mismatch the ticket exists to name.
* `no_test_file` — the proof names no test *file* at all: a directory (`tests/e2e/capabilities/
  core/`), a bare marker (`pytest -m integration`), a suite named in prose, or `[Pending]`. A place
  is not a proof — nothing pins which test carries the claim, so the claim cannot rot loudly.

All three violations in the first sweep are the second shape, and the third is why it matters as
much as the first. `INT-US-21-SUB` claims coverage by "`pytest -m integration` and the
`FeatureDecomposer` suite"; naming no file is what let that stand for months, because a reader
cannot check it without going and finding the suite. `TECH-018` did go and find it: the suite is
`tests/unit/workflows/planning/test_decomposer.py` — **4 unit tests** — and both integration files
mentioning `FeatureDecomposer` patch it out. Written as a path, it would have been `unit_only` and
visible on day one.

**Entries are keyed by file + title, not by ID, because IDs are not unique.** `INT-US-05-SUB`
names two different delivered add-ons — Intelligent Code Exclusions (`C-SENS-02`) and Framework
Native Understanding (`B-INTL-02`). Keying on the ID would freeze one and silently hide the other.

**Ratcheted, not enforced retroactively.** The three violations present when this shipped are on
delivered entries, which `finished-stories-immutable` forbids editing; two are `TECH-038`'s and
`TECH-017`'s own subjects. So they are frozen with a named owner and a reason, and only NEW ones
block. Same shape as the complexity, class-health, suppression and duplication ratchets.

Usage:
    python scripts/check_proof_tier.py            # judge the tree against the baseline
    python scripts/check_proof_tier.py --list     # print every violation, frozen or not
    python scripts/check_proof_tier.py --freeze   # rewrite the baseline (requires a reason edit)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Reading the proof field is shared with `check_story_preconditions.py` — both used a character
#: window and both under-verified because of it. `TECH-017`; see `_proof_field.py`.
_spec = importlib.util.spec_from_file_location(
    "_proof_field", Path(__file__).parent / "_proof_field.py"
)
assert _spec is not None and _spec.loader is not None
_proof_field = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_proof_field)
proof_segment = _proof_field.proof_segment
CONTRACTS = REPO_ROOT / "docs" / "roadmap" / "topics" / "topic_08_integration"
DESIGNS = REPO_ROOT / "docs" / "roadmap" / "features" / "topic_08_integration"
BASELINE = REPO_ROOT / "scripts" / "baselines" / "proof_tier.json"

#: Verdicts. `OK` is not a violation; the other two are.
OK = "ok"
UNIT_ONLY = "unit_only"
NO_TEST_FILE = "no_test_file"

#: A contract entry declares its ID in backticks, either as a `##` heading (the base contract) or
#: as a `*` bullet (an add-on). Capturing both in one pattern is what keeps add-ons from being
#: swallowed into the base contract's block.
_ENTRY = re.compile(r"^(?:##\s+(?P<h>.*?)|\*\s+\*\*(?P<b>.*?))\(`(?P<id>INT-US-[\w\-]+)`\)", re.M)

_STATUS = re.compile(r"\*\*Status:\*\*\s*(\S+)")

#: One Progress Tracker row. Columns after the id: Name | Depends On | Design | Impl Plan | Dev | …
_SF_ROW = re.compile(r"^\|\s*(SF-\d+)\s*\|([^\n]*)$", re.M)
_SF_DESIGN, _SF_DEV = 2, 4
_TEST_FILE = re.compile(r"tests/[\w/]+\.py")


@dataclass(frozen=True)
class Entry:
    """One contract entry: a base contract or a sub-story add-on."""

    source: str
    entry_id: str
    title: str
    delivered: bool
    proof: str

    @property
    def key(self) -> str:
        """File + title. **Not** the ID — `INT-US-05-SUB` names two different add-ons."""
        return f"{self.source} :: {self.title} (`{self.entry_id}`)"

    @property
    def verdict(self) -> str:
        return classify(self.proof)


def classify(proof: str) -> str:
    """Judge one Verifiable Proof segment.

    A proof naming both a unit test and an integration/e2e test passes: the ticket's rule forbids a
    contract proven *only* by unit tests, not the presence of a unit test.
    """
    paths = _TEST_FILE.findall(proof)
    if not paths:
        return NO_TEST_FILE
    tiers = {p.split("/")[1] for p in paths}
    return UNIT_ONLY if tiers <= {"unit"} else OK


def contract_entries(text: str, source: Path) -> list[Entry]:
    """Split one contract document into its entries, each with its OWN status and proof.

    Splitting first is the point. A single regex from `**Status:**` to `**Verifiable Proof:**`
    matches greedily across add-on boundaries, which credits one entry with a neighbour's proof —
    the first prototype of this checker reported 1 violation instead of 3 for exactly that reason.
    """
    matches = list(_ENTRY.finditer(text))
    entries: list[Entry] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[m.end() : end]
        status = _STATUS.search(block)
        proof = proof_segment(block)
        raw_title = (m.group("h") or m.group("b") or "").strip()
        title = raw_title.removeprefix("Base Story Contract").strip("* ").strip() or "Base Contract"
        entries.append(
            Entry(
                source=source.name,
                entry_id=m.group("id"),
                title=title,
                delivered=bool(status and "✅" in status.group(1)),
                proof=proof or "",
            )
        )
    return entries


@dataclass(frozen=True)
class Collision:
    """One identifier used by more than one entry in the same contract document."""

    source: str
    entry_id: str
    titles: list[str]


def duplicate_ids(text: str, source: Path) -> list[Collision]:
    """Identifiers naming more than one entry. `TECH-039`.

    An identifier that names two things identifies neither. `INT-US-05-SUB` named two different
    delivered add-ons, so `check_story_preconditions.py INT-US-05-SUB` resolved to whichever its
    regex reached first and could never check the other — and this module keys its own ratchet on
    file+title rather than ID precisely because of that entry.

    Status is deliberately ignored: a collision is a defect whether or not the entries shipped.

    NOT the same defect as the accepted `OQ-1` divergence, where one add-on carries a different
    identifier in two documents. Two names for one thing is unambiguous and stays legal here; one
    name for two things does not.
    """
    seen: dict[str, list[str]] = {}
    for entry in contract_entries(text, source):
        seen.setdefault(entry.entry_id, []).append(entry.title)
    return [
        Collision(source=source.name, entry_id=key, titles=titles)
        for key, titles in seen.items()
        if len(titles) > 1
    ]


def all_duplicate_ids() -> list[Collision]:
    found: list[Collision] = []
    for path in sorted(CONTRACTS.glob("US-*_integration.md")):
        found.extend(duplicate_ids(path.read_text(encoding="utf-8", errors="replace"), path))
    return found


def unbuilt_sub_features(entry_id: str, designs: Path = DESIGNS) -> list[str]:
    """Sub-features of `entry_id` that were **designed and never built** (Design ✅, Dev not ✅).

    `Design ✅ + Dev ⬜` is the signature of a broken promise, and the qualifier is load-bearing.
    Keying on `Dev ⬜` alone flags the four add-ons `ADR-003` RETIRED and one that is only pending
    design — legitimately unbuilt, and nothing was ever promised for them. Requiring a design first
    separates *we planned this and stopped* from *we decided not to*.

    A missing design doc yields `[]`: absence is not a promise.
    """
    design = designs / entry_id / f"{entry_id}_design.md"
    if not design.is_file():
        return []
    text = design.read_text(encoding="utf-8", errors="replace")
    unbuilt = []
    for sf_id, rest in _SF_ROW.findall(text):
        cells = [c.strip() for c in rest.split("|")]
        if len(cells) > _SF_DEV and cells[_SF_DESIGN] == "✅" and cells[_SF_DEV] != "✅":
            unbuilt.append(sf_id)
    return unbuilt


def all_broken_promises() -> list[tuple[str, list[str]]]:
    """`(entry_id, unbuilt_sfs)` for every DELIVERED base contract with a designed-but-unbuilt SF.

    This is the check that `INT-US-04` needed and nothing had: it read `✅ Complete` from 2026-07
    while the sub-feature implementing its Integration Description sat at Design ✅, Dev ⬜.

    It also covers a gap the correction OPENS. `violations_in` judges delivered entries only, so
    flipping a false `✅` to `⬜` makes the proof-tier check go quiet on that entry — and a check
    that silently stops running is indistinguishable from one that passes (`TECH-032`). This guard
    is what keeps a marker from being downgraded into silence.
    """
    found: list[tuple[str, list[str]]] = []
    for path in sorted(CONTRACTS.glob("US-*_integration.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for entry in contract_entries(text, path):
            if not entry.delivered:
                continue
            unbuilt = unbuilt_sub_features(entry.entry_id)
            if unbuilt:
                found.append((entry.entry_id, unbuilt))
    return found


def violations_in(text: str, source: Path) -> list[Entry]:
    """Only DELIVERED entries are judged — undelivered work does not yet owe a proof."""
    return [e for e in contract_entries(text, source) if e.delivered and e.verdict != OK]


def all_violations() -> list[Entry]:
    found: list[Entry] = []
    for path in sorted(CONTRACTS.glob("US-*_integration.md")):
        found.extend(violations_in(path.read_text(encoding="utf-8", errors="replace"), path))
    return found


def load_baseline() -> dict[str, dict[str, str]]:
    if not BASELINE.exists():
        return {}
    data: dict[str, dict[str, str]] = json.loads(BASELINE.read_text(encoding="utf-8"))
    return data


def _report_collisions() -> bool:
    """Print any identifier naming two entries. True if there were any.

    `TECH-039`: not ratcheted. There was exactly one collision, it is repaired, and an identifier
    naming two entries is never acceptable debt to freeze — unlike a weak proof, which can be
    true-but-thin while someone schedules the work.
    """
    collisions = all_duplicate_ids()
    if not collisions:
        return False
    print(f"Duplicate identifiers: {len(collisions)}\n")
    for c in collisions:
        print(f"  {c.source}: `{c.entry_id}` names {len(c.titles)} entries — {', '.join(c.titles)}")
    print(
        "\nAn identifier that names two things identifies neither: a story-scoped check "
        "resolves to whichever entry it reaches first and can never see the other. Give each "
        "entry its own id — the master roadmap usually already has them."
    )
    return True


def _report_broken_promises() -> bool:
    """Print any delivered contract with a designed-but-unbuilt sub-feature. True if there were any.

    `TECH-017`: not ratcheted, same reasoning as duplicate ids. A contract claiming to be finished
    while a designed sub-feature is unbuilt is never acceptable debt to freeze — the honest move is
    to correct the marker or build the sub-feature.
    """
    promises = all_broken_promises()
    if not promises:
        return False
    print(f"Contracts marked delivered with designed-but-unbuilt sub-features: {len(promises)}\n")
    for entry_id, sfs in promises:
        print(f"  {entry_id}: {', '.join(sfs)} — Design ✅ but never built")
    print(
        "\nA ✅ on a contract asserts the integration it describes is real. A sub-feature that "
        "was designed and never built means it is not. Correct the status marker or build the "
        "sub-feature — and if you correct the marker, say what IS delivered, because an "
        "undelivered entry stops being judged for proof tier at all."
    )
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--list", action="store_true", help="print every violation, frozen or not")
    ap.add_argument("--freeze", action="store_true", help="rewrite the baseline from the tree")
    args = ap.parse_args(argv)

    # A checker that cannot find its subject must say so, not pass. `TECH-032`'s lesson: an absent
    # toolchain reported as a clean run is a vacuous proof inside the gate itself.
    if not CONTRACTS.is_dir():
        print(f"could not run: contract directory not found: {CONTRACTS}", file=sys.stderr)
        return 2

    found = all_violations()

    if args.freeze:
        baseline = load_baseline()
        payload = {
            e.key: {
                "verdict": e.verdict,
                "reason": baseline.get(e.key, {}).get("reason", "TODO: state why this is frozen"),
            }
            for e in found
        }
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", "utf-8")
        print(f"froze {len(payload)} violation(s) into {BASELINE.relative_to(REPO_ROOT)}")
        return 0

    if args.list:
        for e in found:
            print(f"  {e.verdict:13} {e.key}")
        print(f"\n{len(found)} violation(s) total")
        return 0

    if _report_collisions():
        return 1

    baseline = load_baseline()
    if not baseline and found:
        print(
            f"could not run: {len(found)} violation(s) and no baseline at "
            f"{BASELINE.relative_to(REPO_ROOT)}. Run --freeze and give each a reason.",
            file=sys.stderr,
        )
        return 2

    new = [e for e in found if e.key not in baseline]
    if new:
        print(f"Proof-tier ratchet: {len(new)} NEW violation(s)\n")
        for e in new:
            what = (
                "cites only unit tests"
                if e.verdict == UNIT_ONLY
                else "cites no test FILE (a directory, a bare marker, or [Pending])"
            )
            print(f"  {e.key}\n      {what}")
        print(
            "\nAn INT-US story is an integration contract, so its proof must be integration or e2e "
            "tests naming real files. A unit test alongside them is fine; a unit test instead of "
            "them is not."
        )
        return 1

    print(
        f"Proof-tier ratchet: {len(found)} violation(s), none new. "
        "No duplicate identifiers, no unbuilt sub-features under a delivered contract."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
