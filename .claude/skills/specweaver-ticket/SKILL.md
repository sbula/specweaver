---
name: specweaver-ticket
description: "Mint a new registry ID (TECH-NNN technical-debt ticket, capability ID like C-FLOW-12, or an INT-US-NN-SFxx sub-story) without colliding with an existing one, and register it everywhere that must know about it. Use when the user asks to file/create/mint a TECH ticket, a new capability, or a sub-story, or when work spins off a defect that needs its own ID."
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

## Phase 1: Identify the Registry (do NOT skip)

Each ID family has a **different** authoritative source. Pick the right one:

| ID family | Example | AUTHORITATIVE source (decides the next number) |
|---|---|---|
| Technical debt | `TECH-014` | **`ls docs/roadmap/features/topic_07_technical_debt/`** — one directory per ticket |
| Capability | `C-FLOW-12` | `docs/roadmap/capability_matrix.md` **and** `docs/roadmap/topics/topic_NN_*.md` |
| Sub-story add-on | `INT-US-21-SF02` | `docs/roadmap/topics/topic_08_integration/US-NN_integration.md` |

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

## Phase 3: Create the Design-Doc Stub

Every ticket has `docs/roadmap/features/<topic_dir>/<ID>/<ID>_design.md`:

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
- **Ship the guardrail with the fix.** If the ticket removes a pattern, it should also add the check
  that stops it regrowing — otherwise it will.

> [!IMPORTANT]
> **CHECKPOINT:** ID proven free by both commands, design-doc stub created, registry entry filed in
> the correct section, cross-references added, verification commands green.
