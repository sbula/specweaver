# ADR 005: Integration Is Implicit in the (Sub)Story, and `INT-US` Is Retired

**Status:** Accepted
**Date:** August 19, 2026
**Supersedes:** `ADR-003` and `ADR-004` — both of which kept a separate integration artifact
**Context:** the 2026-08-19 audit of the 28 integration contracts, after `TECH-060`'s migration closed

## Context and Problem Statement

`ADR-003` moved a seam onto the consumer capability and stopped minting `INT-US` entries.
`ADR-004` reversed that for (sub)stories holding closed features, because
`finished-stories-immutable` bars a closed capability from accepting a new FR, so it gave the
`INT-US` entry the proof instead. Both kept a **separate place** where integration is written down.

That separate place is the defect. Measured on 2026-08-19, after the migration had sorted every
claim into the new structure:

* **36 path rows were open across 28 contracts. 31 of them named another ticket as the blocker** —
  5 an open `TECH` ticket, 26 an unbuilt capability. Every one of those 31 was the same work
  recorded twice: once where it would be built, once in a contract that would never build it.
* **Every one of the 27 discharged migrations still carried an open `INT-US` line.** Discharging the
  migration moved the claims; nothing retired the entry the claims came from.
* **12 contracts held nothing of their own** once the 31 rows found their owners — no design
  document, no self-owned row, and a status that had read `⬜ Pending` for want of work that was
  never theirs.
* **2 entries were finished and still marked open.** `INT-US-05-SF03` and `INT-US-08` closed on
  2026-08-18 behind named e2e files and were carried as `[ ]` for a day, because the entry and the
  work it described were two documents that had to be updated in step.

A registry with two homes for one fact needs an edit in both to stay true, and it did not stay true.
The reader cannot tell an outstanding obligation from a restatement of somebody else's.

## Decision

**Integration is implicit in the (sub)story. There is no explicit integration story.**

1. **A (sub)story owns every test it needs**, including the ones that span more than one feature. If
   the (sub)story cannot be proven by one feature alone, the test that spans the features is part of
   the (sub)story, not part of a separate entry that refers to it.
2. **The test is written before the work, so it can go RED.** A test written after the code is green
   on its first run: it asserts the present state rather than a contract the code must satisfy. Give
   the test the chance to fail. This is the whole value, and it is only available before the code
   exists.
3. **When a related (sub)story is unbuilt, the test is still written now** and committed as
   `pytest.mark.xfail(strict=True)` naming the blocker. It fails for the right reason today.
   `strict=True` means an unexpected pass is a failure, so the moment the last related (sub)story
   lands, the suite says so out loud. `scripts/check_xfail_blockers.py` fails any such marker whose
   named blocker has become `✅`, so the marker cannot decay into a permanent exemption.
4. **The (sub)story is finished when those tests are green**, not when its own feature compiles.
   Green after all related (sub)stories are finished is the closing condition.
5. **No `INT-US-NN` / `INT-US-NN-SFxx` / `-MIG` identifier is ever minted again**, and the family is
   retired. `ADR-004`'s exception for closed features goes with it — see below.
6. **A missing test under an already-finished (sub)story is a defect in delivered work**, so it
   becomes a `TECH` ticket that owns the test and writes it red first. That is the existing rule for
   every other defect in closed code; integration was the one carve-out, and the carve-out is what
   produced a parallel registry.

## What this means for `finished-stories-immutable`

`ADR-004` reasoned that a closed capability cannot take a new FR, therefore the proof needs a
separate owner. The premise is right and the conclusion was wrong. The proof does not need a new
owner; it needs the *right* owner, and there are only two cases:

| The (sub)story is | Who writes the spanning test |
|---|---|
| not finished | the (sub)story itself, red first, `xfail(strict=True)` while a related one is unbuilt |
| finished | a `TECH` ticket, because a gap in delivered work is a defect |

Neither case needs a third kind of entry, and neither edits closed work.

## Consequences

* The `INT-US` family is retired. Its path inventories are the (sub)story's own test list and move
  there; the entries and their roadmap lines go.
* `master_story_roadmap.md` loses every `INT-US` line. A (sub)story's integration state is its own
  status, because its spanning tests are among its tests.
* Gates keyed on the `INT-US` grammar stop having a subject. Each is either re-pointed at the
  (sub)story or removed; a gate that silently passes for want of input is worse than no gate.
* `check_xfail_blockers.py` becomes the load-bearing gate of this ADR, because clause 3 is where the
  discipline lives. It was already written for `ADR-004` clause 4 and needs no change.
* `check_retirement_targets.py` loses its subject once the family is gone. Until then it still holds
  the retirements already recorded.

## What is knowingly not decided here

* **The migration order.** 207 roadmap documents, 19 gate scripts and 14 skill files reference the
  family. This ADR states the target; the sweep is its own work, and until it lands the registry
  holds both shapes.
* **Whether a spanning test is `integration` or `e2e` tier.** Unchanged: the tier follows what the
  test drives, which `check_proof_tier.py` already judges.
