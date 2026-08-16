# Design: The Nightly Runs Its Mutants One at a Time

- **Feature ID**: TECH-057
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: 2026-08-16, from measuring the corpus after `TECH-056`. **Deliberately unscheduled** —
  filed to record a design decision while it is still cheap to change, not to be picked up now.

## Problem Statement

`run_corpus` says it plainly: *"one sandbox reused across all of them."* Every mutant is written into
the same worktree, measured, and reverted, so mutants **cannot** overlap. That is the only reason
the nightly is serial.

Measured 2026-08-16, 24 mutants across five corpora:

| | |
|---|---|
| whole corpus, serial | **129.5s** |
| unit / integration scoped | 1.2 – 1.6 s per mutant |
| e2e scoped | 9.9 – 16.1 s per mutant |
| **sandbox build + teardown** | **0.2 s** |

That last number is the finding. A pool of eight sandboxes costs **1.6 seconds** to stand up, so
nothing about the current design is defending an expensive resource — the serialisation is
incidental to how the code was written, not a constraint anybody chose.

## Why it is not being built yet

Today the nightly finishes in about seven minutes against a window of several hours. Building a
sandbox pool now would optimise the one clock in this repo with real slack, and `TECH-055` already
removed the cost that was actually being paid, in the suite, at every commit boundary.

**What is being recorded instead is the trigger.** 670 (N)FRs are declared today, 61 of 135
capabilities are delivered, and full roadmap is roughly 1,000-1,400 requirements. At today's ratio of
2.7 mutants per requirement and today's scope mix, full coverage is **~4.9 hours serial**. The
nightly starts at 03:00, so that finishes at 07:54 with no margin — and `STALE_AFTER_HOURS = 48`
means a session that overran would not be reported as stale for two days.

**Pick this up when the nightly's own wall clock passes about two hours**, or sooner if a session is
ever observed still running at 08:00. Retrofitting a pool costs the same work at any size; what
grows is the number of campaigns whose verdicts have to be re-validated afterwards.

## Candidate Approaches (not yet designed)

1. **A pool of K sandboxes.** `build_sandbox()` K times, hand each worker a free one, keep the
   per-mutant mutate/measure/revert cycle exactly as it is. Smallest change; each worker's scoped
   pytest is already serial, so K ~ cores.
2. **One sandbox per mutant.** Simpler still and strictly better isolation — `snapshot_cleanliness`
   and `leaked_since` exist because mutants leak into a shared tree — at 0.2s each, ~11 minutes of
   pure setup across 3,240 mutants. Probably acceptable; measure before assuming.
3. **Do nothing; shrink the work instead.** Scope discipline alone takes full coverage from ~4.9 h
   to ~70 min, because an e2e-scoped mutant costs 8x a unit-scoped one. Recorded in
   `docs/dev_guides/writing_mutation_campaigns.md` and the cheaper lever by far.

## Non-Goals (proposed, pending design)

- **Parallelising the pytest run inside a single mutant.** Scoped runs are small by construction; the
  parallelism worth having is across mutants.
- **Touching the baseline.** It is one full-suite run per session, fixed cost, and does not scale
  with the corpus.
- **Any change to `scope` semantics.** Approach 3 is a guidance change, not a mechanism.

## Open question this ticket does not answer

The full session measured **6m51s**, but 129.5s of mutant work plus a 67s baseline is only ~3m15s.
The leading hypothesis is that the baseline runs the suite in a **cold sandbox** with no
`__pycache__`, so it costs far more there than in the working tree. Unverified. It does not affect
the scaling argument — the baseline is a fixed one-off — but whoever picks this up should measure it
before trusting any per-part budget.

## Next Step

None scheduled. Re-measure before designing: both the trigger above and the numbers in this document
are from 2026-08-16, when the corpus held 24 mutants across 9 of 670 requirements.
