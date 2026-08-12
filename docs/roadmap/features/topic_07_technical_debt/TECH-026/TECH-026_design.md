# Design: Roadmap Placement Contract — One Registry ID, One Line

- **Feature ID**: TECH-026
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DELIVERED (2026-08-12)
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

**Measured violations — historical snapshot (2026-08-08) and today's repair list (re-measured
2026-08-11):**

| Entry | 2026-08-08 | 2026-08-11 | |
|---|---|---|---|
| `TECH-001` | 4 | **4** | lines 676–679 |
| `TECH-005` | 3 | **3** | lines 707–709 |
| `TECH-006` | 2 | **2** | lines 721–722 |
| `TECH-009` | 2 | **2** | lines 741–742 |
| `TECH-025` | 7 | **0** | added by the session that found this, and reverted there |
| **Total** | **18** | **11** | |

> **The repair list is 11 lines across 4 entries, not 18 across 5.** The 18 was true when measured;
> `TECH-025`'s seven were its own and are gone. Both numbers are kept because the design phase reads
> this table as a work inventory, and hunting for seven lines that no longer exist ends either in
> "the doc is wrong" or — worse — "someone already did part of this", and stopping short.

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
  sub-feature. **Implement the rule stated in §"Why this matters to the checker" below — a line
  exists only for something with its own registry ID** — not a lexical `INT-US-NN-SFxx`-vs-`SF-NN`
  discrimination.

  > **Corrected 2026-08-11.** This bullet previously read *"It must distinguish `INT-US-NN-SFxx`
  > (legal) from a bare `SF-NN` (illegal) — that distinction is the whole rule, so it is also the
  > whole test."* That contradicts §"Why this matters to the checker" and fails in two directions.
  > It flags legal prose: `SF-NN` appears in 15 ordinary sentences across Sequencing lines, the Debt
  > Sequencing table and the "Known separate gap" notes — including `TECH-025`'s own entry, which
  > would be flagged by the ticket it spun off. And it under-specifies the legal set: ~89 capability
  > lines (`C-EXEC-01`, `B-VAL-02`, …) sit at the same nesting level and a whitelist naming only
  > `INT-US-NN-SFxx` says nothing about them. Left visible rather than deleted, per this document's
  > house style, because the wrong version is the one an implementer reads first.

  **The implementable form, validated against the file 2026-08-11:** a list item at the third
  nesting level (8-space indent) must name a **bold registry ID**.

  ```
  168 items match the bold-ID shape  ->  all legal   (INT-US-NN-SFxx + capability IDs)
   11 items do not                   ->  exactly the 11 violations, no others
  ```

  Perfect separation, no allowlist, no tuning. It works because it is *structural* rather than
  lexical: prose sentences are not list items at that depth, so they never enter the check.
  `TECH-027` carries a sibling rule over the same file and the two should share one scan — see
  §"Spun off from this ticket".
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

## Hierarchy — CORRECTED BY THE USER (2026-08-12). Read this before the section below.

> [!CAUTION]
> **"TECH-XXX are NOT user stories. These are comparable to features like `E-INTL-02`,
> `C-FLOW-01`, …"** — user, 2026-08-12.
>
> **This supersedes the "Measured hierarchy" section below**, which concluded that `TECH-NNN` and
> `US-N` are peers. They are not. A `TECH-NNN` sits at **capability level**, alongside
> `E-INTL-02` / `C-FLOW-01` / `B-INTL-09` — the things that appear as **one line** inside a `US-N`
> entry's Core Required list.

**Why the measurement got it wrong.** The section below is not factually incorrect — `TECH-NNN`
entries *are* top-level `###` sections in the file today, and the line counts are real. It inferred
the hierarchy from that formatting, and the formatting is the defect. Measuring what the file does
cannot tell you what the file should do when the file is what is broken. That is the same trap this
ticket documents twice already, arriving a third time.

**What this changes.** The repair is materially larger than §Problem Statement says:

| | Under the old reading | Under the correction |
|---|---|---|
| Defect | 11 nested `SF-NN` lines inside 4 entries | **24 `TECH-NNN` entries formatted as stories** |
| Fix | Delete 11 lines | Convert each to capability-level, then decide where they live |
| Vocabulary | Kept | `Benefit:` / `Core Required (MVS)` / `Verifiable Proof:` are **user-story fields**; a capability line carries none of them |

