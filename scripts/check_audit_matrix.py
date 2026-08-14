#!/usr/bin/env python
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The integration-contract proof matrix must stay a measurement, not decay into a snapshot.

`TECH-017` produced 64 claims with verdicts and evidence, and then had no way to prove it had. Its
six FRs name **"Auditor"** as the Actor — they describe a process and emit a document, so
`check_fr_coverage.py TECH-017` reported all six as `NO TEST` and blocked the ticket. That was the
right answer to the wrong question: the audit's outputs are checkable, just not as behaviour of
`src/`. This is where `FR-1`..`FR-4` and `FR-6` are owned.

Six rules, each a defect someone shipped:

1. **Every claim carries a recognised verdict** (`FR-2`) — prose where a verdict belongs is how an
   audit quietly loses a claim.
2. **Every `proven` names a tier or a test function** (`FR-2`, `FR-3`) — the audit's founding defect
   was file-level citation: 8 of `INT-US-21`'s 10 requirements credited to a file that asserted
   nothing about them.
3. **The header tally matches the table** (`FR-1`) — both were hand-maintained across four
   sub-features, and a header that drifts is a lie told at the top of the document.
4. **Claims never vanish, `unproven` never rises** (`FR-4`) — the count must fall *by work, not by
   re-wording*, which `NFR-1` forbids outright.
5. **Every cited proof file records a tier** (`FR-3`) — the gap `check_proof_tier` cannot see,
   because it reads the contract's own claim about its proof rather than the audit's reading of it.
6. **The capability-findings table exists and every row names the entry that surfaced it** (`FR-6`)
   — the diagnostic half of the audit, which is the half that goes missing.

`FR-5` (*escalate only decisions*) is deliberately **not** owned here. It constrains what the
auditor may file, and the artifact that would prove it is the absence of tickets — a historical
fact, not a document property. Claiming it from this file would be the loose credit the audit spent
three sub-features removing.

Rule 2 accepts a tier word **or** a test name rather than demanding a name. Five proven rows
legitimately read *"same test"* or *"the cited file"*, pointing at the row above; requiring a
function name there would force copy-paste, and whitelisting the prose would be brittle. Both
spellings were measured against the real matrix before choosing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MATRIX = REPO_ROOT / "docs" / "analysis" / "integration_contract_proof_matrix.md"
BASELINE = REPO_ROOT / "scripts" / "baselines" / "audit_matrix.json"

VERDICTS = ("proven", "unproven", "unprovable")

#: A claim row: `| C<n> | claim | verdict | evidence |`. Anchored on the id so the document's other
#: pipe tables — coverage, capability findings, the tally — are not swept in.
_CLAIM_ID = re.compile(r"C\d+")
#: The verdict cell opens with the word in backticks and may carry a qualifier after it
#: (`INT-US-24` C5 reads ``unproven` — **reason narrowed by SF-04**`).
_VERDICT = re.compile(r"`(" + "|".join(VERDICTS) + r")`")
_TIER = re.compile(r"\b(unit|integration|e2e)\b", re.IGNORECASE)
_TEST_FN = re.compile(r"test_\w+")

TIERS = ("unit", "integration", "e2e")
#: A per-entry proof row: `| `tests/...py` | e2e | 2 |`. The tier cell is `FR-3`'s whole point.
_PROOF_ROW = re.compile(r"^\|\s*`?(tests/[^|`]*)`?[^|]*\|\s*([^|]*?)\s*\|", re.MULTILINE)
#: `FR-6`'s consolidated table: `| `D-INTL-01` | finding | surfaced by | state |`.
_FR6_HEADER = "| Capability | Finding | Surfaced by | State |"
_FR6_ROW = re.compile(r"^\|\s*`([A-Z]-[A-Z]+-\d+)`\s*\|([^\n]*)$", re.MULTILINE)


@dataclass(frozen=True)
class Claim:
    """One claim row: its id, verdict and the evidence cell backing it."""

    claim_id: str
    verdict: str
    evidence: str


