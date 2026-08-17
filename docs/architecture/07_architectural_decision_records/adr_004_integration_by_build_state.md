# ADR 004: Integration Belongs to the Consumer When Unbuilt, to the Story When Closed

**Status:** Accepted
**Date:** August 17, 2026
**Supersedes:** `ADR-003` — Integration Belongs to the Consumer, Not to a Separate Story
**Context:** the 2026-08-17 audit of integration coverage across all 28 user stories

## Context and Problem Statement

`ADR-003` decided that a seam belongs to the **consumer capability**, as one of its own FRs, and that
`INT-US` entries are no longer minted. That is correct for work not yet built, and this ADR keeps it.

It was also applied to (sub)stories whose features were **already closed**, and there the rule cannot
execute. `finished-stories-immutable` bars a closed capability from accepting a new FR, so the scope
is retired from one side and lands on neither. `check_fr_coverage.py` can only judge an FR somebody
wrote, and nobody is permitted to write this one.

**Measured 2026-08-17.**

* **25 of 28 base stories** hold at least one closed capability. **17 of their contract documents are
  ten-line stubs** whose Integration Description reads `[Pending definition...]` and whose Verifiable
  Proof reads `[Pending]`.
* **9 add-on groups** hold closed features with no integration entry or an unproven one. **4 have no
  entry at all**, so the gap is not merely unproven — it is unrecorded.
* **3 entries are `✅` and name no test file**: `INT-US-05-SF03`, `INT-US-05-SF04`, `INT-US-21-SUB`.
  `check_proof_tier.py` has been carrying them as accepted debt rather than as delivered work.
* **3 retirements passed `check_retirement_targets.py` while retiring a sub-story that already ships a
  capability.** The guard asks only whether the *destination* is unbuilt. Two of the three had been
  "Corrected 2026-08-16" by removing the delivered capabilities **from the note** rather than by
  concluding that the retirement was invalid — the evidence was deleted until the check passed.
* **Of 62 capabilities marked `✅`, exactly one passes its own FR ledger** (`TECH-053`). Nineteen have
  no design document at all.

**And the half `ADR-003` had no concept of.** A test that cannot go RED proves nothing, and RED is
only available while the code is unwritten. Deferring a seam to an artifact that runs *after* the
capability ships produces a test that is green on its first execution: it asserts the present state
of the code rather than a contract the code must satisfy. `ADR-003`'s test-sequencing section moved
authorship to the story that creates the seam for exactly this reason, but drew no conclusion for the
seams whose creating story had already closed.

## Considered Options

### Option 1: keep `ADR-003`, add a third addendum

It already carries two. The scope defect is not a detail at the edge of the decision — it is the
decision's applicability condition, and three of its recorded dispositions are wrong because of it. A
reader would need the original plus three corrections to learn what is true.

**Rejected:** a document with more corrections than sections is not a decision record.

### Option 2: reopen the closed capabilities and give them the seam FRs

Directly satisfies `ADR-003` as written: the consumer owns the seam.

**Rejected:** it voids `finished-stories-immutable`, which is what makes a `✅` mean anything, and it
would reopen 62 capabilities to add FRs that — per `TECH-053` — nobody can currently falsify. It also
does not solve the RED problem: the code already exists, so the FR's test is green on arrival.

### Option 3: split the rule by build state

The owner of a seam proof depends on whether the seam's features are built. Unbuilt → the capability,
as `ADR-003` says. Closed → the story, because nothing else can hold it.

**Chosen.**

## Decision Outcome

**Chosen: Option 3.** Six clauses.

1. **An unbuilt capability owns its own integration and e2e proof.** It declares its seam FRs and
   proves them at integration/e2e tier inside its own TDD cycle, red before the code they judge.
   Nothing is deferred to a later story. This is `ADR-003`'s core, unchanged.
2. **A (sub)story holding one or more closed features owns an integration story for those features.**
   The entry is minted where missing. An **open** entry is never deleted: it is the only record that
   shipped work has not been integration-tested, and removing it hides the debt rather than paying it.
3. **End-to-end ownership is decided by span.** A path a single feature can walk belongs to that
   feature. A path crossing several features of a (sub)story belongs to that story, and passing it is
   a condition of the story closing.
4. **A test is written as soon as the interface it exercises is defined** — not when the
   implementation lands. Where the implementation is absent the test is committed as
   `pytest.mark.xfail(strict=True)` naming the blocking capability, so it fails first and proves it
   tests the path at the moment it turns green.
5. **A (sub)story may not go green while any of that is missing**, even when every feature task
   beneath it is green. Feature-level green is not story-level proof.
6. **A defect found by an integration test becomes a NEW ticket.** The story's line stays open until
   that ticket lands and the test passes. The closed capability is not edited.

