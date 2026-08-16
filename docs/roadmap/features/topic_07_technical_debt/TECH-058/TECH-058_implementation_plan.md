# Implementation Plan: The Nightly's Baseline Forgot Its Own `-n auto`

- **Feature ID**: TECH-058
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-058/TECH-058_design.md
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-058/TECH-058_implementation_plan.md
- **Status**: APPROVED (2026-08-16)

**FRs owned: FR-1.** One commit boundary.

## CB-1

`tests/unit/scripts/test_baseline_parallelism.py`, five tests, two red before the change. Then
`run_baseline` appends `-n auto`.

### Proof, per claim

| Claim | Proven by | Tier |
|---|---|---|
| the baseline runs under xdist | `test_the_baseline_runs_under_xdist` | unit |
| the two whole-suite runners agree | `test_it_agrees_with_the_other_whole_suite_runner` | unit |
| NFR-1: a red baseline still reports its failures | `test_a_failing_baseline_is_still_reported` | unit |
| `tests=` is not displaced by the new flags | `test_the_target_is_still_configurable` | unit |

**Unit only, and not by default.** The seam is `run_baseline` building a command; the subprocess is
stubbed so the assertion is on what it built. An integration test would run the real suite to observe
a flag, and an e2e would do it again through `--corpus-dir` — both would cost minutes to re-measure
what this ticket already measured by hand, and neither could fail for a reason the unit test cannot.

**The agreement test is the one that matters.** The flag is easy to re-lose; what was actually absent
was any test comparing the two places that run the whole suite. It reads `_mutate.py`'s source for
its unscoped branch, so if that branch stops adding xdist the test says so rather than silently
agreeing with the new wrong answer.

### Done when every mutant is killed

`TECH-058_mutants.json`:

| Mutant | Result |
|---|---|
| the baseline drops back to serial | KILLED ×2 |
| a red baseline loses its failures | KILLED ×1 |

## Out of scope

- **Parallel mutant execution.** `TECH-057`, and now the larger half of the session.
- **The suite's own runtime.** 66.5s, already parallel; this ticket is about the sandbox copy of it.
