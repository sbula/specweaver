# Design: Roadmap Placement Contract — One Registry ID, One Line

- **Feature ID**: TECH-026
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Found 2026-08-08 during `TECH-025` SF-02. Asked whether sub-features were recorded
  anywhere, the agent compared `TECH-025`'s roadmap entry to `TECH-001`'s and `TECH-006`'s, judged
  it "inconsistent", and added all seven of `TECH-025`'s **design-document sub-features** to
  `master_story_roadmap.md`. The user's standing rule is that the master roadmap carries names and
  prerequisites only. The rule is written down **nowhere in the repository** — so the agent derived
  a convention from the two entries that already violate it, and reproduced the violation.

## Problem Statement

No document states what belongs in `docs/roadmap/master_story_roadmap.md` versus a topic doc versus
a feature's own design document. The actual convention is visible in the file and is nearly
universal, but it has never been written down, so it is enforced only by whoever happens to notice.

**The convention, read off the file:** one registry ID = one line — ID, short name, link to its
design doc, status flag. A design document's `SF-NN` decomposition never appears.

**Evidence it is the convention:**

| Entry | Sub-features in its design | Lines in the roadmap |
|---|---|---|
| `B-INTL-09` (Agent Memory Bank) | 4 | **1** |
| `C-FLOW-02` (Router-based flow control) | 1 | **1** |

`B-INTL-09` is structurally identical to `TECH-025` — a multi-sub-feature design — and gets a single
line.

**Measured violations (2026-08-08), the full repair list:**

| Entry | Illegal nested SF lines |
|---|---|
| `TECH-001` | 4 |
| `TECH-005` | 3 |
| `TECH-006` | 2 |
| `TECH-009` | 2 |
| `TECH-025` | 7 — added 2026-08-08 by the session that found this; TECH-025 reverts its own |
| **Total** | **18** (11 pre-existing) |

**Every violation is in the TECH family. Zero US-N or capability entries deviate.** That asymmetry
is the finding: an agent looking for precedent inside `TECH-NNN` sees the convention broken four
times out of the ~25 entries there and never reaches the ~28 clean US-N entries. The bad examples
are exactly where a TECH ticket's author will look.

**The trap that makes this easy to get wrong.** Two different things are both spelled "SF":

- `INT-US-21-SF01` — a **sub-story add-on**. Minted, registered in
  `topics/topic_08_integration/US-NN_integration.md`, has its own design. **Belongs** in the
  roadmap, and `US-21`'s entry lists exactly these.
- `SF-01` in a design's Sub-Feature Breakdown — **internal decomposition**. No registry ID, no
  independent existence, exists only to sequence one ticket's work. **Never** belongs.

`US-21` lists `INT-US-21-SF01` and `INT-US-21-SF02`. It does **not** list `INT-US-21`'s design-doc
SF-01/SF-02/SF-03. Both are "SF"; only one is an ID.

**Three contributing instruction defects, measured:**

1. **No contract exists.** No skill, template or doc defines the split. The nearest thing is
   `specweaver-ticket/SKILL.md:56-59`, which says `master_story_roadmap.md` "only references"
   registries — but scopes that sentence to *capability* IDs and says nothing about sub-features.
   It also lives in the ticket-minting skill, which is not running when a pre-commit updates state.
2. **An ambiguous mandatory order.** `specweaver-pre-commit/references/phase-6-documentation.md`
   §6.3.1: *"You MUST physically update `master_story_roadmap.md` … check off boxes `[x]` for the
   User Story and any **Add-Ons** you implemented."* In roadmap vocabulary "Add-Ons" means
   `INT-US-NN-SFxx` sub-story IDs, which legitimately belong. Read as "sub-features", it is a
   standing order to do the wrong thing — and nothing in the file disambiguates.
3. **Four entries model the error, all in the same family.** `TECH-001`, `TECH-005`, `TECH-006` and
   `TECH-009` are what an agent finds when it looks for precedent inside Topic 07 — and precedent in
   the artifact beat the rule. The ~28 clean `US-N` entries are never reached, because nothing tells
   the agent to look outside the family it is already working in. That is the navigational failure
   the hint in *Next Step* exists to prevent.

This is the same defect class as `TECH-019` — instructions that do not match intended reality,
executed as truth — and the same shape of fix: repair the instances, then ship the guard.

## Candidate Approaches (not yet designed)

- **Write the contract once**, as a shared reference owned by `specweaver-ticket` (which already
  owns the ID registries), following the `references/test-quality.md` precedent: one home, several
  callers, cross-referenced by full path.
