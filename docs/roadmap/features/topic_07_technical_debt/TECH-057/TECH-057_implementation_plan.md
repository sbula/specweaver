# Implementation Plan: TECH-057

- **Feature ID**: TECH-057
- **Status**: DELIVERED 2026-08-19
- **Commit boundaries**: one

## CB-1 — a pool, and the order kept

| Task | FR | Change |
|---|---|---|
| T1 | FR-1 | Split the loop body out of `run_corpus` so one mutant's cycle is callable on any sandbox |
| T2 | FR-1 | `_run_pooled`: K sandboxes on a free-queue, one per concurrent worker, capped by the work |
| T3 | FR-2 | Carry the index, re-sort at the end |
| T4 | FR-1 | `--workers`, defaulting to 4; the session keeps its own sandbox for the baseline |
| T5 | — | Time it on a real corpus and diff the verdicts, not just the exit code |

**T3 is not cosmetic.** Appending as futures complete orders the report by finishing time, which
makes two nights impossible to diff for a reason that has nothing to do with the code under test.

**T5 is the task that could have failed.** A pool that is faster and disagrees is worse than a serial
run; 8 mutants, identical verdicts, identical order, 46.3s to 18.4s.
