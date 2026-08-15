# Implementation Plan: Mutation Campaign Corpus and Session Gate [SF-02: Session Baseline and Scoped Execution]

- **Feature ID**: TECH-049
- **Sub-Feature**: SF-02 — Session Baseline and Scoped Execution
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_sf02_implementation_plan.md
- **Status**: APPROVED

**FRs owned: FR-3, FR-4, FR-7.** Depends on: SF-01 (committed).

> **Proportionality.** This is dev tooling in `scripts/`, not a shipped capability. Two commit
> boundaries, no dev guide, no walkthrough unless something surprising turns up. The rigour that
> stays: TDD, a killed mutant per claim, and the full gate before each commit.

## Scope

Run the suite once per session to lay the baseline, then run each mutant against its campaign's
declared scope in a sandbox that is clean between mutants. **Produces raw results — no verdicts.**
Classification is SF-03's.

## Research notes

Measured against real pytest, not recalled.

| Fact | Evidence |
|---|---|
| Exit codes are a contract: `0` ok · `1` tests failed · `2` interrupted · `3` internal · `4` usage error · `5` nothing collected | executed all four reachable cases |
| **A bad `--tests` path exits 4 and prints `no tests ran`** — no `FAILED` line, so the runner reads it as `SURVIVED` | executed |
| **Everything deselected exits 5 and prints `N deselected`** — same false survival | executed |
| `_run()` returns `stdout + stderr` and **discards the exit code**; 11 call sites | read `_mutate.py:139-142` |
| `run_one()` restores the file itself in a `finally` since `103d7998`; `reset_file` is gone | read `_mutate.py:208-243` |
| `_build_sandbox` **copies untracked files into the sandbox**, so a fresh sandbox is never `git status --porcelain` empty | read `_mutate.py:145-168` |
| `killers()` already yields node ids — the baseline's failing-test list needs nothing new | read `_mutate.py:112-116` |
| `_corpus.load_corpus()` → `Corpus.campaigns[].{requirement, scope, mutants}` | read `_corpus.py` |

## Decisions taken at the Phase 4 gate (Steve Bula, 2026-08-15)

| # | Decision |
|---|---|
| Q1 | **Exit code decides the verdict.** `FAILED` lines are still parsed, but only to learn *which* tests died — the in-scope-killer rule needs that. Text stops being load-bearing for classification, which is what the colour bug broke. New `_run_rc()` returns `(output, code)`; `_run` is untouched so the other call sites do not move. |
| Q2 | **`_mutate_campaign.py` stays.** The ad-hoc form answers a throwaway question mid-investigation — used six times in one session. The corpus runner is a second entry point, not a rewrite. |
| Q3 | **`scripts/mutation.py`** — bare name like `quality.py` and `tests.py`, because a person and later a timer invoke it. The `_`-prefixed files remain its building blocks. |
| Q4 | **Cleanliness is measured against a post-build snapshot**, not against empty. A correction to the design's FR-7 wording, which assumed a clean tree that `_build_sandbox` never produces. |
| Q5 | **A dirty sandbox is cleaned, the run continues, and the leak is recorded** against the mutant that caused it. Aborting turns one leaky test into a night with no data. |
| Q6 | **The seam test lands at CB-1**, where the interface exists and the behaviour does not — not parked at the end. |

## Shape

`scripts/mutation.py`, consuming `_corpus` and `_mutate`:

```
run_session(corpus_files, root) ->
    build ONE sandbox
    snapshot cleanliness
    baseline: full suite, record collected/failed/failing-node-ids
    for each campaign, for each mutant:
        run_one scoped to campaign.scope
        classify by EXIT CODE, collect killers from output
        assert sandbox still matches the snapshot; clean and record if not
    return raw results
```

## Commit boundaries

### CB-1 — Exit-code plumbing and the seam

**Delivers:** `_run_rc()` in `_mutate.py`; `run_one` returning the exit code and collected state
alongside its existing keys; `scripts/mutation.py` with the sandbox + baseline.

**Tests:**
- *unit* — `_run_rc` surfaces the code; a run that collects nothing is distinguishable from one
  where everything passed. Four exit codes, four outcomes.
- *integration* — **the seam, written here**: a real `Corpus` from SF-01 drives `run_one` in a real
  sandbox against a real test file. Red before `mutation.py` exists, green after. This is the first
  boundary where `_corpus` and `_mutate` meet, and per `ADR-003` no later story writes it.

**Done when** the zero-collection guard kills a mutant: neutralise the exit-code check and confirm
the mis-typed-scope test goes red. That guard is the whole point of FR-4.

### CB-2 — Scoped execution and sandbox hygiene

**Delivers:** per-mutant scoped runs across a whole corpus; the post-build cleanliness snapshot,
the between-mutant check, and the clean-and-record path.

**Tests:**
- *unit* — cleanliness compares against the snapshot, not empty; a leaked file is detected, cleaned
  and recorded; accounting holds (N mutants declared, N results returned) when a leak happens.
- *integration* — two mutants in one sandbox, the first deliberately leaking a file, and the second
  still measured correctly. This is the regression guard for the class of bug `103d7998` fixed.

**Done when** the hygiene check kills a mutant: neutralise the snapshot comparison and confirm the
leak test goes red.

## Risks

| # | Risk | Mitigation |
|---|---|---|
| R-1 | The integration tests build real worktrees and are slow | Scope them to one tiny test file, not the suite. SF-01's measurement says a scoped mutant is ~1.2 s |
| R-2 | Exit-code classification silently changes `_mutate.py`'s CLI behaviour | `run_one`'s existing keys stay; the code is **added**, not substituted. Existing tests pin the old contract |
| R-3 | `_corpus.py` is 458 lines, past YELLOW | SF-02 adds nothing to it. If it must, the CLI splits out first |
| R-4 | The baseline is slow enough that iterating on SF-02 is painful | The baseline is a parameter — tests inject a tiny path; only the real session runs the full suite |

## Delivered

Both boundaries committed. Six mutants, all KILLED. Full suite 7042 passed, 0 failed.

**Deviations from this plan, recorded rather than folded in:**

- CB-1's done-when exposed a bug in CB-1's own code: `run_one` appended a multi-path test target as
  one argv element, so any campaign with more than one `scope` file measured nothing while
  reporting cleanly. Fixed with a regression test inside the same boundary.
- `FR-7`'s design wording ("verify `git status --porcelain` is empty") is unachievable, as Q4
  anticipated. Implemented against a post-build snapshot; only additions count as leaks.
- The `FR-7` tests were written without a `Proves:` tag, so `check_fr_coverage` reported `NO TEST`
  while three tests proved it. Caught at the closing gate.

## Out of scope

Verdicts, the in-scope-killer rule, `INDETERMINATE`, the report, the scheduler, the gate. SF-03
onward. SF-02 produces raw results and decides nothing.
