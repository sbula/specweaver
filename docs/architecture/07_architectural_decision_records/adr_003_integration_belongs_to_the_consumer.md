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

> **Tracked 2026-08-15 as `TECH-049`.** A coverage audit of this decision confirmed the rule reached
> five of seven skills as instruction and **zero scripts as enforcement**. That makes this paragraph
> the weakest link in the chain the ADR relies on: every downstream gate trusts a red that nothing
> observes. See `docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_design.md`.
>
> The same audit found the **e2e half of this rule had not reached the skills at all** — the tier
> table named e2e, but only the seam test carried a "write it before the code" sentence, and
> pre-commit's tier profile (*"integration and e2e arrive at `sf` and `feature`"*) reads as licence
> to author them late. Corrected the same day in `specweaver-implementation-plan` and
> `specweaver-dev`, including the clarification that this example's *"steps"* are **pipeline** steps
> inside the test, not commit boundaries.

### Risk accepted

*"Is US-21 integrated?"* stops having a one-document answer and becomes *"are these FRs proven?"*.
That is only as trustworthy as the ratchets, and it is a deliberate trade: the one-document answer
was wrong for `INT-US-21-SUB` for months, and the ratchets are now measured, probed and blocking.

## Addendum, same day: how a seam is DISCOVERED

The decision above says a seam becomes an FR on the consumer. It did not say how anyone finds the
seam in the first place — and an FR is a leaf. You only write *"SHALL deserialise
`handover_context` via `HandoverContext.from_json_str()`"* once you already know the seam exists.
That discovery step is what the integration story used to supply: late, and in the wrong document.

The first attempt to fix this put a "surfaces and interactions" section **before** FR derivation.
That is wrong. The dependency runs both ways: an FR determines the data you need, which names the
surface you consume — but the surface that *actually exists* constrains what the FR can promise,
which rewrites the FR. Ordering it either way fails. It is a **fixpoint iteration**:

```
FR states an outcome -> data it must read/send -> whose module provides it
                     -> what that surface really offers -> back to a now-DIFFERENT FR
```

The loop already happens informally — the design skill has always derived FRs and validated APIs in
one pass. **What was missing is a record of where it converged**, so nobody could tell an FR whose
data dependency was verified from one where it was assumed.

`D-INTL-06` FR-3 is the cost of that. It reads *"Selective Filtering | MemoryHydrator | Filter out
ARCHIVED tasks, tasks outside the project, DONE tasks > 24h old"* — and the hydrator does not filter
at all. It passes `max_age_hours=24` to the repository (`hydrator.py:162`). The FR and the interface
disagreed, the FR was never updated, and it surfaced only in this audit as *"FR-3's proof would have
to live in the provider's test file."*

**Encoded as a Requirement–Surface Bindings table**, one row per FR that crosses a module boundary,
whose termination condition is that every row names a surface someone has **read** — citing the file
or symbol opened, never "per the design". That is the standard `check_story_preconditions.py`
already applies to prerequisites, and for the same reason: `INT-US-21` recorded three prerequisites
as `✅` and all three were materially broken.

Three non-convergent outcomes, all findings rather than failures: the surface provides it (the FR
stands, and its proof tier is integration); the wrong side owns it (rewrite the FR — this is FR-3);
the surface does not exist (the **provider** needs a new FR, which is a cross-story dependency and
fires a HITL gate rather than being deferred to "integration", the exact deferral this ADR removed).

NFRs fall out of the same table: a surface's latency budget, payload cap or failure mode becomes
your NFR. `D-INTL-06`'s 2048-token and 8KB bounds came from the surface, not from a guess.

Encoded in: design skill Phase 2 A.7 (record surfaces with real signatures), Phase 3 A.1b–A.1d
(the loop, the table, the outcomes, the gate), Phase 5 (the template section), Phase 6.0 (the
convergence check), and implementation-plan Phase 1.1 (the bindings say where integration tests go).

## Addendum, 2026-08-16: a retirement is only valid while its target is UNBUILT

