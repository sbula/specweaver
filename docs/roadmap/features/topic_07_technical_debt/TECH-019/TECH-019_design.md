# Design: Skill Instruction Integrity — Dangling Doc References and Contradictory Gate Orders

- **Feature ID**: TECH-019
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: found by the INT-US-21 SF-02 CB-1 pre-commit gate, 2026-07-26

## Problem Statement

Skill instructions are not checked against the repository they instruct on, so they rot silently and
the agent absorbs the rot as truth.

### Defect 1 — six live instruction sites read a file that does not exist

`TECH-008` modularized `docs/architecture/architecture_reference.md` into
`docs/architecture/{01..07}_*/`. The file was deleted. Six **live** instruction sites still tell the
agent to read it:

| File | Line | Instruction |
|---|---|---|
| `.agents/AGENTS.md` | 46 | "Read `docs/architecture/architecture_reference.md` for the module map and dependency rules" |
| `specweaver-design/references/phase-2-research.md` | 24 | read target |
| `specweaver-implementation-plan/references/phase-1-preparation.md` | 20 | read target |
| `specweaver-implementation-plan/references/phase-3-architecture.md` | 22 | "check the `context.yaml` and `architecture_reference.md`" |
| `specweaver-pre-commit/references/phase-1-architecture.md` | 1.1 | read target; **1.8 also names it as the place to record boundary violations** |
| `specweaver-pre-commit/references/phase-6-documentation.md` | 27 | doc-update target |

So **every** design, implementation-plan and pre-commit run since `TECH-008` has been instructed to
load architecture context that cannot be loaded. Two failure modes, both bad: the agent silently
skips the step the phase depends on, or it fills the gap from training data and reports architecture
facts it never read. Phase 1.8's case is worse than a dead read — it directs *new* boundary-violation
records into a nonexistent file, when the live ledger is
`docs/architecture/06_lessons_and_future/known_boundary_violations.md`.

(`master_story_roadmap.md:665` also names the file, but as `TECH-008`'s own benefit statement — a
correct historical reference, not a defect.)

### Defect 2 — two pre-commit phases give contradictory format orders

- `phase-1-architecture.md` §1.9: *"FORMAT EXCEPTION: You MUST NOT write this combined analysis into
  a file or system Artifact! You MUST print … DIRECTLY into your conversational chat response."*
- `phase-2-test-gap.md` §2.8: *"You MUST write the test gap analysis into a system Artifact … You
  MUST NOT print the Coverage Matrix or Test Stories directly into your conversational chat
  response."*

§1.9 relocated the hard gate to the end of Phase 2 and merged both analyses; §2.8 was never updated
to match. Whichever the agent picks, it violates an instruction marked MUST — so compliance becomes
a coin flip and the transcript record of *why* is lost.

## Candidate Approaches (not yet designed)

- Repair the six sites: point at `docs/architecture/README.md` (or the specific numbered section each
  phase actually needs) and at `06_lessons_and_future/known_boundary_violations.md` for §1.8.
- Reconcile §1.9 and §2.8 into one stated format for the combined analysis, and delete the loser
  rather than leaving both.
- **Ship the guardrail with the fix** (the reason this is a ticket and not a patch): a
  `scripts/check_skill_references.py` asserting that every repo-relative path referenced in a skill
  instruction file resolves on disk. This is the same invariant class as the handler-reachability
  test added in `f7a0f34f` — *a declared reference must resolve* — applied to instructions instead of
  pipeline steps. Without it, the next doc refactor re-creates this ticket.
- Consider whether the checker should also flag two instructions in one skill that both say MUST
  about the same output (hard; may be out of scope).

## Non-Goals (proposed, pending design)

- Not a rewrite or reorganization of the skills. Repair references and one contradiction only.
- Not a sweep of historical documents. Implementation plans and delivered design docs that mention
  `architecture_reference.md` are **records of what was true then** and must not be edited
  (finished-stories-immutable).
- Not the `.claude/` ↔ `.agents/` distribution question. Those trees are hardlinked, so one edit
  covers both; `check_skill_sync.py` already guards it.

## Next Step

Run the `specweaver-design` skill. Low risk, high blast radius — it silently degrades every design,
plan and pre-commit run, so it should land ahead of the next feature's design phase rather than
waiting behind the audit tickets (`TECH-017`, `TECH-018`). One commit for the reference repairs, one
for the checker.