### An integration story is a migration vehicle, not a permanent artifact

Its scope is the already-developed features in its (sub)story. Its work is to place every path in the
story into the structure this ADR defines, and then be discharged. It does not preserve the old shape.

| Path | Home | Mechanism |
|---|---|---|
| One feature can walk it, runnable today | the feature | backfill on contact (`specweaver-dev` §3.2c), scoped to the capability under test, with a mutant killed to prove the FR constrains something |
| Crosses several features, runnable today | the (sub)story's path inventory | one inventory row yields one cross-feature FR, numbered on the contract so `check_fr_coverage.py` reads it unchanged |
| Touches an interface not yet defined | a deferred inventory row | names its blocking capability; a gate fails that capability's delivery while the row is unwritten |

This dissolves the duplication the audit found. Six base contracts list `B-SENS-02` as their only
closed capability; its seams land on `B-SENS-02` rather than on whichever of the six reached it first.
Only journeys remain per-story.

### The (sub)story contract

The `INT-US` entry **is** the (sub)story contract — one artifact, not two. It holds the story's **path
inventory** and its **cross-feature (N)FRs**, and nothing else: a requirement provable inside one
feature belongs to that feature, never restated here (`ADR-003`'s Type A). The inventory covers every
path in the story with an owner and a status per row, including paths through unbuilt features, and it
is expected to change as contracts and scopes change.

Going forward, every (sub)story gets one, created when the first design inside it begins. That is what
makes clause 4 possible: cross-cutting tests can be written as soon as an interface is defined rather
than after the last feature ships.

## Consequences

### What changes

* **`INT-US` entries are minted again** — for any (sub)story holding closed features, and for every
  (sub)story going forward as its contract. `ADR-003`'s blanket prohibition is withdrawn; the
  prohibition survives only for **unbuilt** work, where clause 1 leaves such an entry nothing to own.
* **26 stories are in scope for migration**: 14 open base contracts, 5 add-on groups with an
  identifier, 4 needing one minted, and the 3 marked `✅` with no cited test file. Those 3 are flipped
  back to open — a `✅` nothing can verify is what `TECH-053` exists to prevent.
* **17 already-proven contracts** need inventories but have proof. Deferred to a named follow-on
  ticket, not silently.
* **`specweaver-feature`** owns the contract artifact; **`specweaver-design`** carries the trigger and
  stops if the contract is absent; **`specweaver-implementation-plan`** schedules the cross-feature
  tests from the inventory; **`specweaver-dev`** enforces the strict-xfail marker.

### What does NOT change

* **`finished-stories-immutable`.** Clause 6 exists to protect it: a defect becomes a ticket, never an
  edit to closed work. Backfill on contact (§3.2c) is the one sanctioned addition, and it adds proof
  for claims the capability already makes.
* **The 13 delivered integration contracts** keep their FR tables and their citations. This ADR
  governs what is written next.
* **Requirement ids, the citation grammar, and every ratchet.** Cross-feature FRs stay numbered
  `<ID> FR-N` precisely so no gate grammar changes.

### Reversals of `ADR-003`

| `ADR-003` said | Now |
|---|---|
| New `INT-US-NN` / `INT-US-NN-SFNN` entries are no longer minted | Minted for closed-feature (sub)stories, and for every (sub)story as its contract |
| `INT-US-25-SF01` → **CLOSED EMPTY** | Reopened — its three capabilities are closed and their cross-feature paths unproven |
| `INT-US-01-SF02` note corrected to name `E-UI-04` only | Un-retired — the sub-story ships `C-EXEC-01` and `C-EXEC-03` |
| `INT-US-01-SF03` note corrected to name `E-VAL-04` only | Un-retired — the sub-story ships `E-VAL-02` and `B-VAL-02` |

### Enforcement

Discipline-only clauses regrow the defect on the next `✅` — `check_retirement_targets.py`'s own
docstring makes that argument, and this ADR exists because a rule written in three skills was broken
anyway. Two gates are therefore required, both at the `doc` gate because both are registry-state
questions rather than diff questions:

* **`check_delivered_claims.py`** gains clause 5: a (sub)story marked green whose closed features have
  no integration/e2e evidence is a finding.
* **`scripts/check_xfail_blockers.py`** (new) fails any `xfail(strict=True)` whose named blocking
  capability is now `✅` — without it clause 4's markers decay into permanent exemptions.

`check_retirement_targets.py` also asks the wrong question on its own: "is the destination unbuilt?"
passes a retirement whose sub-story already ships a capability. The correct second question reads
group membership from `master_story_roadmap.md`, not prose in the topic documents.

The method, the identifier grammar for the migration entries, and both gates are owned by the
migration ticket rather than by this ADR.
