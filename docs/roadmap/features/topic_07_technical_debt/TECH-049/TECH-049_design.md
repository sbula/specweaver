# Design: Mutation Campaign Corpus and Session Gate

- **Feature ID**: TECH-049
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — decisions settled 2026-08-15, not yet run through `specweaver-design`
- **Origin**: 2026-08-15, from the `ADR-003` skill-coverage audit. Rescoped the same day — the
  original framing (*"Nothing Verifies a Test Was Red Before the Code It Covers"*) named a real gap
  whose two cheap answers the closure contract already refuses, and whose expensive answer is
  `A-VAL-03`. What survives is dev tooling, below.

> **Track: dev tooling.** This is how *we* build SpecWeaver. `A-VAL-03` (Mutation Testing Gates) is
> a product capability run against a *user's* codebase. Overlapping subject matter, different
> deliverable. Nothing here is blocked on it; nothing here belongs in it.

## Problem Statement

Mutation testing exists (`scripts/_mutate.py`, `scripts/_mutate_campaign.py`) and works. Nothing
around it does:

- Campaigns are ad-hoc JSON, authored once and thrown away. **No campaign file is committed
  anywhere in the repo.**
- Reports go to gitignored `.tmp/` and are discarded. No prior result survives, so **drift cannot be
  detected** — "this was killed in July, it survives today" is unaskable.
- `_mutate_campaign.py` **returns 0 unconditionally**. A campaign where every mutant is `BROKEN`
  exits clean and writes a report that reads healthy.
- Nothing runs it. No cron, no timer, no scheduled workflow — `.github/workflows/` holds only an
  image build, and there are no git hooks.

## Settled decisions (2026-08-15)

Reached by discussion; recorded here so they are not re-derived.

| # | Decision |
|---|---|
| 1 | Mutation detects **shift and drift**. Red-first TDD stays the primary discipline; mutation does not replace it. |
| 2 | Mutants are **deliberate, never random** — each plants a bug that should break one isolated (N)FR. |
| 3 | A **campaign targets one (N)FR** and holds several mutants. Requirement ids are unique per feature, **not repo-wide**. |
| 4 | **One file per feature**, beside the design: `<ID>_mutants.json`. 55 files today, ~149 at full roadmap. One file per requirement would be 575 now and ~1,400 later — rejected. |
| 5 | Success = scoped tests **green before, red after**, with at least one killer **in scope** for the (N)FR. A bystander kill is a failure: the requirement is still unproven. |
| 6 | **Baseline runs the full suite once per session.** A red baseline does **not** stop the run — it yields `INDETERMINATE` for the affected mutants and tells you how to read the rest. |
| 7 | Mutant runs are **(N)FR-scoped**, not full-suite. Measured: **71.7 s → 1.24 s** per mutant. Scoping is semantics (see 5), not an optimisation. |
| 8 | **Accounting rule**: N mutants declared, N verdicts returned. Any mismatch fails the campaign. Catches crashes, interrupts, silent skips. |
| 9 | A failing campaign **never stops the others**. All campaigns run; the session verdict aggregates. |
| 10 | **`symbol_sha` only** — hash of the normalised AST (`ast.dump()`, line numbers stripped) of the enclosing symbol. Not a skip mechanism (a full corpus is ~10 min); its only job is answering *"did the code this claim rests on move?"*. `file_sha` adds nothing. |
| 11 | **Campaign declares its own `scope`.** Citation tags cross-check where present, never gate — only 35 of 554 test files carry one. |
| 12 | **One report**, `.tmp/mutation_report.json`, summary block first. No markdown, no human formatting. |
| 13 | The report is **self-contained**. The sandbox is a detached worktree deleted at any time; killers, collected counts and failure text are captured before teardown. Nothing may point into it. |
| 14 | Sandbox output is for scripts only. **`PY_COLORS=0`** — no colour anywhere in the pipeline. |

### Verdicts

| Baseline (scoped) | After mutation | Verdict |
|---|---|---|
| green | red, killer in scope | `PASS` |
| green | red, no in-scope killer | `FAIL` — bystander; FR unproven |
| green | green | `FAIL` — FR not protected |
| **red** | anything | `INDETERMINATE` |
| — | anchor will not apply | `STALE` — code moved |
| — | 0 tests collected | `FAIL` |

Every kill is re-run without the mutant before it is believed, or a flaky test reads as a pass.

## Tasks

1. ~~Fix the runner's false `SURVIVED` under a colour-forcing shell.~~ **DONE `72b82df8`.**
2. **Campaign format** — `<ID>_mutants.json` schema, loader, validation, `symbol_sha` computation.
3. **Runner changes** — session baseline, scoped runs, collected-count assert, kill re-confirmation,
   sandbox-clean check between mutants, accounting rule.
4. **Single JSON report** — summary first, self-contained, exit codes `0` pass / `1` fail / `2` could
   not run.
5. **Scheduler** — run the corpus nightly. Nothing exists: no cron, no timer, no scheduled workflow.
6. **Session gate** — evaluate the report automatically and decide *continue* or *fix first*.
   Standalone; deliberately **not** wired into any commit gate.
7. **Override census** — a human may overrule the gate when a feature genuinely outranks the issue,
   but never silently. Reuse the `check_suppressions.py` + `scripts/baselines/` pattern: the bypass
   is an entry naming the requirement, the person, the reason and the promise, ratcheted so the
   count may fall and never rise. A `--force` flag with no record turns the gate into decoration.

> **Open on task 7:** does an override expire on a date, or is a non-growing ratchet enough?

## Non-Goals

- **Mutant generation from an AST.** That is `A-VAL-03`. Every entry stays hand-authored, so the
  format must remain writable by a person.
- **Any commit-gate integration.** The session gate is standalone by decision.
- **Blocking on a surviving mutant as a general rule.** Equivalent mutants are 4–39% of all mutants
  and equivalence is formally undecidable — a blanket block carries that as a false-failure floor.
- Retrofitting campaigns onto delivered stories. The corpus grows as campaigns are written.

## Intake for `A-VAL-03`

Carry forward, do not re-derive: the cost figures (7), the equivalent-mutant floor, scoping-as-
semantics (5), baseline-once-per-session (6), the accounting rule (8), and the verdict table.

## Next Step

Run `specweaver-design TECH-049`. The decisions above are inputs, not a substitute for it.
