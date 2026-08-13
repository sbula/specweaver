# Design: Registry Entries Carry Content Belonging Four Layers Down

- **Feature ID**: TECH-044
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: 2026-08-13, raised by the user while reviewing `TECH-017`'s parser fix: a
  1886-character Verifiable Proof line prompted "should a line that long be legal at all?" —
  which is the right question, and a bigger one than the parser bug that exposed it.

> **ID note.** `TECH-042` and `TECH-043` were skipped deliberately: both are live fixture IDs in
> `tests/unit/scripts/test_check_story_preconditions.py`, and minting either as a real ticket would
> manufacture exactly the one-ID-two-meanings collision `TECH-039` exists to fix. Freeing them by
> renumbering those fixtures into an obviously-synthetic range is worth doing and is **not** this
> ticket's job.

## Problem Statement

`R-DEPTH` (shipped 2026-08-13) caps every line in `docs/roadmap/` at 200 characters and freezes the
existing **2341 over-long lines across 278 files**. The ratchet stops new ones. This ticket is the
backlog it froze.

The measurement that motivated it:

| Tree | over 200 | longest |
|---|---|---|
| `master_story_roadmap.md` | 1.6% | 363 |
| `topics/topic_*.md` | **33.5%** | **5624** |
| `topics/topic_08_integration/US-*.md` | 9.6% | 1909 |
| `features/**/*_design.md` | 7.6% | 1830 |

All ten worst lines in the tree are `TECH` entries, most written during the 2026-08-12/13 debt
sessions. `R-LENGTH` capped the roadmap with the rationale *"detail lives in the topic doc and the
design"*, nothing then checked the topic doc, and the topic doc grew 5624-character lines.

## The layer map — measured, not assumed

The obvious fix is "push the detail from the topic entry into the design doc". That is wrong,
because a 5624-character entry usually holds content for three layers at once. But the tree is
**four layers, not six** — the directory listing suggests six and the practice is four:

| Layer | Path | Folders with it | What belongs |
|---|---|---|---|
| 1 | `master_story_roadmap.md` | — | ID, short name, link, status. One line. |
| 2 | `topics/topic_NN_*.md` | — | The entry: what, why, how sequenced. A **summary**. |
| 3 | `<ID>_design.md` | **88%** | Problem, evidence, approaches, non-goals, guardrail. |
| 4 | build record | 62% / 6% / 1% | What happened while building: plan before, walkthrough after, review record. |

Layer 4 is **one concern with three optional file kinds**, not three layers: implementation plans
cover 62% of feature folders, walkthroughs 6% (a July practice that stopped), review records 1%
(one ticket). Modelling them as separate layers over-fits something almost nothing uses — and the
naming has already drifted three ways each (`sfN_implementation_plan` / `sfN_impl_plan` /
`implementation_plan`), which is what an unowned convention looks like.

**Decisive evidence:** the last 13 TECH tickets have exactly one document each — the design.

### The knowledge tree is a different axis, not a deeper layer

`docs/analysis/`, `docs/architecture/06_lessons_and_future/`,
`07_architectural_decision_records/` and `docs/dev_guides/` are **not** deeper than a design. They
are for a different reader — someone who will never open the ticket. A lesson in `anti_patterns.md`
is not "more detail than the design"; it is the part that outlives it. Depth and audience are
orthogonal, and an earlier draft of this ticket listed them as one ladder.

### Why there is no character budget per entry

Rejected after measuring. Within `master_story_roadmap.md` alone the kinds have genuinely different
natural sizes — a `### US-N` block runs 18 lines (max 62), while sub-story, capability and `TECH`
entries are one line each (medians 76 / 64 / 138 chars). One number cannot fit them, and per-kind
numbers would be arbitrary. **`R-DEPTH`'s per-line 200 works precisely because it is kind-agnostic**
— all three single-line kinds already sit under it with nobody tuning anything. The fix for a
5624-character entry is that it becomes a *block of short lines*, exactly as a `US-N` section
already is; how much content belongs there is a layer question, not a character count.

## Non-Goals (proposed, pending design)

- **Deleting anything.** The remedy is redistribution. `scripts/check_entry_orphans.py` exists to
  make that checkable and must report zero orphans for an entry before it is shortened.
- Re-wording delivered entries' *claims*. Moving text is not licence to revise what it says.
- Lowering `MAX_LINE`, or adding a second threshold per layer. One rule, one number.
- The `topic_08_integration` contracts, which have their own shape and their own gate
  (`check_proof_tier.py`) — worth a separate pass, not this one's scope.

## Candidate Approaches (not yet designed)

1. **Worst-first, ticket by ticket**, each one: run `check_entry_orphans.py <ID>`, move each orphan
   fact to the layer that owns it, shorten the entry, re-freeze the ratchet down. Slow, verifiable,
   and each step is independently committable. `TECH-035` (5624), `TECH-017` (4963) and `TECH-037`
   (4284) are the top three.
2. **Layer-at-a-time**, e.g. all of `topic_07` before any design docs. Fewer context switches,
   but a half-done topic doc is harder to review than a half-done backlog.
3. **Mechanical wrap first, redistribute later.** Cheapest, and it would clear the ratchet without
   fixing anything — the content stays at the wrong depth and the count says it is solved. Rejected
   for exactly that reason, and recorded so it is not re-proposed as an optimisation.

## The scaffolding is deleted when this ticket closes — enforced, not promised

`scripts/check_entry_orphans.py` exists only to make this redistribution safe. When the R-DEPTH
backlog reaches zero there is nothing left to redistribute and it has no job.

That deletion is a **failing test**, not a note:
`test_entry_depth.py::TestTheOrphanCheckerIsDeletedWhenDone` asserts the checker exists **exactly
while** the baseline is non-empty, so the suite demands its removal the moment the backlog empties
— and demands its restoration if it is deleted early. A promise in a docstring would not survive
the session that made it; this repo watched a `pytest.skip` guard outlive its own written-down
lesson by eighteen days.

## Known gap: nothing bounds a delivery record's SIZE

R-DEPTH caps line length, not file length, and `check_file_sizes.py` runs on `src tests scripts`
only — `docs/` is not covered by anything. So `TECH-035_delivery.md` (21 KB) can grow without
limit, and so can any design doc; the largest today is 45 KB. Raised by the user while reviewing
the first redistribution and recorded rather than fixed, because a size rule for prose needs the
same per-kind argument that killed the entry-size cap: a design and a one-paragraph stub have no
common number.

## Guardrail

Already shipped with the finding: `R-DEPTH` (`scripts/_entry_depth.py`, `doc` gate, ratcheted per
file) and the advisory `scripts/check_entry_orphans.py`. What is missing is a written statement of
the layer map above — `TECH-026` wrote down what belongs in the *roadmap* and stopped there, which
is the same one-level-only mistake in the documentation of the rule as in the rule itself. The
design should decide where that map lives so it is findable: a `specweaver-ticket` reference is the
obvious candidate, since that skill already owns registry placement.

## Next Step

Run the `specweaver-design` skill against this stub before any implementation.
