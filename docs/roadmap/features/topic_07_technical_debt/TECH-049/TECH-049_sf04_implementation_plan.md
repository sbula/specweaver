# Implementation Plan: Mutation Campaign Corpus and Session Gate [SF-04: Machine Report]

- **Feature ID**: TECH-049
- **Sub-Feature**: SF-04 — Machine Report
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-04
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_sf04_implementation_plan.md
- **Status**: APPROVED

**FRs owned: FR-9.** Depends on: SF-03 (committed).

> **Proportionality.** One FR, one commit boundary. TDD, a killed mutant per claim, full gate.

## Scope

One JSON report, summary first, **self-contained**, plus the session entry point and its exit code.

## Research notes

| Fact | Evidence |
|---|---|
| **The leak is real, not theoretical.** A stale anchor raises `anchor not found in /tmp/sw-leak-jvmq7sif/src/specweaver/graph/lineage/scanner.py: '…'` | executed against a real sandbox |
| Sandbox paths reach `detail` from two places: `str(exc)` in `_run_mutant` (`mutation.py:295,297`) and `out[-800:]` in `run_one` (`_mutate.py:269`), which is raw pytest output carrying tracebacks | read |
| Node ids are already relative — pytest runs with `cwd=sandbox` and a relative target, so killers and baseline failures need no cleaning | executed in SF-02 |
| `render_report`'s ordering precedent: `SURVIVED` → `KILLED x1` → `BROKEN` → `KILLED`, worst first | read `_mutate_campaign.py:82-147` |
| `mutation.py` is 306 lines against a 451 YELLOW; `_corpus.py` already crossed it by accretion | `wc -l` |

## Decisions taken at the Phase 4 gate (Steve Bula, 2026-08-15)

| # | Decision |
|---|---|
| Q1 | **Sandbox paths are rewritten to repo-relative**, not replaced by a placeholder. The sandbox mirrors the repo, so `src/…/scanner.py` is both accurate and still useful; `<sandbox>/…` would throw away the only informative half. |
| Q2 | **Zero corpus files found is exit `2`, not `0`.** "Nothing to do" reported as success is the same false-green class this ticket has now fixed four times. |
| Q3 | **Corpus discovery globs `docs/roadmap/features/**/*_mutants.json`** — the filename is the contract, so the glob and the validator agree by construction. |
| Q4 | **Exit code ≠ gate.** The code reports run health; SF-06 reads the report and decides whether work continues. Confirmed, not re-opened. |
| Q5 | **The report lives in `scripts/_mutation_report.py`.** Splitting now rather than repeating `_corpus.py`, which crossed YELLOW by exactly this accretion. |

## Report shape

`.tmp/mutation_report.json` (gitignored), summary block first:

```
summary: head · dirty · verdict · baseline{collected,failed,green} ·
         counts{pass,fail,indeterminate,stale,broken} · declared · returned · not_run
campaigns[]: feature · requirement · verdict · mutants_declared · verdicts_returned ·
             results[]: derived_id · verdict · reason · drift · confirmed · killers · leaked · detail
```

**Nothing in it may point into the sandbox** — the worktree is deleted at the end of the run, so a
report that references it is unreadable by the time anyone acts on it.

## Exit codes

| Code | When |
|---|---|
| `0` | every campaign `PASSED` or `PARTIAL` |
| `1` | any campaign `FAILED` |
| `2` | could not run — no corpus files, a corpus that will not load, a sandbox that will not build |

## Commit boundary — CB-1

**Delivers:** `_mutation_report.py` (build the document, sanitise, serialise), `mutation.main()`
with discovery and exit codes.

**Tests:**
- *unit* — the summary block is first; counts match the results; a sandbox path in `detail` is
  rewritten to repo-relative; a report is emitted even when every campaign fails; exit `2` for no
  corpus files, for an unloadable corpus, and `1` vs `0` on verdicts.
- *integration* — **the seam**: a real session over a real corpus in a real sandbox, sandbox
  removed, then the report is loaded from disk and asserted to contain **no `/tmp/` path in any
  field**. Written here because the report is the interface that outlives the sandbox, and that
  claim is only falsifiable once the sandbox is gone.

**Done when** the sanitiser kills a mutant: neutralise the path rewrite and confirm the
no-`/tmp/`-in-the-report test goes red. That test is the whole of FR-9's "self-contained".

## Risks

| # | Risk | Mitigation |
|---|---|---|
| R-1 | Sanitising by string replace misses a path the sandbox spelled differently (symlinks, `/private/tmp`) | Assert on the *absence of any* `/tmp/` substring rather than on one known prefix — a broader claim that a near-miss still fails |
| R-2 | The report grows a field that is never sanitised | Sanitisation applied once at serialisation, over the whole document, not per-field at each call site |
| R-3 | `mutation.py` grows past YELLOW anyway | Report split out at 306; measured again at the close |

## Out of scope

The scheduler, the gate, the override census. SF-05 and SF-06.
