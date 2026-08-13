# ADR 003: Integration Belongs to the Consumer, Not to a Separate Story

**Status:** Accepted
**Date:** August 13, 2026
**Context:** `TECH-017` proof audit — measured evidence that the capability/integration split
produced unproven capabilities and unfalsifiable contracts

## Context and Problem Statement

Every user story carries a parallel `INT-US-NN` **integration contract**, and every sub-story add-on
pre-allocates an `INT-US-NN-SFNN` integration entry. The intent was sound: a capability proves
itself, and a separate artifact proves the capabilities work *together*.

The `TECH-017` audit measured what the split actually produced.

**The integration story did capability work.** `git log` shows 4 of `INT-US-28`'s 5 unit-test files
were created on 2026-05-10 — the day it was delivered. **41 of its 56 unit tests were written
during the integration story**, testing `MemoryHydrator` sanitisation, handover fail-safes and
`_build_base_prompt`. Those are `B-INTL-09`'s and `D-INTL-06`'s own requirements.

**And the credit landed in the wrong place.** Because the tests were cited by the contract,
`check_fr_coverage.py` reported **both capabilities `BLOCKED` — 9 declared requirements, zero cited
tests each** — while the contract read as proven by 88 tests for a seam with 6 claims. Two
capabilities read as untested for three months while their tests sat in the tree, passing.

**The contract became a second place to make claims about a capability, where nothing checked
them.** `INT-US-21-SUB` advertised *"Recursive Planning … implements iterative decomposition,
generating a structured DecompositionPlan by resolving the AST graph into sub-tasks."* Measured
against `src/` on 2026-08-13, the shipped decomposer makes **one** LLM call, has no recursion, and
returns a flat `list[ComponentChange]` with no nesting to recurse into. `TECH-038` resolved that the
scope was wrong, not the wording — the recursion was designed in `C-INTL-01`, never built, never
descoped, and the contract kept advertising it. A registry entry survived delivery *and* an epic
closure while describing behaviour that does not exist.

**The pre-allocation never paid off.** 63 `INT-US-NN-SFNN: Sub-Story Integration (Pending Design)`
entries exist in `master_story_roadmap.md`. **None has a feature directory.** They are slots reserved
for an artifact that, on the evidence above, would have restated capability claims in a document no
gate compares against code.

## Considered Options

### Option 1: Keep the split, enforce it harder

Add a checker that a contract may not cite unit tests, and that a capability must prove its own
requirements before an integration story may close.

* **Pros:** No process change; the tier rule already exists in the implementation-plan skill.
* **Cons (fatal):** It treats the symptom. `INT-US-28`'s unit tests were not a mistake of
  discipline — they were the honest response to integrating two capabilities that shipped
  incomplete. Forbidding them would have blocked the integration without making the capabilities any
  more complete. The rule already said *"unit-test-heaviness is a diagnostic"* and it fired
  correctly; nobody read it, because nothing ran it.

### Option 2: Abolish integration stories entirely

Fold all integration into the capability stories; delete the `INT-US` family.

* **Pros:** No second place to claim anything. Every requirement has exactly one owner.
* **Cons (fatal):** It discards the half that works. *"`sw implement` generates code **and** tests,
  runs them, runs code rules C01-C08, and auto-fixes lint, all in one autonomous loop"* and *"the
  journey costs **exactly one** LLM call"* are product-level claims that **no capability owns and
  none ever will**. Deleting the artifact deletes the only statement of what the product does end to
  end.

### Option 3: Split the artifact by the kind of claim it makes (Chosen)

The 42 claims across the 13 delivered contracts are three different things wearing one name:

| Kind | Example claim | Owner under this ADR |
|---|---|---|
| **A — capability restatement** | *"`B-INTL-09` provides a persistent SQLite schema with CRUD, OCC concurrency, circuit breakers, zombie recovery"* | **Deleted.** The capability's design is the single place its behaviour is claimed. |
| **B — seam** | *"`_build_base_prompt()` calls `MemoryHydrator` to inject memory context into every LLM prompt"* | **The consumer capability**, as one of its own FRs. |
| **C — journey** | *"the journey costs exactly one LLM call"* | **A journey proof** — e2e tests only, implements nothing. |

