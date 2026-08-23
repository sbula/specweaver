# Task: retire TECH-069, and record decisions inline

**Skill**: `specweaver-dev` · **Story**: TECH-069 (`🔧`, retired by the user) · **Kind**: tooling

The user retired the capability after the `specweaver-design` Phase 1 grilling. The gate is deleted
outright; the record it checked is replaced by an inline marker beside the fact it governs.

Retire `TECH-069` entirely — the check is deleted, not rescoped `[agreed 2026-08-23]`. The check,
its baseline, its 27 tests and its 6 mutants go; the design is kept as a banner-marked retirement
record, per the `E-VAL-03` precedent `[agreed 2026-08-23]`. An inline decision is written
`` `[agreed <date>]` `` in backticks — chosen over a bolded prose form because it is greppable and
carries its own date `[agreed 2026-08-23]`; the date is ISO `YYYY-MM-DD`, matching every other date
in this repo. The `Decisions taken with the user` section is removed from the rule and the six skill
files: it is a second copy of a fact, and `PRINCIPLES.md` §5 already forbids that
`[agreed 2026-08-23]`. No replacement check is built here — removal only `[agreed 2026-08-23]`.

**A trigger that did not fire is written nowhere.** It has no fact to sit beside, and the user ruled
the `not touched` line valueless. The 13-item list survives in `PRINCIPLES.md` §2 and `/grill-me`
walks it, so nothing is lost but the unverifiable receipt.

Untouched: `quality.py` and its other four gates but for one row; `T-SPEND`, `T-BOUNDARY`,
`T-ORDER`, `T-PROVEN`, `T-DATA`, `T-OBLIGATION`, `T-DEFAULT`.

## Research (measured this session — do not re-derive)

| Fact | Evidence |
|---|---|
| The check is on `doc` only, 1 row of 14 | `quality.py` MATRIX; `quick`/`cb`/`sf`/`feature` never name it |
| 13 triggers, 139 designs, 127 unaccounted, 12 pass | 10 of the 12 pass only as `STUB`-exempt |
| Only 2 designs pass on merit | `TECH-068`, `TECH-069` — both written after the gate shipped |
| The gate is defeated by one line | all 13 named `not touched` on one bullet passes |
| The truth-destroying edit is one word | `fired — <answer>` → `not touched` passes, reason gone |
| The check never reads the rest of the design | so `not touched` beside a live number passes |
| `.agents/` and `.claude/` design skills are **separate copies** | `grill-me` alone is a symlink |
| The two registries already disagree | `topic_07` says `🔧`, `master_story_roadmap:682` says `🔴` |
| **No skill or doc names the script** | only `TECH-069`'s own design and mutants do — no dangling ref |
| **`TECH-069`'s FRs/NFRs are in neither sweep baseline** | its FRs are all cited; its NFRs carry `[proof: ...]` |
| **`baseline_snapshot.py` enumerates by `rglob`** | deleting one baseline file breaks no guard |
| **`check_retirement_targets.py` matches `INT-US-*` only** | a `TECH` retirement note is outside its grammar |

## Commit boundary 1 — the gate is gone

- [x] 1 — `test_quality_runner.py` asserts the `doc` gate does **not** name `decision_citations`
      (by absence, not by a count — a magic `13` breaks on the next doc check) — **RED first**
- [x] 2 — Unwire: drop the MATRIX row (`quality.py`) and the runner entry (`_quality_checks.py`) → GREEN
- [x] 3 — Delete `scripts/check_decision_citations.py`, `scripts/baselines/decision_citations.json`,
      `tests/unit/scripts/test_check_decision_citations.py`, `TECH-069_mutants.json`
- [x] 4 — Tombstone the registries in the `E-VAL-03` grammar: `topic_07_technical_debt.md`
      (`⚰️ RETIRED` + *ID is dead — do NOT reuse*), `master_story_roadmap.md:682`,
      `adr_006_...md:124`. The `🔧`/`🔴` disagreement dies with the entry
- [x] 5 — `TECH-069_design.md` becomes a retirement record: `> **⚰️ RETIRED 2026-08-23 by the
      user.**` banner naming the reason, and `Status: ⚰️ RETIRED 2026-08-23`. FR/NFR tables removed
      because a retired capability may not keep making claims — **not** for the sweeps, which never
      counted them
- [x] 6 — `.agents/STATE.md`: the gate row, the `TECH-069 minted` row and the "no non-stub design
      accounts" bullet all tell the truth
- [/] **CB-1 — the check, its wiring, its tests and its claims are gone**

## Commit boundary 2 — decisions are written where the fact is

- [ ] 7 — `PRINCIPLES.md` §2: the settled-decision source becomes the inline `` `[agreed <date>]` ``
      marker. The ADR and this-file clauses either side of it are left intact. §5 is cited as the reason
- [ ] 8 — `specweaver-design/references/phase-1-intake.md` × 2 trees: record each settled decision
      beside the fact it governs; a trigger that did not fire is written nowhere
- [ ] 9 — `specweaver-design/references/phase-6-consistency.md` × 2 trees: approval reviews the
      inline decisions
- [ ] 10 — `specweaver-implementation-plan/SKILL.md` × 2 trees: the precondition reads inline
      decisions, not a section
- [ ] 11 — `.tmp/HANDOVER.md`: replace the TECH-069 gate entry with the retirement outcome. It is
      gitignored, so no gate will ever catch it going stale
- [ ] 12 — `.agents/STATE.md`: CB-1 left it saying *"right now the rule has no reader"* and *"the
      commit that follows replaces it"*. Both go stale the moment CB-2 lands — update them
- [ ] 13 — `TECH-069_walkthrough.md`: it promises *"CB-2 … is appended to this file when it lands"*.
      Append it
- [ ] **CB-2 — the rule and the six skill files say where a decision is written**

## CB-1 pre-commit gate (`specweaver-pre-commit`)

- [x] Phase 1 — architecture: tach pass, no imports changed. 3 findings, 0 blocking (A2 discharged by CB-2; A3 pre-existing root `context.yaml` stub, recorded)
- [x] Phase 2 — test gap: coverage matrix + 0 proposed stories, justified per bucket. Guards 2/2. New test probed by mutation — 5 objections
- [x] Phase 3 — implement tests: **no branch was touched, so no test was written.** Both trimmed literals verified still exact-set. Ruff clean
- [x] Phase 4 — full suite
- [x] Phase 5 — code quality (`quality.py cb`)
- [x] Phase 6 — documentation
- [x] Phase 7 — walkthrough
- [x] Phase 7.5 — red/blue on the diff
- [x] Phase 7.9 — handover / STATE
- [/] Phase 8 — commit boundary (HITL)

**Finding against the skill itself:** `phase-3-implement-tests.md` contradicts itself — §3.1b orders
a mandatory HITL yield, while the closing `IMPORTANT` says there is no gate and to proceed
immediately to Phase 4. `SKILL.md` and `specweaver-dev` both say Phase 3 gates. Yielding.

## Notes on tiers and proof

- Task 1 is the only genuine red→green cycle here. Deletions and prose edits have no honest test;
  writing one would be the decoration `PRINCIPLES.md` §3 forbids.
- The existing gates carry the rest: `check_skill_sync.py` holds the two trees in parity,
  `check_skill_references.py` catches a skill pointing at a deleted file, and `quality.py doc` must
  go green at 13 checks.
- No new check is built.
