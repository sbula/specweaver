# Design: The Morning Gate Marks Its Own Homework

- **Feature ID**: TECH-056
- **Epic**: Topic 07 (Technical Debt)
- **Status**: APPROVED (2026-08-16)
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-056/TECH-056_design.md
- **Origin**: 2026-08-16, found while running the morning check after `TECH-055`. A defect in
  `TECH-049`'s delivered gate, so it is a new ticket rather than an edit to that story
  (`finished-stories-immutable`).

> **Proportionality.** One line of production logic and the seam test that should have caught it.
> The value is entirely in the seam: both halves of this gate were already correct.

## Problem Statement

`mutation.py --gate` **cannot block**. Reproduced directly against `scripts/_mutation_gate.py`:

```
1. gate before the session records anything
   blocked=True  | findings nobody has looked at ['X-1 FR-1 a-real-survival']
2. the session folds its own findings into the ledger — what main() does at the end of every run
   ledger now: {'X-1 FR-1 a-real-survival': {'runs': 1}}
3. the morning gate, run after that session
   blocked=False | every finding carries a disposition
```

`gate_verdict` computes `known = set(load_ledger(...)["findings"])` — **presence**, not disposition.
`record_run`, called at the end of `main` on the same run that discovers a finding, inserts every
`FAIL`/`BROKEN` as `{"runs": 1}` with no disposition. So the session that finds a real survival marks
it as read, and the morning gate then announces *"every finding carries a disposition"* about an
entry that carries none.

**Nothing about this is visible in either half.** `gate_verdict` is right: an empty ledger blocks, a
dispositioned entry clears. `record_run` is right: a new finding starts at `runs: 1`, a returning one
increments, a departed one is pruned. Their unit tests assert exactly those things and all pass.
**They are never used apart**, and no test composes them — which is the third time today a defect has
had this shape: `sw resume`'s persistence was well covered and its discovery unreached
(`TECH-054`); the baseline comparison was well covered and its wiring untested (`TECH-055`).

**Why it matters more than the other two.** This gate is the repo's only standing question about
whether its tests still work. `CLAUDE.md` instructs every session to run it and trust the answer;
the answer has always been the same one.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | A finding is "read" only once a human has recorded a disposition for it | A developer running the morning check after a session that found a survival | runs `mutation.py --gate` | it blocks and names the finding, and keeps blocking until `--confirm … --as … --why …` records a decision |

**One requirement.** The `runs` counter is not a second one — recording recurrence and recording a
decision are different acts, and the defect was reading the first as evidence of the second.

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | The fix must not create a bootstrap trap | A first-ever finding must be clearable by the documented route and nothing else: `--confirm <id> --as <disposition> --why <reason>`. If clearing it needed a hand-edited ledger, the gate would be routed around within a week |
| NFR-2 | Recurrence survives a disposition | `runs` must keep counting across the fix, because a `will-fix` re-confirmed for a fortnight is the only pressure on a fix that never happens |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Filter on `disposition`, do not stop recording | The alternative — have `record_run` skip undispositioned findings — would make the ledger unable to count how long a finding has been present, which is the reason it exists (`TECH-049` FR-11a) | No |
| AD-2 | The proof is a **composed** integration test, not another unit test | Both units already pass in isolation and would keep passing under the defect. Only `record_run` → `gate_verdict`, in that order, can fail | No |
| AD-3 | Land it while the corpus is clean | Measured 2026-08-16: a full session over all four corpora returns **20/20 PASS and zero findings**, so the gate stays CLEAR either way today. Turning on a gate that has never fired is cheapest at the moment it has nothing to say | No |

## Sub-Feature Breakdown

**Single feature — no decomposition.** One expression, one new test module.

## Execution Order

One commit boundary: the composed seam test first, red for the right reason, then the one-line fix.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| — | Single feature | — | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: DELIVERED 2026-08-16. Four mutants, all killed; `mutation.py --gate` re-run
after the fix still reports `CLEAR`, which is the only way to know the fix did not simply invert the
silence.

**Three defects today with one shape.** `sw resume`'s persistence was well covered and its discovery
unreached (`TECH-054`); the baseline comparison was well covered and its wiring untested
(`TECH-055`); here both halves of the gate had passing unit tests while their composition could not
work. In each case the missing test was at the tier nobody had written, and in each case the units
kept passing throughout. That is the pattern worth carrying, not the three fixes.
