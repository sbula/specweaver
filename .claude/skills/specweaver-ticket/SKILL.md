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
