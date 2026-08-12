# Walkthrough: TECH-025 SF-07 — the guard, and the ticket's own ledger

- **Feature ID**: TECH-025 / SF-07 (Ledger Regression Guard)
- **Date**: 2026-08-12
- **Boundary**: CB-1, the only one. Widened at the Phase 4 gate to close TECH-025's own ledger.

## Result

```
check_fr_coverage.py TECH-025  ->  exit 0     all nine requirements planned and cited
TECH-001  0    TECH-002  0    TECH-005  0    INT-US-21  0    TECH-019  0
```

The last sub-feature. Every subject ledger is closed, the ticket's own ledger is closed, and a
guard now fails if any of them reopens.

## What changed

| File | Purpose |
|---|---|
| `scripts/baselines/fr_traceability_closed.txt` | The manifest — four ids, `#` comments allowed |
| `tests/unit/scripts/test_ledger_regression_guard.py` | 7 tests. FR-1, FR-2, FR-3, FR-4, FR-5 |
| `tests/unit/scripts/test_registry_id_conventions.py` | 9 tests. FR-6, FR-7, FR-8 |

## The constraint that shaped the whole design

TECH-025's ledger cited only FR-9, and every natural host for the rest already named another story.
Measured before choosing anything:

| Candidate host | Names | Consequence of tagging it |
|---|---|---|
| `test_architecture.py` | TECH-001 | would credit TECH-001 with **all eight** tokens |
| `test_check_conventions.py` | TECH-019 | would credit **TECH-019 FR-6** — a closed ledger, from a test proving nothing about it |
| `test_check_fr_coverage.py` | INT-US-21 | fixture-marked, so it can neither gain nor grant a citation |

So the citations had to live in files naming **TECH-025 and nothing else**, which forced two
decisions the plan would not otherwise have made.

**The story ids live in data, not in the test.** The scan reads `tests/**/*.py`; a manifest under
`scripts/baselines/` is neither, so it names the four freely while the guard reads them at run time.
That is not tidiness — it is the only way the guard can exist.

**FR-4 was generalised rather than abandoned.** Its acceptance is that TECH-001's design assigns its
two orphaned requirements to a sub-feature — but any test asserting that must locate
`TECH-001_design.md`, and *the path contains the story id*. Stated generally — *every requirement a
design declares is assigned to some sub-feature* — it is provable for every manifest entry with the
ids coming from data, and FR-4's specific claim is an instance. Verified true before being asserted:

```
TECH-001 declared 9 assigned 9    TECH-002 declared 6 assigned 6
TECH-005 declared 8 assigned 8    INT-US-21 declared 10 assigned 10
```

**The conventions fixtures name nothing at all.** R5 matches the *snake_case* spelling a filename
uses (`tech_\d{3}`), while the citation scan matches the canonical `TECH-NNN`. Different strings —
so `tech_999` triggers the rule while naming no story. The first draft used `SAMPLE-1`, which the
rule does not match, and the tests failed honestly rather than being weakened to fit.

## Proving the guard can fail

`test_the_gate_can_fail` asserts `main(["SAMPLE-404"]) != 0`. Without it, the loop over the manifest
could be comparing `0 == 0` against a gate that always succeeds — the vacuous-proof pattern this
entire ticket exists to remove, in the test written to prevent it. `test_the_manifest_lists_stories`
covers the other half: an emptied manifest would make every assertion iterate over nothing.

## One false credit caught in draft

The first version of the conventions module built its citation-tag fixture with a literal `FR-2`,
which would have credited **TECH-025 FR-2** — "close TECH-002's ledger" — from a file that proves
nothing of the sort. Assembling the tag through the `_token()` helper removed it. The self-guard
would have caught it, and did.

## Gates

| Gate | Result |
|---|---|
| `check_fr_coverage.py TECH-025` | **exit 0** — nine of nine |
| All four manifest entries | 0 |
| `TECH-019` | 0, and gained no citation |
| `quality.py cb` | 9 passed; `complexipy` and `cycles` chronic (`TECH-023`/`TECH-024`) |
| unit / integration / e2e | 5620·1 / 578·13 / 182·9 |

`TECH-021` and `TECH-022` still exit 1. Verified pre-existing against a stashed clean HEAD; neither
is a subject of this ticket, and the new files name only TECH-025 so they cannot have affected them.

The 23 test failures are unchanged and accounted for: 18 `TECH-029`, 4 Cluster E tooling, 1
`TECH-030` held red deliberately.
