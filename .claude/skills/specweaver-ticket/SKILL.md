---
name: specweaver-ticket
description: "Mint a new registry ID (TECH-NNN technical-debt ticket, capability ID like C-FLOW-12,
or an INT-US-NN-SFxx sub-story) without colliding with an existing one, and register it everywhere
that must know about it. Use when the user asks to file/create/mint a TECH ticket, a new capability,
or a sub-story, or when work spins off a defect that needs its own ID."
---

# Ticket / ID Minting Skill

```
Trigger: "file a TECH ticket", "create TECH-XXX", "mint a capability",
         "new capability ID", "add a sub-story", "spin this off into its own ticket",
         "make a ticket for this"
```

## Purpose

Minting an ID looks trivial and is not. The registries are **split across multiple files and
directories**, no single document lists everything, and a collision silently steals another
ticket's identity. This skill exists because that failure has actually happened.

> [!CAUTION]
> **The failure this prevents (2026-07-25, real).** An agent grepped only
> `docs/roadmap/topics/topic_07_technical_debt.md`, saw `TECH-001`..`TECH-008`, and minted
> `TECH-009` and `TECH-010`. **Both were already taken** — `TECH-010` had a full design doc. The
> topic doc listed only a *subset*; five tickets existed solely as design-doc directories. The
> true maximum was `TECH-013`.

> [!CAUTION]
> **A second failure this prevents (2026-07-30, real).** `specweaver-pre-commit` Phase 2 told the
> agent to "raise a story to make it honest" for a vacuous-test finding. Read as a standing
> invocation of this skill, that ran Phases 1-5 to completion — registry entry, design-doc stub,
> cross-references — inside an unrelated pre-commit task, with no point where the human was asked
> whether a new ticket should exist at all. Another skill's prose is never a green light to mint.

> [!IMPORTANT]
> **STOP before Phase 3.** This skill creates a permanent registry ID and a feature-folder — undoing
> a wrong one means renumbering or orphaning a directory, not a quick edit. Before writing anything:
> 1. State the proposed ID, its title, and which family it belongs to.
> 2. Confirm with the user that a *new* ticket is wanted (as opposed to, e.g., folding the finding
>    into the story already in progress). If you arrived here via another skill's instructions rather
>    than a direct "file a ticket" / "mint a capability" ask, **that confirmation is mandatory, not
>    optional** — do not treat another skill's wording as the user's approval.
> 3. Only proceed to Phase 3 after the user says yes.

---

> [!CAUTION]
> **A ticket is a last resort, not a reflex — and filing one is not resolving anything.**
> Six tickets were filed on 2026-08-13 in a single day, several as the "outcome" of resolving an
> earlier one. The backlog grew; the verification did not. Before Phase 1, answer out loud:
>
> 1. **Can I verify this now?** Then verify it. A finding backed by a failing test beats a ticket
>    saying someone should look.
> 2. **Can I fix this now?** Then fix it. "Out of scope for this commit" is a real answer;
>    "deserves its own ticket" usually is not.
> 3. **Does this need a decision I cannot take** — scope, descope, anything changing what the
>    product does? That is the one good reason to file. Name the decision and who takes it.
>
> A ticket that only records a fact you could have checked is a note, and a note belongs in the
> design document of the thing it concerns. Full contract: `references/closure-contract.md`.

## Phase 1: Identify the Registry (do NOT skip)

Each ID family has a **different** authoritative source. Pick the right one:

| ID family | Example | AUTHORITATIVE source (decides the next number) |
|---|---|---|
| Technical debt | `TECH-014` | **`ls docs/roadmap/features/topic_07_technical_debt/`** — one directory per ticket |
| Capability | `C-FLOW-12` | `docs/roadmap/capability_matrix.md` **and** `docs/roadmap/topics/topic_NN_*.md` |
| Sub-story add-on | `INT-US-21-SF02` | `docs/roadmap/topics/topic_08_integration/US-NN_integration.md` |

