# Implementation Plan: Registry IDs Leaking Into Proofs [SF-07: Ledger Regression Guard]

- **Feature ID**: TECH-025
- **Sub-Feature**: SF-07 — Ledger Regression Guard
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-07
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_sf07_implementation_plan.md
- **Status**: APPROVED (user, 2026-08-12 — all three Phase-4 recommendations taken; SF-07 widened to close TECH-025's own ledger)

> Bare `FR-N` below means **TECH-025's own** requirement. Every other story's is written qualified.
> This sub-feature is the one where that distinction decides the design, not just the prose.

## Overview

All three subject ledgers are closed — `TECH-001` (SF-04), `TECH-002` (SF-05), `TECH-005` (SF-06).
Nothing stops them reopening. This sub-feature records them in a manifest and fails a test if any
does.

**FRs**: FR-5 (guard the closed ledgers) — **widened at the Phase 4 gate to FR-1…FR-8**, i.e. to
closing TECH-025's own ledger. R5 showed nothing comes after SF-07 and no natural host exists, so
"the closure step will handle it" would have meant nobody.

## Research Notes

**R1 — `main(argv)` is a usable entry point.** `check_fr_coverage.main` takes `argv` and **returns**
an int; `sys.exit(main())` happens only under `__main__`. A guard test can call
`main([story]) == 0` in-process, with no subprocess and no `tach`-on-PATH fragility of the kind that
made `test_tach_architectural_boundaries` fail silently this session.

**R2 — The manifest must live outside `tests/`, and that is what makes the whole design work.**
The citation scan reads `tests/**/*.py`. A manifest at `docs/roadmap/fr_traceability_closed.txt` is
neither, so it can name `TECH-001`, `TECH-002`, `TECH-005` and `INT-US-21` freely. The guard test
reads the IDs **at runtime** and never contains one as a literal.

This is not stylistic. It is the only way the guard can exist at all — see R3.

**R3 — The trap, quantified. This is the sub-feature where SF-05's finding becomes a design
constraint rather than a caution.**

TECH-025's own ledger cites **only FR-9**. Closing it means citing FR-1…FR-8 from files that name
`TECH-025` — and every natural host already names another story:

| Candidate host | Names | Consequence of adding TECH-025 + its tokens |
|---|---|---|
| `test_architecture.py` | `TECH-001` (FR-1…FR-9) | would credit TECH-001 with **all eight** of TECH-025's tokens |
| `test_check_conventions.py` | `TECH-019` (FR-1…FR-6) | would credit **TECH-019 FR-6**, a closed ledger, from a test that proves nothing about it |
| `test_check_fr_coverage.py` | `INT-US-21` (FR-1…FR-10) | marked fixture-data by SF-01, so it is skipped entirely — it can neither gain nor grant a citation |
| `test_fr_coverage_fixture_exclusion.py` | `TECH-025` only | safe, and already carries FR-9 |

**So TECH-025's citations can only live in files that name TECH-025 and nothing else.** There is
exactly one such file today.

**R4 — The guard genuinely proves three more requirements, not just FR-5.** Their acceptance
criteria are literally what it asserts:

| FR | Acceptance criterion in the design | The guard asserts |
|---|---|---|
| FR-1 | `check_fr_coverage.py TECH-001` exits 0 | `main([entry]) == 0` for that manifest entry |
| FR-2 | `check_fr_coverage.py TECH-002` exits 0 | same |
| FR-3 | `check_fr_coverage.py TECH-005` exits 0 | same |
| FR-5 | a manifest plus a test that runs the gate for each | the guard itself |

This is not tag-stuffing: a test that runs the gate for every closed ledger **is** the stated proof
of FR-1, FR-2 and FR-3. And it can carry those tokens honestly because the IDs come from the
manifest, so the file never names a subject story.

**R5 — What the guard cannot prove, and why.** FR-4, FR-6, FR-7 and FR-8 are outside its reach:

- **FR-4** (adopt TECH-001's orphaned FRs) — acceptance is that `TECH-001`'s design assigns FR-7/FR-8
  to its SF-01. Any test asserting that must locate `TECH-001_design.md`, and that path **contains
  the story ID**. There is no way to name the file without naming the story.
- **FR-6, FR-7** (renames, R5 across tiers) and **FR-8** (R6 class-naming ratchet) — all proven today
  by `test_check_conventions.py`, which names `TECH-019`.

These are the ticket's **closure** problem, not this sub-feature's scope. SF-07 declares only FR-5.
But nothing else is coming after SF-07, so the plan must say who solves it — see Q1.

**R6 — AD-5 as amended seeds four entries, not three.** `INT-US-21` joins `TECH-001`, `TECH-002` and
`TECH-005`. SF-01 removed citation credit that INT-US-21 was receiving from fixture data, and the
claim that it still closes on genuine proof "cannot be a pytest, because asserting it means naming
the story in a file that also carries an `FR-N` token, which would re-credit it." The manifest is
the only place that check can live permanently — which is R2 restated from the other direction, and
is why AD-5 was amended.

## Proposed Changes

### 1. `[NEW] scripts/baselines/fr_traceability_closed.txt`

One story ID per line, `#` comments allowed. Seeded with the four from AD-5. The file explains that
adding a line is how a future ticket records its own closure.

### 2. `[NEW] tests/unit/scripts/test_ledger_regression_guard.py`

Names **only** `TECH-025`. Reads the manifest, calls `main([entry])` per entry, asserts 0.

Carries `Proves:` tags for FR-1, FR-2, FR-3 and FR-5 per R4 — and **no subject-story literal**,
which a self-guard asserts. Same shape as SF-01's file and SF-05's and SF-06's, for the same reason.

## Test Plan

| # | Bucket | Story |
|---|---|---|
| T1 | Guard | The manifest exists, parses, and yields a non-empty entry list — an empty manifest would make the loop pass vacuously |
| T2 | Happy | Every entry in the manifest exits 0 |
| T3 | Boundary | Comments and blank lines are ignored; a `#` line is not treated as a story ID |
| T4 | Hostile | An unknown story ID in the manifest fails loudly rather than being skipped |
| T5 | Hostile | A story whose ledger is genuinely open returns non-zero — proves the guard can fail |
| T6 | Degradation | A missing manifest fails with a message naming the path, not a bare `FileNotFoundError` |
| T7 | Invariant | This file names one story and carries exactly the tokens it earns |

T5 is the load-bearing one. Without it the guard could be asserting `0 == 0` against a gate that
never fails, which is precisely the vacuous-proof pattern this whole ticket exists to remove.

## Verification

```bash
PY=.venv/bin/python
$PY -m pytest tests/unit/scripts/test_ledger_regression_guard.py -v --tb=short
$PY scripts/check_fr_coverage.py TECH-001   # 0
$PY scripts/check_fr_coverage.py TECH-002   # 0
$PY scripts/check_fr_coverage.py TECH-005   # 0
$PY scripts/check_fr_coverage.py INT-US-21  # 0
$PY scripts/check_fr_coverage.py TECH-019   # MUST stay 0 and gain no new citation
$PY scripts/quality.py cb
```

Attribution verified by file list, per the method SF-05 established.

## Commit Boundaries

**CB-1 — manifest and guard.** One boundary. Unlike SF-04/05/06 there is no citation half to
separate: the guard's `Proves:` tags are for requirements it genuinely asserts, so splitting would
mean committing a test that deliberately omits its own true citations.

## Open Questions for the Phase 4 Gate

| # | Question |
|---|---|
| Q1 ✅ | *Decided: (a) — widen SF-07.* **Who closes TECH-025's own ledger?** After SF-07, FR-4/6/7/8 remain uncited and R5 shows no natural host exists. Options: **(a)** widen SF-07 to add the missing proofs in new TECH-025-only files — honest but duplicates `test_check_conventions.py`'s coverage to satisfy an attribution rule; **(b)** do it as the ticket's closure step, same problem one document later; **(c)** descope FR-4/6/7/8 from the design's FR table, which the gate's own message invites — *"If an FR is genuinely out of scope, delete the row so the descoping is visible"* — but they are **not** out of scope, they were delivered. Recommend **(a)**, scoped tightly: assert the *rule behaviour* rather than re-test the checker. |
| Q2 ✅ | *Decided: in-process.* **Should the guard run the gate in-process or as a subprocess?** In-process via `main([story])` is fast and has no PATH fragility. A subprocess would prove the CLI entry point too. Recommend **in-process**: the CLI is one line (`sys.exit(main())`), and this session already watched a shell-out test fail for environmental reasons unrelated to its claim. |
| Q3 ✅ | *Decided: `scripts/baselines/`.* **Does the manifest belong under `docs/roadmap/` or `scripts/baselines/`?** The design says `docs/roadmap/`. `scripts/baselines/` already holds `test_class_naming.json` and `suppressions.json` — frozen data the gates read. Recommend **`scripts/baselines/`** for consistency, unless the design's placement was deliberate. Either satisfies R2. |

---

## Widened scope (Phase 4 gate, user 2026-08-12)

### FR-4 without naming `TECH-001` — generalise the claim

FR-4's acceptance is that `TECH-001`'s design assigns its two orphaned requirements to a
sub-feature. R5 showed no test can assert that directly, because the design's *path* contains the
story ID.

**The general form is provable and stronger:** for every entry in the manifest, every requirement
declared in its design is assigned to some sub-feature in that design. The story IDs come from the
manifest, so the file names none of them, and FR-4's specific claim is an instance of it.

Verified true before planning to assert it — the R4 discipline from SF-06:

```
TECH-001    declared= 9  assigned= 9  orphaned=NONE
TECH-002    declared= 6  assigned= 6  orphaned=NONE
TECH-005    declared= 8  assigned= 8  orphaned=NONE
INT-US-21   declared=10  assigned=10  orphaned=NONE
```

### FR-6, FR-7, FR-8 — assert the rule, not the checker

`[NEW] tests/unit/scripts/test_registry_id_conventions.py`, naming only `TECH-025`:

| FR | Asserts |
|---|---|
| FR-6, FR-7 | R5 rejects a registry ID in a test **filename, class name and function name**, in every tier, including the `_sf<N>` form |
| FR-8 | R6 rejects a unit test class naming no subject, and the frozen baseline exists |

**All fixtures use synthetic IDs** (`SAMPLE-1`, following SF-01's `TestMain` precedent). A real one
would credit that story from this file. This is deliberately *not* a re-test of
`test_check_conventions.py`'s internals: it asserts the rules' observable behaviour, which is what
FR-6/7/8 actually claim. The duplication is the price of the attribution rule, and it is noted here
rather than hidden.
