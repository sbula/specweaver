# Implementation Plan: The Morning Gate Marks Its Own Homework

- **Feature ID**: TECH-056
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-056/TECH-056_design.md
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-056/TECH-056_implementation_plan.md
- **Status**: APPROVED (2026-08-16)

**FRs owned: FR-1.** One commit boundary.

## CB-1 — the composed test first, then one expression

`tests/integration/scripts/test_mutation_gate_composition.py`, six tests, written before the fix
and **four of them red**. Then `gate_verdict` stops keying on presence:

```python
known = {id for id, entry in load_ledger(...)["findings"].items() if entry.get("disposition")}
```

That is the entire production change. The gate's own message — *"every finding carries a
disposition"* — was already the correct specification; the code checked something else.

### Proof, per tier

| Tier | What it proves | Where |
|---|---|---|
| unit | each half in isolation: an empty ledger blocks, a dispositioned entry clears, `runs` starts at 1 and increments, a departed finding is pruned | `tests/unit/scripts/test_mutation_gate.py` (22, pre-existing) |
| integration | `record_run` → `gate_verdict`, in the order `main` uses them | `tests/integration/scripts/test_mutation_gate_composition.py` (6, new) |
| e2e | — | none; see below |

**The unit tier is not the proof and could not have been.** Both halves passed every one of their
assertions for as long as the gate was incapable of blocking, because each test builds the ledger it
wants rather than letting the other half build one. The defect existed only in the handover, so the
integration test is the only tier where it can fail.

**No e2e.** `main`'s subprocess path is one `argparse` hop above these calls, and
`test_mutation_seam.py::TestReportLedgerGateChain` already drives `--gate` through it with an
explicit `--ledger`. An e2e here would re-run that with a different verdict and add no reach.

### Done when every mutant is killed

`TECH-056_mutants.json`:

| Mutant | Result |
|---|---|
| presence counts as having been read (the defect, restored) | KILLED ×4 |
| nothing ever counts as read | KILLED ×4 |
| a blocking finding is not named | KILLED ×9 |
| a confirmation forgets the recurrence count | KILLED ×3 |

The first two are deliberately a pair. One direction makes the gate silent forever; the other makes
it noisy forever, and a gate that re-blocks a confirmed finding every morning gets switched off just
as surely as one that never speaks. Both had to be killable before the fix could be called correct.

### Landed against a clean corpus, on purpose

Measured the same day: a full session over all four corpora returns **20/20 PASS, zero findings**, so
the gate reports `CLEAR` before and after this change. Turning on a gate that has never fired is
cheapest at the moment it has nothing to say — and re-running `mutation.py --gate` after the fix
confirms it, which is the only way to know the fix did not simply invert the silence.

## Out of scope

- **Proving that a fix worked.** `TECH-049` NFR-5 rejected that deliberately: it would mean an
  on-demand corpus run, and the next scheduled session re-measures anyway.
- **`INDETERMINATE` and `STALE` blocking.** Still non-blocking, for the reason the gate's docstring
  gives — neither is evidence that a requirement is unprotected.
- **The other two functions in `_mutation_gate.py`.** `confirm` and `record_run` were correct; the
  ticket changes what *reading* the ledger means, not what writing it does.