def matrix_text(path: Path = MATRIX) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def claim_rows(text: str) -> list[Claim]:
    """Every claim row in the document, in order. Rows that are not claims are skipped silently."""
    rows: list[Claim] = []
    for line in text.splitlines():
        if not line.startswith("| C"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not _CLAIM_ID.fullmatch(cells[0]):
            continue
        verdict = _VERDICT.match(cells[2])
        rows.append(
            Claim(
                claim_id=cells[0],
                verdict=verdict.group(1) if verdict else "",
                evidence=cells[3],
            )
        )
    return rows


def _header_tally(text: str) -> dict[str, int]:
    """The summary table at the top: `| \\`proven\\` | 51 |`. Missing rows are simply not checked."""
    tally: dict[str, int] = {}
    for verdict in VERDICTS:
        found = re.search(rf"^\|\s*`{verdict}`\s*\|\s*\*{{0,2}}(\d+)", text, re.MULTILINE)
        if found:
            tally[verdict] = int(found.group(1))
    return tally


def _claim_violations(rows: list[Claim]) -> list[str]:
    """FR-2: a recognised verdict, and a `proven` that names how it was proven."""
    found: list[str] = []
    for row in rows:
        if not row.verdict:
            found.append(f"{row.claim_id}: verdict is not one of {', '.join(VERDICTS)}")
        elif row.verdict == "proven" and not (
            _TIER.search(row.evidence) or _TEST_FN.search(row.evidence)
        ):
            found.append(
                f"{row.claim_id}: `proven` but the evidence names no tier and no test function"
            )
    return found


def _tier_violations(text: str) -> list[str]:
    """FR-3: an entry's proof table records the TIER of each proving file.

    This is the gap `check_proof_tier` cannot see, because it reads the contract's own claim about
    its proof rather than the audit's reading of it.
    """
    return [
        f"{path}: tier {tier!r} is not one of {', '.join(TIERS)}"
        for path, tier in _PROOF_ROW.findall(text)
        if tier.lower() not in TIERS
    ]


def _finding_violations(text: str) -> list[str]:
    """FR-6: capability findings are recorded against the capability, with what surfaced them.

    The diagnostic half of the audit, and the half that goes missing — so the table's existence is
    asserted rather than assumed.
    """
    if _FR6_HEADER not in text:
        return ["the FR-6 consolidated capability-findings table is missing"]
    found: list[str] = []
    for capability, rest in _FR6_ROW.findall(text):
        cells = [c.strip() for c in rest.split("|")]
        if len(cells) < 3 or not cells[1]:
            found.append(f"{capability}: FR-6 row names no entry that surfaced it")
    return found


def _tally_violations(text: str, rows: list[Claim]) -> list[str]:
    """FR-1: the header tally matches the table it summarises."""
    counted = {v: sum(1 for r in rows if r.verdict == v) for v in VERDICTS}
    return [
        f"header says {stated} `{verdict}` but the table holds {counted[verdict]}"
        for verdict, stated in _header_tally(text).items()
        if stated != counted[verdict]
    ]


def violations(text: str) -> list[str]:
    """Every rule broken by this document, as human-readable lines. Empty means clean."""
    rows = claim_rows(text)
    return [
        *_claim_violations(rows),
        *_tier_violations(text),
        *_finding_violations(text),
        *_tally_violations(text, rows),
    ]


def load_baseline(path: Path = BASELINE) -> dict[str, int]:
    if not path.exists():
        return {}
    data: dict[str, int] = json.loads(path.read_text(encoding="utf-8"))
    return data


def ratchet_failures(baseline: dict[str, int], claims: int, unproven: int) -> list[str]:
    """`FR-4`'s ratchet. Claims may only be ADDED; `unproven` may only FALL.

    Claims rising is work — the count rose twice during the audit as contracts were re-read in
    full. Claims falling means a row was deleted, which `NFR-1` forbids.
    """
    failures: list[str] = []
    if not baseline:
        return failures
    if claims < baseline.get("claims", 0):
        failures.append(
            f"claims fell from {baseline['claims']} to {claims} — a claim was deleted, "
            "and a delivered contract's claims are immutable (NFR-1)"
        )
    if unproven > baseline.get("unproven", 0):
        failures.append(
            f"unproven rose from {baseline['unproven']} to {unproven} — the count falls by "
            "work, not by re-wording (FR-4). A proof was lost or a verdict was downgraded"
        )
    return failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--matrix", default=str(MATRIX), help="path to the proof matrix")
    ap.add_argument("--freeze", action="store_true", help="rewrite the baseline from the tree")
    args = ap.parse_args(argv)

    path = Path(args.matrix)
    # `TECH-032`: a check that cannot find its subject must say so, not pass. The matrix moving or
    # being renamed would otherwise read as a clean run forever.
    if not path.is_file():
        print(f"could not run: proof matrix not found: {path}", file=sys.stderr)
        return 2

    text = matrix_text(path)
    rows = claim_rows(text)
    if not rows:
        print(f"could not run: no claim rows found in {path}", file=sys.stderr)
        return 2

    unproven = sum(1 for r in rows if r.verdict == "unproven")

    if args.freeze:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        payload = {"claims": len(rows), "unproven": unproven}
        BASELINE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"froze {payload} into {BASELINE.relative_to(REPO_ROOT)}")
        return 0

    broken = violations(text)
    if broken:
        print(f"Audit matrix: {len(broken)} violation(s)\n")
        for line in broken:
            print(f"  {line}")
        print(
            "\nA verdict without evidence naming a tier or a test function is the file-level "
            "citation this audit exists to remove."
        )
        return 1

    failures = ratchet_failures(load_baseline(), len(rows), unproven)
    if failures:
        print(f"Audit matrix ratchet: {len(failures)} regression(s)\n")
        for line in failures:
            print(f"  {line}")
        return 1

    print(f"Audit matrix: {len(rows)} claims, {unproven} unproven, all verdicts evidenced.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
