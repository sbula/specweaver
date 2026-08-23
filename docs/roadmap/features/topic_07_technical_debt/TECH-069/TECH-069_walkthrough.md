# Walkthrough: TECH-069 — retiring the decision-citation gate

- **Feature ID**: TECH-069 (⚰️ RETIRED 2026-08-23)
- **Boundary**: CB-1 of 2 — *the gate is gone*
- **Kind**: tooling · **DAL-C** (TECH default baseline)

CB-2 — moving the settled-decision record inline — is the second half, recorded at the foot of this file.

## What changed, and why

The gate was built 2026-08-21 and never approved. Running `specweaver-design` on it from scratch,
the Phase 1 grilling did not reach an FR table: the user ruled the capability **oversold** and
retired it.

The measured case against it, all of it re-derived this session rather than taken from the design:

| Probe | Result |
|---|---|
| 13 triggers read from `PRINCIPLES.md` §2; 139 designs scanned | 127 unaccounted, 12 pass |
| Of the 12 that pass | **10 pass only because they are `STUB`-exempt** |
| Designs passing on merit | **2** — `TECH-068` and `TECH-069`, both written after the gate shipped |
| One bullet naming all 13 as `not touched` | **passes** |
| `fired — <answer>` flipped to `not touched` | **passes, and the answer is gone** |
| `T-SPEND: not touched` beside a live `$25` in the same document | **passes** — the check never reads past its own section |
| `- \`T-SPEND\` was fired at dawn` | **passes** — the marker only has to appear on the line |

The check measured the presence of vocabulary, not the truth of a claim.

**The decisive argument was not the weak check.** It was what a *guaranteed-present* record does to
the reader. A missing section makes the next agent stop and ask the user — the safe failure. A
present-but-rotten one makes it proceed and build. And because *what the user agreed* is
**testimony**, no later run can recompute it: a stale agreement is undetectable by construction,
unlike a stale count. `PRINCIPLES.md` §5 had already forbidden the second copy.

The generalised lesson is recorded in
[`anti_patterns.md`](../../../architecture/06_lessons_and_future/anti_patterns.md) — *a gate that
checks for words about a rule instead of the rule*.

## What was settled, and when

Written in the convention this ticket introduces. The heading is deliberately *not* the retired one:
a walkthrough is a record of one boundary, so these markers sit beside the facts they govern in the
sections below as well — this list is the index, not the source.

- Retire `TECH-069` entirely — deleted, not rescoped `[agreed 2026-08-23]`
- The check, its baseline, its 27 tests and its 6 mutants go; the design stays as a banner-marked
  record, per the `E-VAL-03` precedent `[agreed 2026-08-23]`
- The `T-*` trigger IDs and the decisions record are **internal machinery for agents and scripts**;
  there is no human-readability requirement on them `[agreed 2026-08-23]`
- The record's audience is other agents across sessions, and it must be up to date, short, and
  enough to double-check work done by another session `[agreed 2026-08-23]`
- A settled decision is written `` `[agreed <date>]` `` beside the fact it governs — chosen over a
  bolded prose form because it is greppable and carries its own date; ISO `YYYY-MM-DD`
  `[agreed 2026-08-23]`
- No replacement check is built. Removal only `[agreed 2026-08-23]`
- A trigger that did not fire is written nowhere: it has no fact to sit beside, and the `not touched`
  line was ruled valueless `[agreed 2026-08-23]`
- The 13 triggers stay in `PRINCIPLES.md` §2 — they work as the agent's own detector, which is the
  half that was never in doubt `[agreed 2026-08-23]`

## What CB-1 did

| # | Change |
|---|---|
| 1 | `test_quality_runner.py` gains an absence guard — **written red, watched fail** |
| 2 | Unwired from `quality.py` MATRIX and `_quality_checks.py` CHECKS → green |
| 3 | Deleted `check_decision_citations.py`, its baseline, its 27 tests, `TECH-069_mutants.json` |
| 4 | Registries tombstoned: `topic_07`, `master_story_roadmap`, `adr_006` |
| 5 | `TECH-069_design.md` → retirement record; FR/NFR tables removed |
| 6 | `STATE.md` corrected in three places |