**Open for the design phase — do not guess this.** A capability line lives *inside* a `US-N`
section's Core Required or Add-Ons list, and a `TECH-NNN` belongs to no user story. So converting
them raises a question the file cannot answer today: **where does a capability-level entry live when
it has no parent story?** Candidates: a single Technical Debt section holding one line per ticket;
or the master roadmap referencing `topic_07` only, since that document already carries the full
prose for all 24. The second matches this ticket's own thesis — one home per fact — and would make
the master roadmap's TECH region a list of links.

**Converted 2026-08-12 — all 29, not just the new five.** Every `TECH-NNN` now sits as a
capability-level line under one `### 🔧 Technical Debt (TECH)` grouping: ID, short name, link,
status box, no story fields. `master_story_roadmap.md` went from 839 lines to 704.

**Two of this ticket's measured defects closed as a side effect:**

| Defect | Before | After |
|---|---|---|
| Nested `SF-NN` lines (§Problem Statement's repair list) | 11 across `TECH-001`/`005`/`006`/`009` | **0** |
| Lines over 200 chars in the TECH region (§Third rule) | 12 | **0** |

The 11 nested lines lived inside the `Core Required (MVS)` blocks of four TECH sections; removing
the story scaffolding removed them with it. That is the stronger argument for the capability-line
reading than anything measured earlier — the placement defect and the sub-feature-leak defect turn
out to be **the same defect**, which is why deleting 11 lines was never going to be the whole fix.

**What remains for this ticket** is therefore not the roadmap file. It is writing the contract down
once, pointing the callers at it, and shipping the checker — so the shape cannot regrow.

**The tooling was enforcing the wrong shape, which is why this kept regrowing.**
`check_story_preconditions.py::_story_block` looked only for a `^### .*<ID>:` heading, so writing a
TECH entry *correctly* made it report "no roadmap section found" and fail the ticket — all five went
red the moment they were converted. An agent that followed the rule got a red gate; an agent that
broke it got green. That is the same instructions-versus-reality class as `TECH-019`, arriving
through a checker rather than through prose, and it is why "precedent in the artifact beat the rule"
kept happening. `_story_block` now falls back to the capability line when no `###` section exists,
so the correct shape is writable at all.

**Consequence for the design phase, recorded rather than papered over**: `Verifiable Proof:` has
nowhere to live on a one-line entry, so all five now warn about it. That is not a regression to
suppress — it is the question this ticket must answer. Either proof citations move to the topic doc,
or they belong to the design's FR ledger and the roadmap field was duplicating `check_fr_coverage`
all along.

## Measured hierarchy (2026-08-08) — SUPERSEDED, see the correction above

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

## Third rule (DRAFT, 2026-08-11) — every line in an entry is bounded

> [!WARNING]
> **Draft, not designed.** Written after this ticket's own roadmap entries violated it. It appears to
> contradict §"Why this matters to the checker" above, which rejects a size-based checker. The
> measurement below resolves that — but read both before writing any FR.

### Origin

The session that registered `TECH-026`, `TECH-027` and `TECH-028` (2026-08-11) gave each entry a
`**Sequencing:**` field that ran to a full paragraph — measurements, dry-run output, `file:line`
references and out-of-scope lists. Every one of those facts already existed in the topic doc and in
the ticket's own design. Reverted in `134f8de6`.

Two things make this a rule rather than a correction:

1. **The one-ID-one-line rule did not catch it.** No nested `SF-NN` line was added and the
   third-level line count was unchanged; the entry *bodies* grew instead. The contract as written
   constrains how many lines an entry has, not how much each line carries.
2. **The verification reported clean.** That session checked the third-level line count and declared
   the entry compliant. Wrong measurement for this defect — the same failure this document already
   warns about, arriving from the other direction.

### The apparent contradiction, and why it dissolves

§"Why this matters to the checker" says a checker written against size "would enforce the wrong
invariant and flag the 28 clean `US-N` entries — which are the largest sections in the file." That is
correct about section **size**. It says nothing about field **values**, and the two turn out to be
unrelated.

**Measured 2026-08-11, one method, whole file** — the distribution nobody had taken:

| Field | n | Median | p90 | Max |
|---|---|---|---|---|
| `Benefit:` | 49 | **127** | 219 | 296 (`TECH-002`) |
| `Sequencing:` | 11 | **128** | 183 | **708** (`TECH-025`) |
| `Known separate gap:` | 3 | 173 | 179 | 179 |

**The `US-N` family is not an outlier on field values.** The longest `Benefit` in the file belongs to
a TECH entry (296); the longest `US-N` one is `US-27` at 235, inside the general spread. `US-N`
sections are long because they carry *many legitimate ID lines*, which this rule does not touch. So a
field-value bound does **not** flag the 28 clean entries, and the objection above does not apply to
it.

`Sequencing:` is bimodal: ten entries between 94 and 211, and `TECH-025` at 708 — 5.5× the median and
3.9× p90. One pre-existing violation, not from the session that prompted this.

```
TECH-017   94  ############
TECH-026  101  #############
TECH-020  128  ################
TECH-027  161  ####################
TECH-028  164  #####################
TECH-023  183  #######################
TECH-024  211  ##########################
TECH-025  708  ####################################################################...
```

### Proposed rule

**A field's value is a clause, not a paragraph.** In a `### <ID>` section, the value of `Benefit:`,
`Sequencing:` or any similar inline field is bounded. Detail belongs in the topic doc, which owns it.

Deliberately **not** bounded:

- The number of `Core Required` / `Sub-Story Add-Ons` lines — that is what makes `US-N` entries long
  and it is correct, each line being a registry ID earning its place.
- `Verifiable Proof:`, which is a header whose value is the test paths on the lines beneath it. It
  measures 0 chars inline in all five occurrences; a naive character check must not treat it as a
  field or it will read as trivially compliant while meaning nothing.

### Open — pick one at design time

| Form | Mechanism | Trade |
|---|---|---|
| **A — absolute cap** | ~300 chars per field value: above p90 for both fields, below every current value except `TECH-025`'s | Simplest to check, and the measurement now supports a defensible number. Makes exactly one pre-existing entry non-compliant |
| **B — ratchet** | Freeze today's per-field p90; a new or edited entry may not exceed it | Precedent: `TECH-025` SF-03's R6 ratchets unit test class names against a frozen per-directory baseline (278 across 10 dirs). Ships without touching `TECH-025` |
| **C — structural** | A field value may contain no `file:line` reference, no measurement and no out-of-scope list, regardless of length | Targets what actually went wrong instead of proxying it by size. Hardest to express as a check |

**Leaning A**, which the measurement did not originally support and now does: a single violation is a
repair, not a sweep, and `TECH-025`'s 708-char entry is independently worth cutting. **C is the more
honest rule** — length is a proxy for the real defect, and this document elsewhere criticises proxy
invariants — so if C can be expressed cheaply it should win. A and C are not exclusive.

### Scope correction (user, 2026-08-11) — the rule is general, and it is about line length

> [!IMPORTANT]
> **"I am not talking about TECH stories alone. This is a general rule for all stories / sub-stories
> / features / tech debts / … mentioned in `master_story_roadmap`. They must be short — this is an
> overview only."**
>
> The framing above ("a field's value is bounded") is a **subset** of the rule, derived from the two
> fields that happened to break. The rule the user states is simpler and wider: **every line of every
> entry, in every family, is bounded.** Design against this, not against `Benefit:`/`Sequencing:`.

The field-value measurement above looked at three named fields. This is the same file measured
without that filter — **every non-empty line inside a `### ` section**, by family:

| Family | Lines | Median | p90 | Max | >200 ch | >400 ch |
|---|---|---|---|---|---|---|
| `TECH-NNN` | 146 | 96 | 186 | **728** | 12 | 1 |
| `US-N` | 507 | 58 | 138 | 248 | 11 | 0 |
| capability / other `###` | 110 | 93 | 196 | 335 | 10 | 0 |
| **whole file** | **763** | — | — | 728 | **33** | **1** |

**This corrects the section above in one important way.** "The `US-N` family is not an outlier" is
true, but it was read as *`US-N` is clean*. It is not: **11 `US-N` lines and 10 capability lines
exceed 200 characters.** Measured on the three named fields the repair list is one entry; measured as
the user states the rule it is **33 lines spread across all three families**. A design written against
the narrow framing would ship a checker that passes 32 of the 33 lines the user is pointing at.

The medians say the convention is already short — 58 to 96 characters, roughly one clause — so as
with `TECH-027`'s padding rule, this **ratifies existing practice** and the long lines are outliers
rather than the norm.

**What stays unbounded** is unchanged and still important: the *number* of `Core Required` /
`Sub-Story Add-Ons` lines. `US-N` sections are long because they list many registry IDs, one per
line, and each earns its place. Bounding line length does not touch that — which is precisely why a
line-length rule can be general where a section-size rule could not, and why §"Why this matters to
the checker" still stands.

A cap in the **200–250** range sits above every median and p90 in the table and below all 33
outliers. That number is for the design phase to set; the measurement is here so it does not have to
be re-derived.

### Interaction with the checker

If `scripts/check_roadmap_placement.py` takes this on it walks the file once and applies three
line-class rules, not three scans: the list-item rule from this ticket, the prose qualification rule
from `TECH-027`, and this length rule. A fourth pass would be the wrong shape.

## Known adjacent defects (found while minting, not this ticket's scope)

**Both entries below are closed. Struck 2026-08-11 rather than deleted, per this document's house
style — a stub that lists resolved defects as open costs the design phase a round of
re-verification, which is the cost this section exists to avoid.**

- ~~`.tmp/pre/` holds a stale copy of the `tests/` tree and pollutes every repo-wide grep — including
  the collision check `specweaver-ticket` Phase 2 mandates. It produced phantom `TECH-042` /
  `TECH-999` hits during this ticket's own minting.~~ **Resolved.** The directory is gone;
  repo-wide greps are clean and the Phase 2 collision check runs uncorrupted. Confirmed while
  minting `TECH-027` and `TECH-028`, both of which used that check. The only remaining
  `TECH-042`/`TECH-999` hits are the deliberate fixtures in
  `tests/unit/scripts/test_check_story_preconditions.py`.
- ~~`TECH-025`'s roadmap title ("Pre-Existing FR Traceability Gap") has drifted from its design-doc
  title ("Registry IDs Leaking Into Proofs"). That is `TECH-025`'s to fix.~~ **Resolved.** All three
  registries now read "Registry IDs Leaking Into Proofs — FR Traceability Gap and Story-Named
  Tests", byte-identical.

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

---

## Delivery (2026-08-12)

### The contract exists now, which was the whole point

`.claude/skills/specweaver-ticket/references/roadmap-placement.md` states the three-document split
and the three rules once. The three callers point at it — `phase-6-documentation.md` (with the
"Add-Ons" ambiguity disambiguated in place), `phase-5-document.md`, `specweaver-ticket/SKILL.md` —
in both `.agents/` and `.claude/`, byte-identical per `check_skill_sync`.

### `scripts/check_roadmap_placement.py`, in the `doc` gate

One walk, three rules by line class — the shared walker `TECH-027` clause 2 was blocked on:

| | |
|---|---|
| **R-PLACE** | a nested list item must name a bold registry ID |
| **R-LENGTH** | a line inside an entry is ≤ 200 chars |
| **R-OWNER** | a bare `SF-NN` must have its owner named |

Probed rather than assumed: a planted `SF-01:` line is caught with the message naming why.

**R-OWNER is line-scoped, and that was a correction made against the real file.** Requiring the id
*adjacent* to each reference reported correct references as violations — `**INT-US-04-SF05:** …
[SF-05: Advanced Routing]` names its owner in the bold key, and a clause-scoped rule flagged it
anyway. Four earlier measurements in `TECH-027` failed the same way. A checker that cries wolf gets
disabled and takes its rule with it.

### 11 over-length lines repaired

Seven sub-story lines carried `Sub-Story Integration defined in [SF-NN: <full section title>]`,
where the id is already the bold key; four `Benefit` lines were simply overlong prose.

### The template was teaching the defect

`specweaver-design`'s Sub-Feature Breakdown template used `### SF-1:` and `[ID]_sf1_…`. Every design
written from it inherited the single-digit form that `TECH-027` then swept. Corrected, and the
clause-1 guard now scans the skill trees as well as `docs/` — it could not see the template that was
propagating the error.

### An extraction the size limit forced, and what it uncovered

`quality.py` sat at 595/600 against the RED threshold, and a fifth check needs ~8 lines. The
project's rule is that headroom comes from structure, not denser prose, so the argv builders and the
venv resolution moved to `_quality_runners.py` and `_venv.py`. **`venv_python` turned out to be
duplicated verbatim in `scripts/tests.py`** — two places to keep in step for a thing with one
correct answer. `quality.py` is now 541.

A first attempt at this broke 43 tests by importing the sibling directly: `scripts/` is not a
package, so a plain import resolves only when the file is run as a script, never when a test loads
it by path. The repo already had `_load_sibling` for exactly this, in two other scripts.

### Two guards fired, correctly

`test_quality_runner.py` pins the doc gate's exact check set, so adding one failed it until updated
— that is the guard doing its job. And a `# noqa` added in passing tripped the suppressions ratchet,
which is the point of having one; the annotation moved into a `TYPE_CHECKING` block instead.

### What remains

**`TECH-027` clause 2 is now unblocked** — R-OWNER is the walker it needed. The remaining question
is whether "enclosing entry" should mean the markdown structure rather than the line, which is a
refinement of a rule that now exists rather than a rule that does not.