> [!CAUTION]
> **`ADR-003`: do NOT mint a new `INT-US-NN` / `INT-US-NN-SFNN` for seam or capability work.**
> Integration now belongs to the capability that creates the seam, as one of **its own FRs** — which
> `check_fr_coverage.py` and `check_fr_sweep.py` already enforce. Before minting anything in this
> family, classify the claim:
>
> * **restates what a capability does** → it belongs in that capability's design. Mint nothing.
> * **a seam** (this module calls/reads/persists through another) → an FR on the **consumer**
>   capability. Mint nothing.
> * **a user-visible journey across capabilities** (*"the journey costs exactly one LLM call"*) →
>   still legitimate, as a **journey proof**: e2e tests only, declares no FRs, implements nothing.
>
> **The seam bullet's "Mint nothing" holds only while the consumer is UNBUILT.** If the consumer is
> already `✅`, `finished-stories-immutable` forbids adding the FR to it, so "it moves to the
> capability" moves it nowhere — **mint a ticket instead**, which owns the seam FR and writes the
> failing integration/e2e test first.
>
> **Retiring an existing entry follows the same rule**, and it is enforced:
> `scripts/check_retirement_targets.py` in `quality.py doc` fails a `RETIRED … by ADR-003` note
> whose destination is `✅`, is absent from the capability matrix, or is **not named at all**. When
> it fires, the retirement does not happen — pick a real disposition instead: **un-retire** (the
> seam is genuinely missing), **`CLOSED EMPTY`** (nothing left to build, only a scope decision), or
> a new ticket. See the 2026-08-16 addendum to `ADR-003` for the audit that produced this.
>
> Measured 2026-08-13: 63 pre-allocated `Sub-Story Integration (Pending Design)` entries existed and
> **not one had a design document or a feature directory**. The family's failure mode is a second
> place to make claims that no gate compares against code — `INT-US-21-SUB` advertised recursive
> decomposition that was never built, through delivery and an epic closure (`TECH-038`).

> [!WARNING]
> For **TECH** IDs the topic doc is NOT authoritative — it has historically listed only a subset.
> For **capability** IDs the matrix and topic docs *are* authoritative, and
> `master_story_roadmap.md` only references them.
>
> That last clause is not capability-specific: `master_story_roadmap.md` references **every**
> family and holds detail for none. What may appear there, and at what length, is written down
> once in `references/roadmap-placement.md` and enforced by `check_roadmap_placement.py`.

## Phase 2: Prove the ID Is Free (MANDATORY — both commands)

A directory listing alone is insufficient; an ID can be referenced from another feature's docs
before it has a directory. Run **both**:

```bash
# 1) the authoritative registry for the family
ls docs/roadmap/features/topic_07_technical_debt/

# 2) every mention anywhere in the repo — this is the collision check
grep -rhoE "TECH-[0-9]{3}" --include=*.md --include=*.py . | sort -u | tail -5
```

The new ID is `max(both) + 1`. If the two disagree, **investigate before minting** — a disagreement
means either a ticket with no directory or a directory nobody references, and both are registry
defects worth reporting.

> [!CAUTION]
> If the user reports the registry is corrupt, **research git history first** — never guess or
> renumber from the (possibly also-corrupted) current state:
> `git log -S"<string>" --oneline -- <file>` and `git log --follow --format=%h -- <file>`
> to find the introducing commit and the pre-corruption value. A mechanical rename commit is the
> usual culprit and typically damaged more than one ticket.

## Phase 3: Create the Design-Doc Stub — **TECH tickets only**