Every retirement note this ADR produced makes the same promise:

> The scope above is NOT descoped — it moves to `X`, which owns its own integration and e2e
> proof as FRs rather than a separate add-on restating them.

**That promise is unsatisfiable when `X` is already `✅`.** `finished-stories-immutable` forbids
adding an FR to a delivered story, so there is no design that will ever own the seam. The scope is
retired from one side and never lands on the other: homeless, and invisible to every gate, because
`check_fr_coverage.py` can only judge an FR that someone wrote.

**The rule, and it is mechanical:** a retirement is valid **if and only if every capability it
names is unbuilt**. If any target is `✅`, **the retirement does not happen** — the add-on stays
open, because the only honest reading of "it moves to a delivered story" is that it moved nowhere.
Closing it afterwards is then a real decision with three legitimate outcomes: **un-retire** (the
seam is genuinely missing), **close empty** (nothing is left to build, only a scope decision), or
mint a **new ticket** that owns the seam FR — the ticket skill's existing rule that *"a defect in
delivered code becomes a NEW ticket, never an edit to the delivered story's entry"*. Whichever is
chosen, the integration or e2e test is written first and fails because the wiring does not exist,
which is the whole reason this ADR moved the tests earlier.

### What the re-audit found

Re-checked against the code, entry by entry. `bb789a29` deleted **63 `Sub-Story Integration
(Pending Design)` lines**, and **68 distinct ids** once prose mentions are counted.

| | |
|---|---|
| named no capability and had no topic-doc entry | **46** — nothing to restore; there is no scope to put back |
| carried a real entry in `topics/topic_08_integration/` | **22** |
| …of those, target only unbuilt capabilities | **17** — correctly retired |
| …of those, target at least one delivered `✅` | **5** — the class the rule failed to protect |
| …of those, genuinely homeless work | **1** |

The one is **`INT-US-03-SF01` (Multi-Language Test Support) → `D-VAL-03` ✅**. `resolve_runner` is
polyglot, but `sw implement` cannot reach a non-Python branch: the pipeline hardcodes
`src/{stem}.py` and `tests/test_{stem}.py`, and the generator tags artifacts `"python"` and strips
` ```python ` fences. **Un-retired**, with the roadmap line restored.

The dispositions of the other four, each checked against the code rather than the document:

| Entry | Found | Disposition |
|---|---|---|
| `INT-US-09-SF01` | `B-EXEC-01` is threaded end-to-end from `QARunnerAtom`, but **opt-in**; the add-on wanted it enforced | **un-retired** — a product decision nobody has taken |
| `INT-US-25-SF01` | all three targets delivered *and* exercised by its own base contract | **closed empty** — nothing moved, because nothing was left |
| `INT-US-01-SF02` | `C-EXEC-01`/`C-EXEC-03` already live; blocked on `E-UI-04`, unbuilt | note corrected to name `E-UI-04` only |
| `INT-US-01-SF03` | `E-VAL-02`/`B-VAL-02` already wired; blocked on `E-VAL-04`, unbuilt | note corrected to name `E-VAL-04` only |

**Enforced by** `scripts/check_retirement_targets.py`, in `quality.py doc`. It reads the
destination clause of every retirement note and fails when a target is `✅`, when a target is
absent from the capability matrix, or when the note **names nobody at all** — `INT-US-25-SF01` read
*"it moves to the capability that builds it"*, the unfalsifiable prose this ADR set out to delete,
wearing the ADR's own name.

Two further defects surfaced while writing it, both the same shape and both in `_registry_orphans`:
`"RETIRED" in body` also matches **`UN-RETIRED`**, so a withdrawal kept absolving the entry and its
missing roadmap line went unreported — the check that exists to catch exactly this correction was
blind to it. And **`CLOSED EMPTY`** had no expression at all, so an add-on with nothing left to
build could only exit by claiming a move that never happened. Both fixed with word-boundary
matching and a second sanctioned disposition.

Without enforcement this clause is discipline-only and the defect regrows on the next `✅` — three
of the five above sat one delivery away from it.