- **Point the callers at it** — `specweaver-pre-commit/references/phase-6-documentation.md`
  (disambiguate "Add-Ons"), `specweaver-design/references/phase-5-document.md` (the Sub-Feature
  Breakdown is the only home for SFs), `specweaver-ticket/SKILL.md` (generalise beyond capability
  IDs). **Every edit lands in both `.agents/skills/` and `.claude/skills/`** — they are separate
  files kept byte-identical by convention, enforced by `check_skill_sync.py` in the `doc` gate.
- **Ship `scripts/check_roadmap_placement.py`**, wired into the `doc` gate beside `skill_sync` and
  `skill_references`: assert no line in `master_story_roadmap.md` introduces a design-doc
  sub-feature. It must distinguish `INT-US-NN-SFxx` (legal) from a bare `SF-NN` (illegal) — that
  distinction is the whole rule, so it is also the whole test.
- **Repair all four pre-existing offenders** — `TECH-001`, `TECH-005`, `TECH-006`, `TECH-009`
  (11 lines). Each one's SF detail already exists in its own design's Sub-Feature Breakdown and
  Progress Tracker, so the roadmap lines are duplicates, not the only record — nothing is lost by
  deleting them. Verify that per ticket before deleting, not as an assumption.
- **Note the finished-stories tension.** All four are delivered (🟢). Editing their roadmap entries
  is normally forbidden. This ticket is the sanctioned route, exactly as `TECH-025` is for the test
  files it renames — and the edit removes duplicated status detail rather than changing any claim
  about what was delivered. Say so in the commit.

## Non-Goals (proposed, pending design)

- ~~**Not** a re-litigation of why `TECH-NNN` entries get a full `###` section with Benefit /
  Verifiable Proof / Sequencing where a capability gets one line.~~ **Struck 2026-08-08 — the
  premise was false.** See "Measured hierarchy" below. Left visible rather than deleted because the
  false belief is itself evidence of how easy this file is to misread.
- **Not** a general skill rewrite. Only the sentences that state or contradict this contract.
- **Not** `TECH-025`'s own roadmap entry beyond reverting the sub-features added on 2026-08-08 and
  the title drift noted below.

## Measured hierarchy (2026-08-08) — carry this into the design phase

Recorded because the minting session got it wrong twice, in opposite directions, and the design
phase should not have to re-derive it.

**`TECH-NNN` and `US-N` are peers.** Both are top-level `###` sections. A capability
(`B-INTL-09`, `C-FLOW-02`) is *not* a peer of either — it is a **child**, listed as one line
inside a `US-N` entry's Core Required or Add-Ons list. Three levels, not two:

```
### US-N / ### TECH-NNN        top-level section
    Core Required (MVS)         -> capability IDs, INT-US-NN base contract   (one line each)
    Sub-Story Add-Ons           -> INT-US-NN-SFxx + the capabilities it needs (one line each)
```

Volume, measured across the whole file:

| Family | Sections | Median size |
|---|---|---|
| `US-N` | 28 | 15 lines / 1068 chars |
| `TECH-NNN` | 24 | **4 lines / 431 chars** |

So TECH sections are **leaner** than US sections, not bloated. The earlier claim that "TECH tickets
get a full section where a capability gets one line" compared a top-level section to a child line —
two different levels — and concluded a deviation that does not exist.

**Why this matters to the checker.** The rule is not "TECH entries must be short". It is *a line
exists only for something with its own registry ID*. A section may legitimately carry Benefit,
Verifiable Proof and Sequencing prose; what it may not carry is a line for something that has no ID.
A checker written against size or prose volume would enforce the wrong invariant and flag the 28
clean `US-N` entries — which are the largest sections in the file.

## Second placement contract: design vs implementation plan

The roadmap split is one instance of a wider rule this ticket should write down while it is at it:
**each document holds one altitude, and the detail is written once, into the file that owns it.**

Measured across every multi-sub-feature story (2026-08-08):

| | Size | Holds |
|---|---|---|
| `<ID>_design.md` — feature-wide | 200–430 lines | overview, research (`### Codebase Patterns` runs 34–60 lines and **belongs**), FRs / NFRs / ADs, boundary and reuse analysis, execution order, Progress Tracker, Session Handoff |
| `### SF-NN` inside the design | **8–10 lines** | scope · FRs · inputs · outputs · depends_on · plan path. **Nothing else.** B-FLOW-01: 10/10/10. D-INTL-06: 9/9/8 |
| `<ID>_sfNN_implementation_plan.md` | **400–650 lines** | every per-SF detail — file inventories, test plans, commit boundaries, research notes |