> [!CAUTION]
> **A capability is minted as a TOPIC ENTRY and nothing else. Do not write it a design document.**
> There is a level between the registry and the design: the decision to build it. Creating a stub
> at mint time takes that decision on someone's behalf and inflates the design corpus with
> documents for work nobody has scheduled.
>
> Measured 2026-08-16 across 153 capabilities: **67 of the 82 unbuilt ones have no feature
> directory at all**, while **54 of the 62 delivered ones do** — the design document appears when
> the work is picked up. Of the 15 unbuilt exceptions, twelve are active routing-queue candidates
> and three were minted the same day by an agent following this phase as if it applied to
> capabilities. `A-VAL-03` is the reference shape: a topic entry, no directory.
>
> **TECH is genuinely different** and that is why this phase exists: its authoritative registry is
> `ls docs/roadmap/features/topic_07_technical_debt/`, one directory per ticket, so a TECH ticket
> without a directory does not exist. Capabilities are registered in the matrix and the topic doc,
> where the entry *is* the artefact.
>
> | Family | Minting creates | Design document |
> |---|---|---|
> | **TECH** | registry entry **and** a design-doc stub | the stub, replaced by `specweaver-design` |
> | **Capability** | the topic entry and matrix cell **only** | written when `specweaver-design` runs |
>
> Research that outlives the ticket — a census, a measurement, an argument — goes in
> `docs/analysis/`, not into a design document written early to hold it. An `R-ENTRY` topic entry
> is four lines; that is the point of it, not a limit to route around.

Every TECH ticket has `docs/roadmap/features/<topic_dir>/<ID>/<ID>_design.md`:

```markdown
# Design: <Title — the same words used in the registry entry>

- **Feature ID**: <ID>
- **Epic**: <Topic NN (Name)>
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: <where it was found — feature, phase, date>

## Problem Statement
## Candidate Approaches (not yet designed)
## Non-Goals (proposed, pending design)
## Next Step
```

The **title must match the registry entry name exactly**. Drift between the two is a recurring
registry defect — three tickets had drifted as of 2026-07-25.

## Phase 4: Register It

1. Add the entry to the topic doc **under the matching `## ` section** (Architecture &
   Restructuring, Context Loading & RunContext Anti-Patterns, Security & Validation, …).
   Inserting before an arbitrary neighbour misfiles it — verify placement afterwards.
2. Link the design doc: `> [Description](../features/<topic_dir>/<ID>/<ID>_design.md) | …`
3. Cross-reference from wherever the ticket was discovered (the design / implementation plan /
   walkthrough of the feature that spun it off), so the origin is traceable both ways.
4. Capability IDs only: update **both** `capability_matrix.md` and the topic doc.

## Phase 5: Verify (MANDATORY)

```bash
python scripts/quality.py doc --only roadmap_sync
grep -n "^## \|^\* \*\*.TECH-" docs/roadmap/topics/topic_07_technical_debt.md   # section placement
```

Then confirm by reading: registry name and design-doc title are identical, the entry sits in the
right section, each ID appears exactly once, and no other ticket uses that ID for a different
subject.

---

## Scope Rules

- **A defect in delivered code becomes a NEW ticket, never an edit to the delivered story's entry**
  (finished-stories-immutable). Say so explicitly in the ticket.
- **Do not defer a live defect to an unbuilt feature.** If some future capability would "fix it
  anyway" but is unscheduled or blocked, the defect still gets its own ticket and lands first.
  State that sequencing constraint in the ticket.
- **Make it actionable, not a wish.** Measure it (line counts, reference counts, affected files),
  name the origin commit where there is one, list explicit out-of-scope items so the ticket cannot
  expand into a crusade, and state the execution constraint (e.g. "one module per commit, never
  bundled into a feature commit").
- **Closing is a claim about the implementation, not about the work.** A `🟢`/`✅` asserts the
  implementation stands up to the ticket's promise: every FR proven by a test
  (`check_fr_coverage.py <ID>` exits 0), every unbuilt FR deleted from the FR table so the descope
  is visible, and the `Verifiable Proof` naming test FILES that pass and do not skip. Measured
  2026-08-13: **46 of 103 capabilities fail that bar while marked delivered.** Full contract:
  `references/closure-contract.md`.
- **Filing a follow-up is not a closure condition.** Resolving a ticket by filing another one
  defers the work and inflates the backlog.
- **Ship the guardrail with the fix.** If the ticket removes a pattern, it should also add the check
  that stops it regrowing — otherwise it will.

> [!IMPORTANT]
> **CHECKPOINT:** ID proven free by both commands, design-doc stub created, registry entry filed in
> the correct section, cross-references added, verification commands green.