The `doc` gate went from **14 checks to 13**.

Two registries had already disagreed about this ticket — `topic_07` said `🔧`, the roadmap said
`🔴`. The disagreement died with the entry; it was never reconciled, only retired.

## Results

**Tests** — `scripts/tests.py cb TECH-069 --kind tooling --all`, widened deliberately because a
deletion is exactly where a module-scoped run lies:

| Tier | Scope | Passed |
|---|---|---|
| unit | module — `tests/unit/scripts` | 1,175 |
| integration | all | 911 |
| e2e | all | 256 |
| **Total** | | **2,342** |

**Static quality** — `quality.py cb`: 14 passed, 1 skipped (`class_health`, nothing in scope), 0
failed. Covers ruff, `ruff format --check`, mypy, complexipy, tach, file sizes, suppressions,
cycles, duplication, conventions, comment provenance, and both test-source guards.

**Registries** — `quality.py doc`: 13 passed, 0 failed.

**Architecture** — `tach check` ✅. No import line was added or removed anywhere in the diff, so no
dependency direction, cycle or archetype constraint could move.

**Probe** — the new guard was re-tested *inside* the gate rather than trusted from its first red:
`_mutate.py` restored the `decision_citations` MATRIX row in a detached worktree and **5 tests
objected**, the new one among them.

## HITL gates — every one, and what was decided

| Gate | Found | User's decision |
|---|---|---|
| `specweaver-design` Phase 1 grilling | 6 questions put to the user; the frontier never closed because the answer superseded it | **Retire the capability.** Reaffirmed after the counter-argument for rescoping was put |
| `specweaver-dev` Phase 1 red-flag | Two things could not be settled without guessing: the inline marker's form (`T-NAME`) and whether a replacement check was in scope | Form **A**, `` `[agreed <date>]` ``. **Remove only** — no replacement check |
| `specweaver-dev` Phase 2.5 task-list review | Task list plus 11 red/blue findings across 2 cycles | **Approved.** CB-1 started |
| `specweaver-pre-commit` Phase 2.8 | 3 architecture findings, 0 blocking; coverage matrix; **0 proposed test stories**, justified per adversarial bucket | **Approved** |
| `specweaver-pre-commit` Phase 3.1b | Zero new tests written, because zero branches were touched | **Approved** |

**No gate was skipped or auto-approved.**

### One correction the user forced

The first draft of the inline-marker question used `$25` as its worked example of an *agreed*
decision. That is the one number `STATE.md` explicitly records as *"a placeholder nobody agreed"*.
The example was withdrawn and re-asked with abstract placeholders.

### Corrections the red/blue review forced

Two are worth carrying forward, because both were assertions that would have read as diligence:

- The task list justified removing the FR/NFR tables *"so the descope is visible to the sweeps"*.
  **Measured false** — `TECH-069`'s FRs were all cited and its NFRs carried `[proof: ...]`, so
  neither sat in a sweep baseline. The real reason is that a retired capability may not keep making
  claims.
- The first absence test asserted `doc == 13 checks`. A count goes red on the next doc check anybody
  adds — a guard that fails for the wrong reason. It asserts the **name is absent** instead.

## Findings recorded rather than fixed

| Finding | Where it now lives |
|---|---|
| Root `context.yaml` is a stub — `purpose: TODO`, `owner: TODO` | `known_boundary_violations.md`, DEFERRED. Filling it is a `T-ARCH` decision for the user |
| CB-1 alone leaves `PRINCIPLES.md` §2 demanding a section nothing reads — the named anti-pattern | Discharged by CB-2. The window is one commit wide and deliberate: folding both into one commit would mix a deletion with a rule change |
| `phase-3-implement-tests.md` contradicts itself — §3.1b orders a mandatory HITL yield, the closing note says there is no gate | **This file.** It was first noted in `task.md`, which is rewritten by the next task and would have lost it. Not fixed inside a retirement commit |

## Not part of this commit

`scripts/baselines/mutation_findings.json` shows 176 insertions and 133 deletions from the
2026-08-23 03:00 mutation run. Left **unstaged**.

