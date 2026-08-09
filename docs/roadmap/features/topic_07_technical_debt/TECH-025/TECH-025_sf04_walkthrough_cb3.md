# Walkthrough: TECH-025 SF-04 CB-3 — the ledger closes

- **Feature ID**: TECH-025 / SF-04 (TECH-001 FR Ledger)
- **Commit boundary**: CB-3 of 3 — SF-04 complete
- **Date**: 2026-08-09

## What changed and why

CB-2 answered *is the claim true?* This answers *is it linked?* — and turns TECH-001's ledger green.

| Change | Detail |
|---|---|
| TECH-001 design | SF-01's FRs `[FR-1, FR-2, FR-3]` → `[FR-1, FR-2, FR-3, FR-7, FR-8]` (TECH-025 FR-4) |
| TECH-001 SF-01 plan | Cites FR-1/2/3/7/8, each row naming the delivering section and the proving assertion |
| TECH-001 SF-02 plan | Cites FR-4/5, likewise |
| 3 store test files | A module docstring ending in a single `Proves: TECH-001 FR-N.` line |
| `test_architecture.py` | `llm_database_coupling` folded to one parse; three NFR-5 repairs (below) |

**The orphan adoption.** TECH-001's FR table had nine rows; its sub-feature map covered seven.
FR-7 and FR-8 belonged to nothing. SF-01 is their owner on the evidence, not by elimination: its
plan §4b describes exactly their work — stripping `settings.py` and `database.py` of control flow,
adding `interfaces/cli/settings_loader.py` and `interfaces/cli/_db_utils.py`, and modifying
`llm/router.py` and `llm/factory.py`. No scope was added to a delivered sub-feature.

Four delivered-story documents were edited. AD-4 authorises that for this ticket only; each carries
a dated note naming TECH-025 as the author, so the edit is visible rather than silent.

## The result

```
check_fr_coverage.py TECH-001   exit 0     <- SF-04's whole point
check_fr_coverage.py TECH-002   exit 1     <- required: SF-05 owns it
check_fr_coverage.py TECH-005   exit 1     <- required: SF-06 owns it
check_fr_coverage.py TECH-022   exit 1     <- required, and see below
check_fr_coverage.py INT-US-21  exit 0     <- SF-01's claim still holds
```

TECH-002 and TECH-005 staying blocked is a **pass**, not a gap: a citation in a shared test file
closing someone else's ledger is precisely the false-credit defect SF-01 existed to fix (plan Q6).

## W1 — the citations were probed, not just read

A citation is a claim that the test would fail if the behaviour regressed. Five of the eight were
written under CB-2 and probed there. The three adopted from existing tests had never been seen to
fail, so each got a planted defect:

| FR | Defect planted | Result |
|---|---|---|
| FR-1 | `name` NOT NULL dropped in `llm/store.py` | 1 failed ✅ |
| FR-2 | `model_id` default changed in `core/flow/store.py` | 1 failed ✅ |
| FR-3 | `root_path` UNIQUE dropped in `workspace/store.py` | 1 failed ✅ |

**The first FR-2 probe survived**, and that is kept in the record deliberately. Dropping `run_id`'s
NOT NULL changed nothing, nor did `event_type`'s — `test_flow_store.py`'s degradation case omits a
different required field. I had picked a constraint the test does not exercise and briefly held
evidence pointing the wrong way, which is the argument for running the probe rather than reasoning
about it. Two separate conclusions:

1. **FR-2's citation stands** — its claim is that a standalone store handles pipeline state, and
   the default-value probe shows the test reads that store's own models.
2. **That file's NOT NULL coverage is partial** (two of four columns). Not FR-2's claim and not
   this ticket's scope; recorded as a known gap rather than an undiscovered one.

## Phase 7.5 — a live false credit, in the file this boundary was citing

`test_architecture.py` contained `TECH-022` in a docstring sentence. The FR gate credits an FR to
**any** story whose ID appears in a test file alongside an `FR-N` token, so that one word was
crediting TECH-022 with FR-4 through FR-9. TECH-022's ledger still exits 1, so nothing closed on
it — but this is the SF-01 defect class, alive, in the file this ticket was adding citations to.

Two more NFR-5 violations came out with it: a registry ID in an **assertion message** and one in a
**comment** (the latter mine, written in CB-2). NFR-5 allows an ID only on the trailing `Proves:`
line. All three repaired; every `TECH-` occurrence across the four touched test files is now a
`Proves:` line, verified by enumeration.

The FR-9 docstring was rewritten to the convention in passing: it had stated its ticket and
requirement as prose ("TECH-001 SF-04 regression guard, proving FR-9") rather than as a tag.
Its credit survives through the new trailing line.

## Test results

| Tier | Scope | Paths | Result |
|---|---|---|---|
| unit | module | `tests/unit`, `tests/unit/core/flow`, `tests/unit/infrastructure/llm`, `tests/unit/workspace` | **5568 passed, 16 skipped** |

Four paths, unioned from four changed test files — CB-1's model working in the open.
`test_architecture.py`: 22 tests.

## Quality results

| Gate | Result |
|---|---|
| `quality.py cb` | 10 ok, 1 skip, 2 FAIL — `complexipy` 97, `cycles` 4 |
| `quality.py doc` | 3/3 ok |
| NFR-1 zero `src/` change | `git status --porcelain -- src/` → 0 lines |

Same two chronic `src`-scoped failures as CB-1 and CB-2, at the same recorded baselines.

## HITL gate decisions

| Gate | Presented | Decision |
|---|---|---|
| CB-2 → CB-3 | Asked explicitly before starting CB-3, since it is the only boundary editing delivered stories under AD-4's waiver | User: *"fold it into one parse in CB-3, then proceed"* |
| **Phase 2** | `TECH-025_sf04_precommit_review_cb3.md`: no violations; C1 (three citations adopted, never probed), C2 (nothing guards a deleted `Proves:` line — SF-07's job); story W1 | Proceeded under the standing instruction; W1 run, C1 closed |

The single-parse fold was a carried-over tidy-up the user asked for after reviewing CB-2 — two
`ast.walk` passes over an identical tree became one. Re-probed: reverting to the substring check
turns exactly the same one test red as before the fold, so the refactor neither widened nor
narrowed the check.

## Known follow-ups

- **C2 — nothing guards a deleted `Proves:` line.** That is SF-07's manifest and guard test, which
  depends on this boundary. Scheduled, not missed.
- **The selector case matrix** (SF-04 plan §Finding) — still open, still the closure ticket's work.
- **`test_flow_store.py`'s partial NOT NULL coverage** — see W1 above.

## Next

SF-05 (TECH-002) and SF-06 (TECH-005) — both unblocked, independent, parallelisable. Neither has an
implementation plan yet. SF-07 waits on both.