## Decision Outcome

**Chosen: Option 3.**

### A seam belongs to the consumer

`D-INTL-06` reads `B-INTL-09`'s `handover_context` column. Consuming it correctly — deserialising,
validating, failing safe — is **`D-INTL-06`'s requirement**, not a third party's observation about
two other modules. So a seam claim stops being prose in a contract and becomes an **FR on the
consumer**, which means the machinery built for `TECH-017` and `TECH-047` already enforces it:
`check_fr_coverage.py` demands a plan that owns it and a test that cites it, `check_fr_sweep.py`
ratchets it, and the citation grammar in `scripts/_citations.py` makes the attribution precise.

No new checker is required. That is the point: this decision converts an unfalsifiable prose claim
into a requirement the existing gates already judge.

### Seams have two ends

If the consumer owns the FR, a change in the **provider** has no story-level reason to revisit it.
That is acceptable and needs no mechanism: the seam test is integration-tier and runs in the whole
suite, so a provider change breaks it there. Ownership decides who *writes* and *maintains* the
test, not who runs it.

### Journeys survive, and stop pretending to implement

A journey artifact's only deliverable is e2e proof of a user-visible flow across capabilities. It
declares no FRs of its own, builds nothing, and writes no unit tests — if it finds itself writing
one, that is the diagnostic that a capability shipped incomplete, and the finding belongs to that
capability (`TECH-017` FR-6).

### Why now, and not six months ago

This decision moves trust from *"a document says the integration works"* to *"the ledger says every
requirement is proven"*. That trade is only safe once the ledger is trustworthy, and until
2026-08-13 it was not: no script in the repo contained the string `NFR`, a bare `FR-5` was credited
to every story a file happened to name, and a docstring saying *"FR-1, FR-6 and FR-7 are
deliberately NOT proven here"* marked all three covered. Those are fixed, ratcheted and probed. The
timing is the argument — the same decision taken earlier would have replaced a weak check with none.

## Consequences

### What changes

- **New `INT-US-NN` / `INT-US-NN-SFNN` entries are no longer minted for seam or capability work.**
  Seam claims become FRs on the consumer capability when its design is written.
- **63 pre-allocated `Sub-Story Integration (Pending Design)` placeholders are removed** from
  `master_story_roadmap.md`. None had a design document, a feature directory, or any content beyond
  the placeholder line.
- **Integration and e2e tests are written by the story that creates the seam**, at the commit
  boundary where the interface first exists — see "Test sequencing" below.

### What does NOT change

- **The 13 delivered integration contracts stay exactly as they are.** `finished-stories-immutable`
  applies, and `TECH-017`'s matrix is mid-assessment against them. This ADR is about what gets
  minted next, not a retroactive rewrite.
- **`INT-US-21`'s journey claims and their proof stay.** They are Type C and remain valuable.
- Requirement ids, the citation grammar, and every ratchet are untouched.

### Test sequencing — the reason this is safe

A test written after the code it covers has never failed for the right reason. So for each seam
claim, the test is written **at the boundary where the interface first exists and the behaviour does
not yet** — typically between step *n−1* and step *n*, where step *n−1*'s output defines step *n*'s
interface. `C-EXEC-06` FR-8 is the worked example: a *"multi-step, freshly-generated-file e2e"*
where step 1 generates a file and a later step consumes it. That test is only meaningful written
between the two steps.

The implementation plan records the red and its reason at that boundary. This is the one piece of
evidence a `Proves:` tag can never supply — that the test **can** fail. It is a partial answer to
`TECH-025` NFR-3 (*"every `Proves:` tag names a test that would fail if that FR's behaviour
regressed"*), which nothing currently checks.

### Risk accepted

*"Is US-21 integrated?"* stops having a one-document answer and becomes *"are these FRs proven?"*.
That is only as trustworthy as the ratchets, and it is a deliberate trade: the one-document answer
was wrong for `INT-US-21-SUB` for months, and the ratchets are now measured, probed and blocking.
