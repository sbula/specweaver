#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Ratchet the number of *behavioural* NFRs cited by no test. `TECH-017`.

The FR ledger has been swept since `TECH-047`. NFRs never were: measured 2026-08-13, **no script in
this repo contained the string `NFR` at all**, while 235 of them sat in 50 design documents and 49
test files carried 62 NFR attributions nobody read. Roughly a third of the declared requirement
surface — and the third holding the security, isolation and performance claims — was exempt from
the closure contract's "every requirement proven by a test".

**Ratcheting the raw number would have been wrong.** 224 NFRs on delivered stories, 37 cited, 187
uncited — but the population is not homogeneous, and demanding a pytest citation for the rows below
would have manufactured exactly the fake proof this repo keeps rejecting:

| Row | Why a pytest is the wrong instrument |
|---|---|
| `C-FLOW-05` NFR-1 — *"`llm/` must remain an adapter and forbid `loom/*`"* | `tach check` proves it |
| `E-EXEC-01` NFR-6 — *"module <= 300 lines"* | the `file_sizes` gate proves it |
| `TECH-025` NFR-3 — *"every `Proves:` tag names a test that would fail"* | a rule about tests |
| `D-VAL-04` NFR-2 — *"token reductions without decreasing accuracy"* | no threshold; unfalsifiable |

So a row is excused only by an explicit marker written into the design — `[proof: arch]`,
`[proof: meta]`, `[proof: none]` — and the sweep counts what remains. Two properties matter:

* **The excuse is visible.** It lives in the design next to the requirement, in review, in git
  history — not in a skip-list inside this file where nobody would ever read it.
* **The excuse is per row.** A marker on NFR-1 does not cover NFR-2. `TECH-039`'s lesson was that a
  tool routing around a defect has already paid for it; a bucket-wide exemption is that shape.

> [!IMPORTANT]
> **What this measures.** Attribution, exactly as `check_fr_sweep.py` does — whether some test cites
> the requirement, never whether it proves it. An increase is a real signal and blocks. A decrease
> is not evidence of quality: bulk-adding citations moves the number and improves nothing.
> Strength is only answerable by mutation testing (`A-VAL-03`).
>
> **Known blind spot, deliberately shared with the FR sweep.** A citation counts only in a file that
> NAMES the story, so a test attributing `NFR-1` without saying which capability is invisible here.
> That is `TECH-017` finding 6, and widening it in this checker alone would make the two sweeps
> disagree about what a citation is.

Usage:
    python scripts/check_nfr_sweep.py            # judge against the baseline
    python scripts/check_nfr_sweep.py --list     # per-design breakdown, worst first
    python scripts/check_nfr_sweep.py --marked   # what is excused, and under which bucket
    python scripts/check_nfr_sweep.py --freeze   # rewrite the baseline
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

_cit_spec = importlib.util.spec_from_file_location(
    "_citations", Path(__file__).parent / "_citations.py"
)
assert _cit_spec is not None and _cit_spec.loader is not None
_cit = importlib.util.module_from_spec(_cit_spec)
sys.modules["_citations"] = _cit
_cit_spec.loader.exec_module(_cit)

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES = REPO_ROOT / "docs" / "roadmap" / "features"
TESTS = REPO_ROOT / "tests"
BASELINE = REPO_ROOT / "scripts" / "baselines" / "nfr_uncited.json"
ROADMAP = REPO_ROOT / "docs" / "roadmap" / "master_story_roadmap.md"

#: Same delivered-only rule as the FR sweep: an unbuilt capability's requirements are correctly
#: uncited, and counting them would punish writing requirements down before building.
_DELIVERED = re.compile(r"`(?:✅|🟢)`?\s*\*\*([A-Z][\w-]*-\d+(?:-SF\d+)?):")

#: An NFR row in the 3-column table used by 47 of 49 designs, and the 2-column variants.
_NFR_ROW = re.compile(r"^\s*\|\s*\**(NFR-\d+)\**\s*\|(?P<body>.*)$", re.MULTILINE)

#: The explicit, in-design excuse. Bucket name is captured for `--marked`.
_MARKER = re.compile(r"\[proof:\s*(?P<bucket>arch|meta|none)\b")

_NFR = re.compile(r"\bNFR-\d+\b")

_SKIP_DIRS = {".venv", "__pycache__", ".git", "node_modules"}

#: Same declaration `check_fr_coverage.py` has always honoured, now honoured here too. A test *of a
#: requirement checker* names real stories and feeds them `NFR-N` strings as INPUT, which is
#: indistinguishable from a citation. Missing this was not theoretical: `test_check_nfr_sweep.py`
#: quotes `C-FLOW-05 NFR-1`, `E-EXEC-01 NFR-6`, `TECH-025 NFR-3` and `D-VAL-04 NFR-2` as worked
#: examples, and silently credited all four the day this sweep was written.
FIXTURE_DATA_MARKER = "# fr-coverage: fixture-data"
_MARKER_SCAN_LINES = 10


def is_fixture_data(text: str) -> bool:
    """Whether a file declares its requirement ids to be inputs rather than citations."""
    for line in text.splitlines()[:_MARKER_SCAN_LINES]:
        if line.rstrip() == FIXTURE_DATA_MARKER:
            return True
    return False


_KNOWN: frozenset[str] | None = None


def _known_stories() -> frozenset[str]:
    """Every id with a design directory, cached — shared rule with the FR sweep."""
    global _KNOWN
    if _KNOWN is None:
        _KNOWN = frozenset(d.parent.name for d in FEATURES.rglob("*_design.md"))
    return _KNOWN