**A plan file exists only once its SF is started.** `INT-US-04` has 9 sub-features and 1 plan;
`B-SENS-02` has 4 and 2. That is correct, not incomplete: the detailed planning is written when the
SF begins, directly into its own file, never up front and never into the design.

**Why the design drifts anyway.** Decomposition happens *before* any plan file exists, so whoever
writes the Sub-Feature Breakdown has nowhere to put detail they have already worked out — and puts
it in the design. When the plan is later written, the detail is written again. Observed on
`TECH-025` SF-02: a 12-row rename inventory lived in both, and **three of the nine names had already
diverged** between them within a day. The design said `test_drafter_e2e.py`; the plan said
`test_drafter_loop_e2e.py`.

**Doing this retrospectively is harder than doing it in order** — untangling which of two copies is
current requires reading both and judging, where writing it once requires only discipline. That
asymmetry is the argument for a checker rather than a convention.

> [!IMPORTANT]
> **Same navigational hint as above: measure this from NON-TECH stories.** `B-FLOW-01`,
> `D-INTL-06`, `B-INTL-09` and `INT-US-21` are the reference shapes. Sampling only Topic 07 gives
> the wrong ratio — `TECH-025`'s plans average 258 lines against a 400–650 norm, precisely because
> its design absorbed detail the plans should own.

## Known adjacent defects (found while minting, not this ticket's scope)

- `.tmp/pre/` holds a stale copy of the `tests/` tree and pollutes every repo-wide grep — including
  the collision check `specweaver-ticket` Phase 2 mandates. It produced phantom `TECH-042` /
  `TECH-999` hits during this ticket's own minting.
- `TECH-025`'s roadmap title ("Pre-Existing FR Traceability Gap") has drifted from its design-doc
  title ("Registry IDs Leaking Into Proofs"). That is `TECH-025`'s to fix.

## Spun off from this ticket

- **`TECH-027`** — [Sub-Feature Identifier Contract](../TECH-027/TECH-027_design.md), minted
  2026-08-11. This ticket measured *where* an `SF-NN` may appear in the roadmap but never asked what
  an `SF-NN` **is**, so two defects it walked past stayed open: the identifier is spelled both
  `SF-01` and `SF-1` (16 unpadded filenames against 166 padded), and a bare `SF-NN` outside
  `features/<topic>/<STORY-ID>/` names nothing — including twice in `master_story_roadmap.md`, where
  another story's sub-features are attributed to `TECH-025` because it is the only ID in the
  sentence. Split out rather than folded in: this ticket repairs 11 lines in one file, `TECH-027`
  reaches 40 documents across 5 delivered stories and needs its own waiver.
- The two contracts are **complementary, not overlapping** — a nested line written
  `✅ TECH-001 SF-01:` satisfies `TECH-027`'s qualification rule and still violates this ticket's
  placement rule. Both fall out of one scan of `master_story_roadmap.md`, so they should share a
  checker rather than each walking the file.

## Next Step

> [!IMPORTANT]
> **Start here: derive the convention from NON-TECH entries.** Read `B-INTL-09` and `C-FLOW-02`
> first. `B-INTL-09` has four sub-features in its design and **one line** in the roadmap — it is
> structurally identical to a multi-sub-feature TECH ticket and shows the correct treatment.
> **Never take precedent from the `TECH-NNN` family**: the convention is broken there in 4 of 24
> entries, and those are exactly what a search inside Topic 07 surfaces first.
>
> This hint came from the user (2026-08-08) **after the agent had already got it wrong twice** —
> once by adding seven sub-features to the roadmap on TECH-001/TECH-006's precedent, and again by
> reporting the pattern as "TECH tickets are the deviation for having sections at all", which is
> false (see *Measured hierarchy*). Both failures came from sampling only the TECH family. Reading
> four non-TECH entries settled it in minutes. Do that first and the rest of this document reads
> as confirmation rather than discovery.

Then run through `specweaver-design`. The contract text is short and largely settled; the design
work is in the checker's rule — precisely which line shapes are legal, given that
`INT-US-NN-SFxx` is legal and a bare `SF-NN` is not — and in confirming that deleting the 11
pre-existing nested lines across `TECH-001`, `TECH-005`, `TECH-006` and `TECH-009` loses nothing,
because each ticket's own design already carries that detail in its Sub-Feature Breakdown and
Progress Tracker. Verify that per ticket rather than assuming it.
