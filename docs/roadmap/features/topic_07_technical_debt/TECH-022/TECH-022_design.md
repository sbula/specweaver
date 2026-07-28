# Design: TECH Registry Split-Brain — Roadmap and Topic Doc Disagree on Seven Statuses

- **Feature ID**: TECH-022
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: User report, 2026-07-28 — "in my browser I am just able to see up to TECH-013"

## Problem Statement

The TECH backlog has **two** registries and neither is complete. They were made to disagree in a
single commit and have never been reconciled.

**`master_story_roadmap.md` §Technical Debt** carries full story entries — Benefit, Core Required
(MVS) with per-SF checkboxes, Verifiable Proof. **`topics/topic_07_technical_debt.md`** carries the
one-line-plus-blockquote registry entries.

| | roadmap | topic_07 |
|---|---|---|
| IDs present (before this ticket) | 12 (`001`–`011`, `013`) | 21 (`001`–`021`) |
| Status accuracy | tracks delivery, with proofs | stale for the pre-`014` block |

Two independent defects:

**D1 — the roadmap section stopped growing at `TECH-013` (fixed 2026-07-28).** Every ticket minted
after 2026-07-20 — `TECH-014`…`TECH-021`, plus `TECH-012` which was skipped — was filed into
`topic_07` and never given a roadmap entry. Eight of the nine were minted during INT-US-21, and the
`specweaver-ticket` skill's Phase 4 does not require a roadmap entry, so nothing caught it. **This
is what the user actually saw**: scrolling the roadmap, the file ends at `TECH-013`. Repaired in the
same commit as this ticket — nine entries added, 21/21 now present.

**D2 — seven statuses contradict each other (OPEN, this ticket).**

| ID | roadmap | topic_07 |
|---|---|---|
| `TECH-001` | 🟢 (SF-01/02/03 all ✅, proof cited) | 🔜 |
| `TECH-002` | 🟢 (proof cited) | 🟡 |
| `TECH-005` | 🟢 (SF-1/2 ✅, proof cited) | 🟡 |
| `TECH-009` | 🟢 | 🔜 |
| `TECH-010` | 🔴 | 🔜 |
| `TECH-011` | 🔴 | 🔜 |
| `TECH-013` | 🔴 | 🔜 |

`git log -S` puts **both sides of the `TECH-001` contradiction in the same commit** — `e73a58c9`
(2026-07-12), *"Refactor TECH story names to 3-digit padded format"*. A mechanical rename wrote
🟢 into one file and 🔜 into the other in one shot. This is the **same commit** the
`specweaver-ticket` skill already documents for corrupting `TECH-009` via the pre-scheme `TECH-08`
collision — a third distinct kind of damage from one rename, which is why that skill says to
git-blame before renumbering.

## Why not just flip them

The obvious move — trust `topic_07`, since the roadmap "only references" the registries — is
**wrong here, and that is the trap worth recording.** For the pre-`014` block the roadmap is the
*more* current record: it tracked delivery with sub-feature checkboxes and named proof files, and
those files exist on disk (`test_cqrs_e2e.py`, `test_dispatcher_sf3_integration.py`,
`test_af60fd3509a2_tech_005_rename_tables.py` all verified present 2026-07-28). `topic_07`'s
markers for those IDs are the original stub-era values, never updated on delivery.

So the authority is **per-ID, not per-file**, and resolving it needs evidence per ticket — not a
bulk rewrite in either direction. Flipping seven statuses on a general rule would silently
re-open delivered work or silently close undelivered work, and either is worse than the current
visible disagreement.

## Candidate Approaches (not yet designed)

- Per-ID adjudication: for each of the seven, establish delivery from commits and the cited proof,
  then correct whichever file is wrong. Evidence recorded in the ticket.
- Decide which file owns TECH status, and make the other derive from it or drop the marker
  entirely. Two hand-maintained copies of the same fact will drift again by construction.
- **Ship the guardrail** (this is the part that stops D1 recurring): extend
  `scripts/check_roadmap_sync.py` to assert every ID under
  `features/topic_07_technical_debt/` has an entry in **both** registries with the **same** status
  marker. D1 survived eight tickets because nothing checked; a rule that is only written down is
  the same rule that did not stop this.
- Add the roadmap entry to `specweaver-ticket` Phase 4, which currently requires only the topic doc.

## Non-Goals (proposed, pending design)

- Not a re-litigation of whether the pre-`014` work was well done — only what its status *is*.
- Not a restructure of either document's format.
- Not the `TECH-009` / pre-scheme `TECH-08` ID collision — already adjudicated in `adr_002` and the
  `specweaver-ticket` skill; `TECH-009` is settled as the Subprocess Migration ticket.
- Not bundled into a feature commit.

## Next Step

Run the `specweaver-design` skill. Start from `e73a58c9` and walk each of the seven forward.
