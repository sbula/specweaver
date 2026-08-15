# Implementation Plan: Mutation Campaign Corpus and Session Gate [SF-05: Scheduler]

- **Feature ID**: TECH-049
- **Sub-Feature**: SF-05 — Scheduler
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-05
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_sf05_implementation_plan.md
- **Status**: APPROVED

**FRs owned: FR-10.** Depends on: SF-04 (committed).

> **Proportionality.** One FR plus the first real campaign. One commit boundary.

## Scope

Run the corpus unattended, nightly, via a systemd user timer — **and write the first real campaign**,
because a scheduler over an empty corpus measures nothing and reports `NOT_RUN` forever.

## Research notes

| Fact | Evidence |
|---|---|
| `systemd 259`; `systemd-analyze verify` exits 0 on a valid unit | executed |
| `~/.config/systemd/user` exists and `loginctl show-user` reports **`Linger=yes`** — user timers fire when logged out | executed |
| The repo cannot own the installed unit: it lives in `~/.config/systemd/user/`, outside the tree | — |
| `mutation.main()` takes `--corpus-dir`, `--out`, `--no-baseline`, `--no-confirm` and returns 0/1/2 | delivered SF-04 |
| The report already carries `summary.dirty` | delivered SF-04 |
| **No corpus file exists anywhere in the repo** — the machinery is complete and measures nothing | `rglob("*_mutants.json")` → empty |

## Decisions taken at the Phase 4 gate (Steve Bula, 2026-08-15)

| # | Decision |
|---|---|
| Q1 | **The first campaign dogfoods `TECH-049`.** Its code is in `scripts/`, its tests are scoped and fast, and the corpus lands beside its own design. Three claims, each a rule the ticket exists for: `FR-4` (`NOTHING_RAN` is not a survival), `FR-5` (a bystander kill is not a `PASS`), `FR-6` (an unconfirmed kill is not protection). |
| Q2 | **The repo ships the unit files; `mutation.py --install-timer` writes them** into `~/.config/systemd/user/` and reports what it did. The repo cannot own a path outside itself. |
| Q3 | **`OnCalendar=*-*-* 03:00` with `Persistent=true`** — a missed night runs at next boot rather than being silently skipped. |
| Q4 | **A dirty tree still runs**, with `dirty: true` already in the report. Skipping would mean the one night work was left in progress is the night with no data. |
| Q5 | **FR-10's falsifiable claims** are that the generated units pass `systemd-analyze verify`, that the `ExecStart` command line actually runs, and that installing twice is idempotent. A timer firing is not testable; those three are. |

## The first campaign

`docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_mutants.json`

Three mutants, one campaign per requirement, each scoped to the tests that cover it. **Every one
has already been run by hand and observed to die** — they are not guesses:

| Requirement | Mutant | What it breaks |
|---|---|---|
| `FR-4` | `_OUTCOMES` maps 4/5 to `NO_KILL` | a mis-typed scope reads as a survival |
| `FR-5` | the in-scope membership check always passes | a bystander kill certifies the requirement |
| `FR-6` | `confirm_kill` returns `True` unconditionally | a permanently red test certifies everything it touches |

**This is the corpus's own first test of itself**, and it is worth stating plainly: if the nightly
run ever reports these three as `PASS` when they are neutralised, the whole apparatus is decorative.

## Commit boundary — CB-1

**Delivers:** unit + timer files, `--install-timer`, and the campaign above.

**Tests:**
- *unit* — the generated `.service` and `.timer` bodies contain the expected `ExecStart`,
  `OnCalendar` and `Persistent`; installing twice writes the same bytes (idempotent); the installer
  refuses when `~/.config/systemd/user` cannot be created.
- *integration* — the generated units pass `systemd-analyze verify`, skipped with a **reason** where
  systemd is absent rather than silently.
- *e2e* — **the seam**: run *the exact `ExecStart` command line* as a subprocess against the real
  corpus, and assert it exits 0/1 and writes a report naming `TECH-049`. Written here because the
  command line is the interface between the timer and the session, and it does not exist until now.

**Done when** the campaign kills its own mutants: run
`python scripts/mutation.py --corpus docs/.../TECH-049_mutants.json` and confirm all three
campaigns come back `PASSED`. That is the corpus proving it can fail — the exit condition for the
whole sub-feature, not just this boundary.

## Risks

| # | Risk | Mitigation |
|---|---|---|
| R-1 | The e2e runs the full corpus and is slow | The corpus is three mutants scoped to two test files; measured ~1.2 s each |
| R-2 | `systemd-analyze verify` is unavailable in CI | Skipped with an explicit reason, never silently — `_silent_skips.py` exists for that failure |
| R-3 | The timer runs while a human is mid-edit | Q4: it runs, and `dirty: true` says so |
| R-4 | The campaign's mutants rot as the code changes | That is `symbol_sha` drift reporting `STALE`, which is the corpus working, not failing |

## Out of scope

The gate and the override census — SF-06.
