# Implementation Plan: Mutation Campaign Corpus and Session Gate [SF-03: Verdicts, Confirmation and Accounting]

- **Feature ID**: TECH-049
- **Sub-Feature**: SF-03 — Verdicts, Confirmation and Accounting
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_sf03_implementation_plan.md
- **Status**: APPROVED

**FRs owned: FR-3a, FR-5, FR-6, FR-8.** Depends on: SF-02 (committed).

> **Proportionality.** Dev tooling. Two commit boundaries, no dev guide, no walkthrough unless
> something surprising turns up. TDD, a killed mutant per claim, full gate before each commit.

## Scope

Turn SF-02's raw outcomes into verdicts. This is where the session finally **judges** — and where
`KILL` stops meaning "tests failed" and starts meaning "this requirement is protected", which are
not the same claim.

## Research notes

| Fact | Evidence |
|---|---|
| Killer node ids are `path::test_name`, so in-scope is plain file membership | executed `killers()` on a real line |
| `drift_of` exists and is **unused** by `mutation.py` — SF-03 wires it | `grep -c drift_of scripts/mutation.py` → 0 |
| An anchor that will not apply raises `ValueError` from `apply_mutation`, caught in `_run_mutant`, reported **`BROKEN`** | read `mutation.py:167-168`, `_mutate.py:94-109` |
| `run_one` already returns `code`, `killers`, `detail`; `MutantRun` carries `leaked` | read `_mutate.py`, `mutation.py` |
| `_citations.strict_citations(text) -> dict[str, set[str]]` | read `_citations.py:38-60` |
| `mutation.py` is 176 lines against a 451 YELLOW | `wc -l` |

## Decisions taken at the Phase 4 gate (Steve Bula, 2026-08-15)

| # | Decision |
|---|---|
| Q1 | **In-scope killer = the killer's file appears in `campaign.scope`.** Node ids are `path::test`; scope is a file list. Scope is authoritative, so membership is the whole test. |
| Q2 | **`STALE` has two sources and both map to it**: hash drift from `drift_of`, and an anchor that will not apply. The second currently reports `BROKEN`, which is wrong — `BROKEN` must keep meaning *pytest itself broke*, not *the code moved*. |
| Q3 | **A drifted mutant still runs.** The `STALE` flag rides alongside the real outcome. Skipping would throw away a measurement, and `drift_of` was built to report rather than act. |
| Q4 | **`UNHASHED` is not drift.** A newly authored mutant gets a normal verdict; the flag is carried so the report can say "pin this". |
| Q5 | **Confirmation re-runs only the killer node ids**, not the whole scope — usually one to three tests. |
| Q6 | **Verdicts live in `mutation.py`.** Judging is what a session is for, and the file has room. |

## Verdict rules

Applied in this order — the first that matches wins, and the order is the design:

1. Any baseline failure whose file is in `campaign.scope` → **`INDETERMINATE`**. Nothing about this
   mutant is readable, so no other rule may fire. (FR-3a)
2. Outcome `NOTHING_RAN` → **`FAIL`**. Zero tests collected is not a survival. (FR-4, already raw)
3. Outcome `BROKEN` → **`BROKEN`**, carried through unjudged.
4. Outcome `NO_KILL` → **`FAIL`** — the requirement is not protected.
5. Outcome `KILL` with **no in-scope killer** → **`FAIL`**. A bystander died; the requirement is
   still unproven, and this is the rule the whole sub-feature exists for.
6. Outcome `KILL` with an in-scope killer, **confirmed** → **`PASS`**.
7. Outcome `KILL` with an in-scope killer that **does not reproduce** when re-run without the
   mutant → **`FAIL`**, reason `flaky`. A test that fails either way protects nothing.

`STALE` and `UNHASHED` are **flags on the result**, not verdicts — they answer a different question
than "is this requirement protected" and collapsing them would lose one of the two answers.

## Campaign verdict (FR-8)

- Verdicts returned ≠ mutants declared → **`FAILED`**. Accounting first: a campaign that lost a
  result cannot be scored on the results it kept.
- Any `FAIL` → **`FAILED`**.
- Only `INDETERMINATE` / `STALE`-flagged non-passes → **`PARTIAL`**.
- Otherwise → **`PASSED`**.

## Commit boundaries

### CB-1 — Verdict assignment and baseline attribution

**Delivers:** `verdict_of()` implementing rules 1–6, `campaign_verdict()` implementing FR-8, and
`drift_of` wired into the run so `STALE`/`UNHASHED` reach the result. Anchor-won't-apply remapped
from `BROKEN` to `STALE`.

**Tests — unit.** One per rule, plus the two that carry the reasoning:
- a baseline failure **outside** the scope does **not** make the mutant `INDETERMINATE`
  (FR-3a's whole point — one unrelated red test must not void the session);
- a kill by a test **not** in scope is `FAIL`, not `PASS`.

**Done when** the in-scope rule kills a mutant: neutralise the membership check so any killer
counts, and confirm the bystander test goes red. That rule is why SF-03 exists.

### CB-2 — Kill confirmation

**Delivers:** re-running the killer node ids **unmutated** before recording `PASS`, and rule 7.

**Tests:**
- *unit* — a killer that fails unmutated too is `FAIL`/`flaky`, not `PASS`; confirmation runs only
  the killer ids, not the scope.
- *integration* — **the seam**: a real corpus, a real sandbox, a genuine kill confirmed end to end,
  and a planted always-failing test shown as `flaky` rather than protection. Written at this
  boundary because confirmation is the interface that does not exist until here.

**Done when** confirmation kills a mutant: neutralise the re-run so its result is ignored, and
confirm the flaky test goes red.

## Risks

| # | Risk | Mitigation |
|---|---|---|
| R-1 | Confirmation doubles the cost of every `PASS` | Only the killer ids are re-run, not the scope — measured 1–3 tests in practice |
| R-2 | Rule order is the design; an implementation that reorders is subtly wrong | Rules numbered here and asserted individually, so a reorder breaks a named test |
| R-3 | `STALE` as a flag rather than a verdict is easy to collapse back | A test asserts a `STALE` mutant still carries a real verdict |
| R-4 | `mutation.py` grows past 451 YELLOW | 176 now, ~300 expected. Measured at each boundary |

## Out of scope

The report, the scheduler, the gate, the override census. SF-04 onward.