def delivered_stories() -> set[str]:
    """Story ids the master roadmap marks delivered."""
    if not ROADMAP.is_file():
        return set()
    return set(_DELIVERED.findall(ROADMAP.read_text(encoding="utf-8", errors="replace")))


def behavioural_nfrs_from_text(text: str) -> list[str]:
    """Declared NFRs a test could prove — every row without a `[proof: ...]` marker."""
    out: list[str] = []
    for match in _NFR_ROW.finditer(text):
        if _MARKER.search(match.group("body")):
            continue
        nfr = match.group(1)
        if nfr not in out:
            out.append(nfr)
    return out


def marked_nfrs_from_text(text: str) -> dict[str, str]:
    """`NFR-N -> bucket` for the rows excused in this design."""
    found: dict[str, str] = {}
    for match in _NFR_ROW.finditer(text):
        marker = _MARKER.search(match.group("body"))
        if marker:
            found.setdefault(match.group(1), marker.group("bucket"))
    return found


def cited_nfrs_in_tests(tests_root: Path, story: str) -> set[str]:
    """NFRs cited by a test file that NAMES the story — the FR sweep's rule, kept in step."""
    cited: set[str] = set()
    if not tests_root.is_dir():
        return cited
    for path in sorted(tests_root.rglob("*.py")):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if story not in text or is_fixture_data(text):
            continue
        # Same rule as the FR sweep: a `Proves:` tag is exhaustive for the story it names.
        cited |= {
            r
            for r in _cit.credited_requirements(text, story, _known_stories())
            if r.startswith("NFR-")
        }
    return cited


def uncited_from(text: str, cited: set[str]) -> int:
    """How many of this design's behavioural NFRs no test cites."""
    return len(set(behavioural_nfrs_from_text(text)) - cited)


def _design(story: str) -> Path | None:
    return next(FEATURES.rglob(f"{story}/{story}_design.md"), None)


def census() -> dict[str, int]:
    """`story -> uncited behavioural NFR count`, for DELIVERED stories with a gap."""
    delivered = delivered_stories()
    found: dict[str, int] = {}
    for design in sorted(FEATURES.rglob("*_design.md")):
        story = design.parent.name
        if story not in delivered:
            continue
        text = design.read_text(encoding="utf-8", errors="replace")
        if not behavioural_nfrs_from_text(text):
            continue
        count = uncited_from(text, cited_nfrs_in_tests(TESTS, story))
        if count:
            found[story] = count
    return found


def load_baseline() -> int:
    if not BASELINE.exists():
        return 0
    data: dict[str, int] = json.loads(BASELINE.read_text(encoding="utf-8"))
    return int(data.get("uncited_nfrs", 0))


def _print_marked() -> None:
    rows: list[tuple[str, str, str]] = []
    for design in sorted(FEATURES.rglob("*_design.md")):
        for nfr, bucket in marked_nfrs_from_text(
            design.read_text(encoding="utf-8", errors="replace")
        ).items():
            rows.append((design.parent.name, nfr, bucket))
    for story, nfr, bucket in sorted(rows, key=lambda r: (r[2], r[0], int(r[1].split("-")[1]))):
        print(f"  {bucket:<5} {story:<12} {nfr}")
    print(f"\n{len(rows)} NFR(s) excused by an explicit in-design marker")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="per-design breakdown, worst first")
    ap.add_argument("--marked", action="store_true", help="what is excused, and under which bucket")
    ap.add_argument("--freeze", action="store_true", help="rewrite the baseline")
    args = ap.parse_args(argv)

    # A checker that cannot find its subject must say so, not pass — `TECH-032`'s lesson.
    if not FEATURES.is_dir():
        print(f"could not run: features tree not found: {FEATURES}", file=sys.stderr)
        return 2

    if args.marked:
        _print_marked()
        return 0

    live = census()
    total = sum(live.values())

    if args.freeze:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(
            json.dumps({"uncited_nfrs": total, "designs": len(live)}, indent=2) + "\n", "utf-8"
        )
        print(f"froze {total} uncited behavioural NFR(s) across {len(live)} design(s)")
        return 0

    if args.list:
        for story, count in sorted(live.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"  {count:3}  {story}")
        print(f"\n{total} uncited behavioural NFR(s) across {len(live)} design(s)")
        return 0

    frozen = load_baseline()
    if total > frozen:
        print(
            f"NFR sweep: {total} uncited behavioural NFR(s), was {frozen} — "
            f"REGRESSION of {total - frozen}\n"
        )
        for story, count in sorted(live.items(), key=lambda kv: (-kv[1], kv[0]))[:10]:
            print(f"  {count:3}  {story}")
        print(
            "\nAn NFR with no test is a promise nothing checks — and NFRs are where the security, "
            "isolation and performance claims live. Four legitimate answers, one that is not:\n"
            "  * write the test;\n"
            "  * delete the NFR row, so the descope is visible;\n"
            "  * mark it `[proof: arch|meta|none]` in the design IF a pytest is genuinely the wrong "
            "instrument — and say which gate proves it instead;\n"
            "  * cite an existing test — but ONLY after reading it and confirming it proves this "
            "requirement.\n"
            "  * NOT: marking a row `[proof: none]` to make this number fall. That is the same "
            "gaming as a bulk citation, with an audit trail pointing at you."
        )
        return 1

    print(f"NFR sweep: {total} uncited behavioural NFR(s) across {len(live)} design(s), none new")
    return 0


if __name__ == "__main__":
    sys.exit(main())
