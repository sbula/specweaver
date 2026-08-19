# Design: The Nightly Runs Its Mutants One at a Time

- **Feature ID**: TECH-057
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DELIVERED 2026-08-19
- **Origin**: 2026-08-16, from measuring the corpus after `TECH-056`.
- **Re-scoped same day**: filed unscheduled, then **scheduled** when the coverage goal was stated —
  *every (N)FR that makes sense goes into the nightly*. That turns this ticket's trigger from a
  contingency into a date.

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

## Why it is now scheduled

It was filed unscheduled on the reasoning that the nightly had hours of slack. **The stated goal
removed that assumption**: every (N)FR that makes sense is to go into the nightly, so the corpus is
no longer a handful of campaigns written when someone happens to call a claim proven — it has a
destination, and the destination is measured.

| | measured 2026-08-16 |
|---|---|
| FRs declared today | 402 |
| behavioural NFRs (mutatable) | 177 |
| NFRs that **cannot** carry a mutant — `meta` 41, `arch` 28, `none` 10 | 79 |
| **mutatable today** | **579 of 658 — 88%** |
| capabilities delivered | 61 of 135 |
| **mutatable at full roadmap** (~1,040 declared x 88%) | **~918** |
| x 2.7 mutants per requirement | **~2,480 mutants** |

Serial, at today's scope mix of 5.4s per mutant: **~3.7 hours**. Disciplined to unit and integration
scopes at 1.3s: **~54 minutes**. The nightly starts at 03:00, so the first figure lands at 06:42 —
survivable, but with the whole margin spent and `STALE_AFTER_HOURS = 48` meaning an overrun goes
unreported for two days.

**`TECH-058` changed the shape of the problem and is why this is worth doing properly.** The
baseline was 291s of a 420s session; it is now 77s. Mutants were 31% of the session and are now 63%,
and that share only grows with the corpus. Parallelism now addresses the majority of the cost rather
than the minority.

**Two levers, and they are not alternatives.** Scope discipline is free and takes ~3.7h to ~54min;
a pool of eight takes ~3.7h to ~28min. Doing both is how the nightly stays under an hour at full
coverage without anyone having to think about it again.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Mutants run across a pool | `run_corpus` | builds one sandbox per concurrent worker and hands each a free one | the nightly overlaps the 1.2–16s measurement of each mutant instead of adding them up, while each mutant still owns its worktree |
| FR-2 | The report is unchanged | `run_corpus` | carries each mutant's index through and re-sorts at the end | results arrive in corpus order, so two nights stay diffable — completion order would reorder the report for reasons unrelated to the code |

## Measured, before and after

Approach 1 as filed: a pool of K sandboxes, the per-mutant mutate/measure/revert cycle untouched.

Timed 2026-08-19 on a real corpus (`TECH-054`, 2 campaigns, 8 mutants):

| | |
|---|---|
| `--workers 1` (the historical path) | **46.3 s** |
| `--workers 4` | **18.4 s** |

**2.5x, with identical verdicts in identical order** — compared campaign by campaign and mutant by
mutant, not inferred from the exit code.

Approach 2 (one sandbox per mutant) was not taken: it is strictly better isolation and the pool
already gives each *concurrent* mutant its own worktree, which is the property that mattered. Approach
3 (shrink the work instead) is not an alternative and remains the cheaper lever — scope discipline
takes full coverage from ~3.7 h to ~54 min on its own, and this multiplies with it rather than
replacing it.

## Why the default is 4 and not the core count

Each worker runs a **scoped pytest**, so the pool competes with pytest's own parallelism rather than
adding to it, and the win is overlapping each mutant's measurement rather than saturating the box.
Four is the conservative end of that; `--workers` exists for the other end, and `--workers 1` is the
old behaviour exactly.

**The session keeps its own sandbox for the baseline.** That is one full-suite run with nothing to
parallelise, and reusing it for mutants would hand the same worktree to several workers — the overlap
the single-sandbox design existed to prevent.

## Verifiable Proof

| FR | Test |
|---|---|
| FR-1 | `tests/unit/scripts/test_mutation_session.py::TestRunCorpusInParallel` — a sandbox handed out twice, or a pool of one, each fail. The cap test pins that two mutants never build eight worktrees |
| FR-2 | the same class — `test_results_stay_in_corpus_order`, and the serial/parallel equality test that is the point of the change |

## Candidate Approaches (as filed)

1. **A pool of K sandboxes.** `build_sandbox()` K times, hand each worker a free one, keep the
   per-mutant mutate/measure/revert cycle exactly as it is. Smallest change; each worker's scoped
   pytest is already serial, so K ~ cores.
2. **One sandbox per mutant.** Simpler still and strictly better isolation — `snapshot_cleanliness`
   and `leaked_since` exist because mutants leak into a shared tree — at 0.2s each, ~8 minutes of
   pure setup across ~2,480 mutants. Probably acceptable; measure before assuming.
3. **Do nothing; shrink the work instead.** Scope discipline alone takes full coverage from ~3.7 h
   to ~54 min, because an e2e-scoped mutant costs 8x a unit-scoped one. Recorded in
   `docs/dev_guides/writing_mutation_campaigns.md` and the cheaper lever by far.

## Non-Goals

- **Parallelising the pytest run inside a single mutant.** Scoped runs are small by construction; the
  parallelism worth having is across mutants.
- **Touching the baseline.** One full-suite run per session, fixed cost, and it does not scale with
  the corpus — `TECH-058` already took it from 291s to 77s.
- **Any change to `scope` semantics.** Approach 3 is a guidance change, not a mechanism.

## The open question, answered — and the hypothesis was wrong

This section originally read: *the leading hypothesis is that the baseline runs the suite in a cold
sandbox with no `__pycache__`.* Measured, in one sandbox, three runs: serial **291.2s**, warm serial
**291.7s**, `-n auto` **77.3s**. Cold bytecode cost **+0.5s**. The cause was a missing `-n auto`,
fixed by **`TECH-058`**.

Kept rather than deleted, because the lesson is the ticket's own: a plausible cause was written into
a design document and would have been inherited by whoever picked this up. The probe that settled it
took one command.

## Next Step

**Scheduled, ordered behind scope discipline.** Approach 3 — shrinking the work — is free, already
shipped as guidance in `docs/dev_guides/writing_mutation_campaigns.md`, and worth letting run for a
while: if campaigns land at unit and integration scope, the pool buys minutes rather than hours and
this ticket can stay small.

Re-measure before designing. Every number here is from 2026-08-16, when the corpus held **26 mutants
across 10 of 579 mutatable requirements — 1.7% of the destination.** The scope mix of the next fifty
campaigns will move these projections more than any implementation choice made now.
