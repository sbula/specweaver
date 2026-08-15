# Implementation Plan: Mutation Campaign Corpus and Session Gate [SF-06: Session Gate and Override Census]

- **Feature ID**: TECH-049
- **Sub-Feature**: SF-06 — Session Gate and Override Census
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-06
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_sf06_implementation_plan.md
- **Status**: APPROVED

**FRs owned: FR-11, FR-11a, FR-12.** (`FR-14` is SF-07.) Depends on: SF-04 (committed).

> **Proportionality.** Two boundaries. TDD, a killed mutant per claim, full gate.

## Scope

Read the report, block on unconfirmed findings, release on a disposition, count recurrence, and
ratchet the overrides. **Then SF-07 makes it usable** — this sub-feature ships the mechanism only.

## Research notes

| Fact | Evidence |
|---|---|
| `scripts/baselines/*.json` shape is `{_comment, counts, total}`, fail-on-growth, re-freeze with `--update-baseline` | read `suppressions.json`, `check_suppressions.py` |
| `.tmp/` is gitignored, so report history dies on a clean — recurrence cannot be derived from past reports | — |
| `quality.py matrix` shows 23 checks across 5 gates; `mutation.py` is deliberately **not** among them | executed |
| The report carries `summary.verdict`, `campaigns[].results[].{derived_id,verdict,drift,detail}` | delivered SF-04 |

## Decisions taken at the Phase 4 gate (Steve Bula, 2026-08-15)

| # | Decision |
|---|---|
| Q1 | **One committed ledger**, `scripts/baselines/mutation_findings.json`, keyed by derived id. Recurrence needs history and `.tmp/` is gitignored, so the ledger is the memory. |
| Q2 | **The ratchet counts only dispositions that release without resolving** — `will-fix` and `equivalent`. `real-gap` (you fixed it) and `stale-refreshed` (you re-read and re-pinned) do not. |
| Q3 | **`NFR-6` wins over the FR-11 binding row.** The gate is standalone (`mutation.py --gate`), never a `quality.py` check. The binding row is amended below; `AD-10`'s whole point was that this gate is not commit gating. |
| Q4 | **A report older than 48 h is stale** — two missed nightly runs, so one skipped night is not a false block. |
| Q5 | **One confirmation at a time, no bulk flag** — same reasoning as `--refresh`: a bulk clear is how a census becomes decoration. |

> **Design amendment, 2026-08-15.** The FR-11 Requirement–Surface Binding read
> *"Gate registration and scope resolution · `quality` · `CHECKS` dict"*. That contradicts `NFR-6`
> (*"No `quality.py` gate may invoke the session gate"*). NFR-6 stands; the binding row is corrected
> to name the ledger and the report instead. Recorded rather than silently fixed — a binding that
> disagreed with its own NFR is exactly the drift `ADR-003`'s fixpoint exists to catch, and it
> survived the design's own Phase 6.

## The ledger

`scripts/baselines/mutation_findings.json`

```
{ "_comment": "...", "findings": {
    "<derived id>": { "disposition": "will-fix", "who": "...", "why": "...",
                      "first_seen": "<head>", "runs": 4 } },
  "override_count": 2 }
```

`runs` is the recurrence count (`FR-11a`) — incremented each time the finding appears again.
`override_count` is the ratcheted number: entries whose disposition is `will-fix` or `equivalent`.

## Gate rules

1. No report, or a report older than **48 h** → **BLOCKED**, reason `stale report`.
2. Any finding in the report with verdict `FAIL` or `BROKEN` that has **no ledger entry** →
   **BLOCKED**, listing them.
3. Otherwise → **CLEAR**.

`INDETERMINATE` and `STALE` do not block on their own: the first says the tree was already red, the
second says the code moved. Neither is evidence a requirement is unprotected, and blocking on them
would train people to confirm noise.

## Commit boundaries

### CB-1 — The ledger and the gate verdict

**Delivers:** ledger read/write, `gate_verdict()` implementing rules 1–3, recurrence increment.

**Tests — unit:** each rule; a stale report blocks; a fresh report with an unconfirmed `FAIL`
blocks and **names it**; a confirmed one clears; `INDETERMINATE`/`STALE` alone do not block;
recurrence increments across two runs and resets when a finding disappears.

**Done when** rule 2 kills a mutant: neutralise the "has a ledger entry" check so everything
clears, and confirm the unconfirmed-finding test goes red.

### CB-2 — Confirmation CLI and the override ratchet

**Delivers:** `--gate`, `--confirm <id> --as <disposition> --why <text>`, and the ratchet.

**Tests:**
- *unit* — an unknown disposition is refused; `--confirm` without `--why` is refused; the ratchet
  fails when `override_count` grows and passes when it falls; `real-gap` does not increment it.
- *integration* — **the seam**: run a real session, take its report, gate on it, confirm the
  finding, gate again and see it clear. Written here because the report→ledger→gate chain does not
  exist until now.

**Done when** the ratchet kills a mutant: neutralise the growth check and confirm the
ratchet test goes red.

## Risks

| # | Risk | Mitigation |
|---|---|---|
| R-1 | Confirming becomes a reflex and the census fills with `will-fix` | That is what `runs` is for — a `will-fix` re-confirmed for a fortnight is visible in the ledger |
| R-2 | The ledger accumulates entries for findings that no longer exist | Entries absent from the current report are pruned on write, so the file describes today |
| R-3 | `--why` becomes a single character | Not mechanically fixable; the ratchet and the diff are the review |

## Delivered

Two boundaries. Eight mutants, all KILLED. Full suite 7119 passed, 0 failed. End to end for real:
session → report → gate → `CLEAR`, exit 0.

**Findings, all from using it rather than reviewing it:**

- A mutant caught the **fourth** test in this ticket asserting the right outcome for the wrong
  reason: `test_a_report_older_than_48h_blocks` used a report that also carried an unconfirmed
  failure, so rule 2 blocked it regardless. Only an otherwise-clearing report proves staleness did.
- **A killed session leaks a git worktree forever.** `run_corpus`'s `finally` survives a crash but
  not a kill, and a nightly timer meets kills. Found because interrupted runs left three
  `sw-session-*` worktrees behind, one `locked`. The next run now prunes them at build time,
  matched by prefix so no one else's worktree is touched — the run that died cannot clean up.
- `main` reached complexity 14 with four modes in it; split into `_cmd_confirm` / `_cmd_gate` /
  `_cmd_install`.

## Out of scope

Skills, the morning routine, `CLAUDE.md` — SF-07 (Adoption).