That run also reports one `UNPROTECTED` mutant on `TECH-068` `FR-9`
(*a-rust-trait-is-invisible-again*) — a real signal, unrelated to this boundary, and the user has
scheduled the test review for later.

---

# CB-2 — decisions are written where the fact is

Commit `a97c8e2d` removed the reader. This removes what it was reading for, and says where a
settled decision goes instead.

## The rule

`PRINCIPLES.md` §2 no longer names a *Decisions taken with the user* section. It now says:

> **Write a settled decision beside the fact it governs, marked `` `[agreed <date>]` `` (ISO date).**
> Not in a section of its own. §5 is the reason: a list of decisions at the foot of a document is a
> second copy of facts stated in the body, and the two drift the moment somebody edits the number
> without scrolling down. Beside the fact, whoever changes it is looking straight at the marker.
>
> A trigger that did not fire is written **nowhere** — it has no fact to sit beside.

## What CB-2 changed

| # | Change |
|---|---|
| 7 | `PRINCIPLES.md` §2 — the settled-decision source becomes the inline marker; §5 cited as the reason |
| 8 | `specweaver-design/references/phase-1-intake.md` × 2 trees |
| 9 | `specweaver-design/references/phase-6-consistency.md` × 2 trees |
| 10 | `specweaver-implementation-plan/SKILL.md` × 2 trees — two clauses each |
| 12 | `STATE.md` — CB-1 had left two sentences that CB-2 makes false |
| 13 | this section |

Six skill files, three files mirrored across `.agents/` and `.claude/`. `check_skill_sync.py`
confirms the trees agree; `grill-me` alone is a symlink and needed no second edit.

## Two claims that were dropped, not moved

**Phase 1 intake** said the section *"is what makes Phase 6 reviewable; without it the approval has
nothing to check the code against."* That claim needs a human to read 139 designs, which does not
scale and was the argument that retired the gate. Phase 6 now reads the marked sentences themselves,
which is the same work at the moment it matters and over only the design in front of you.

**Phase 6** said the design *"must carry a section listing what `/grill-me` settled."* It now says
every fact a trigger fired on must carry its marker in the sentence that states it. The difference
is what a rubber stamp looks like: a list can be written without asking anybody, and reads as
diligence. A marker sits on a number the reviewer is already looking at.

## A pre-existing bug fixed on contact

`phase-1-intake.md` opened with *"The **twelve** triggers ..."* and then listed thirteen, in both
trees. Wrong since `PRINCIPLES.md` §2 was rewritten. Fixed here because the pre-commit gate does not
distinguish inherited defects from introduced ones.

## What deliberately did not change

- **The thirteen triggers.** They stay in §2 exactly as written. They are the agent's own detector,
  and that half was never in doubt.
- **`/grill-me`.** Untouched. It is what actually protects the user: plain questions, in the user's
  language, with a recommendation beside each, at the moment the decision is live.
- **The two designs that carry the old section.** `TECH-068` and `TECH-069` keep theirs as records
  of what was decided when they were built. A delivered design is a record and is not rewritten
  unless a statement in it has become false.

## The gate that could not run

CB-2 changed only prose, and `scripts/tests.py` refused it: a tier selecting no tests was treated
as missing coverage without first asking whether there was any code to cover.

Measured before deciding anything: **131 of the last 400 commits — 32% — changed no Python at all.**
Every one would have been blocked. Two landed anyway (`00b78d5f`, `3db9de2f`) because nobody ran the
gate on them. That is what an unrunnable gate buys: skipped on a third of commits, and then not
trusted on the other two-thirds either.

`quality.py` has carried a separate `doc` track for exactly this since it was written. The pattern
was invented, proven, and applied to one of the two runners.

Fixed in `083e7ef9`, ahead of this commit so that CB-2 itself is the end-to-end proof — it is
documentation-only, and the gate now returns `no tests apply … this boundary changed no code`,
exit 0.

**The option not taken.** Running CB-2 as `--kind audit` would have passed immediately: that kind
declares no tiers by design. It was rejected because `audit` means *produces findings, not code*,
and this produces a rule — the label would have been false, and the gate would have stayed broken
for the next 32% of commits. Recorded here so nobody reaches for it as a shortcut later.
