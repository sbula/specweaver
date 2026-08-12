# Design: Sub-Feature Identifier Contract — Two Digits and an Explicit Owner

- **Feature ID**: TECH-027
- **Epic**: Topic 07 (Technical Debt)
- **Status**: CLAUSE 1 DELIVERED (2026-08-12) — clause 2 open, see §Delivery
- **Origin**: Raised by the user 2026-08-11 while reviewing `TECH-026`'s design. `TECH-026` had
  measured where `SF-NN` may appear in the roadmap but never asked what an `SF-NN` *is* — so a
  reader still cannot tell which story a given `SF-01` belongs to, and the repo spells the same
  identifier two ways. Split out of `TECH-026` rather than folded in, because the two tickets have
  different blast radii: `TECH-026` repairs 11 lines in one file, this one reaches 40 documents
  across 5 delivered stories.

## Problem Statement

`SF-NN` is used project-wide as a sub-feature identifier and has never been given a contract. Two
distinct defects follow, and they compound: the second one is worse when the first is present.

### Rule 1 — the identifier is spelled two ways

`SF-{2d}` (zero-padded, two digits) is already the overwhelming norm. The outliers are a minority
that predate any statement of the rule.

| Where | Padded | Unpadded | Stories affected |
|---|---|---|---|
| Document filenames (`_sfNN_`) | 166 | **16** | `TECH-005` (5), `TECH-002` (4), `C-EXEC-02` (3), `E-EXEC-01` (2), `TECH-007` (2) |
| Prose references (`SF-N`) | — | **40 files** | reaches beyond `roadmap/` into `dev_guides/` and `architecture/` |

Writing the rule down therefore ratifies existing practice rather than imposing a new one. That
matters for the cost estimate: this is not a repo-wide convention change, it is 16 filenames and a
prose sweep.

### Rule 2 — a bare `SF-NN` names nothing outside its own folder

`SF-01` exists in `TECH-001`, `TECH-005`, `TECH-006`, `TECH-009`, `TECH-025`, `B-FLOW-01` and
others. Inside `features/<topic>/<STORY-ID>/` the folder supplies the owner and a bare `SF-01` is
unambiguous. Anywhere else it is a dangling reference that reads as resolved.

**Two live instances, both in `master_story_roadmap.md`, both actively misleading:**

```
684:  *  **Known separate gap:** `TECH-025` tracks a pre-existing FR-traceability
         citation gap in SF-01/02/03 (found by SF-04's own closure gate) ...
```

That line sits inside **TECH-001's** section and the sub-features meant are TECH-001's — but the
only story ID in the sentence is `TECH-025`. A reader binds `SF-01/02/03` to the nearest named
story and gets the claim exactly backwards: TECH-025's own SF-01/02/03 are Gate Integrity, Test
Naming Closure and the Class Naming Ratchet, none of which concern a citation gap.

```
716:  *  **Known separate gap:** `TECH-025` tracks a pre-existing FR-traceability
         citation gap in SF-01/2 (found by SF-03's own closure gate) ...
```

Same sentence shape inside **TECH-005's** section, and unpadded on top — the two rules failing
together in one line, which is why they are one ticket.

Both were written by the closing commits of the stories they sit in (`11abf7d7`, `548b7aaf`, later
widened by `25b3d37c`), so correcting them is an edit to delivered stories' roadmap entries and
needs this ticket's explicit waiver.

### The convention already exists — for `FR-N`, by hand, enforced nowhere

`TECH-025` hit the identical ambiguity in requirement numbers and solved it locally:

> **Reading convention used throughout this document.** A bare `FR-N` always means *this ticket's*
> requirement. A requirement belonging to one of the three subject stories is always written
> qualified — `TECH-001 FR-7`. The two are otherwise indistinguishable and the whole ticket is
> about FR numbering, so the qualification is not optional.
> — `TECH-025_design.md:8`

That paragraph is hand-copied into three further documents (`TECH-025_sf04_implementation_plan.md:10`,
`TECH-025_sf04_task.md:7`, `TECH-025_sf05_implementation_plan.md:10`). So the rule was invented ad
hoc the moment someone tripped over it, duplicated four times, scoped to one ticket, and enforced by
nothing — and **the identical ambiguity in `SF-NN` was never noticed.** Generalising that note into
a checked contract is most of this ticket.

This is the same defect class as `TECH-019` and `TECH-026`: a convention that exists only in
whoever-happens-to-notice, executed as truth. Same fix shape — repair the instances, then ship the
guard.

## Candidate Approaches (not yet designed)

- **State both clauses once**, in the shared reference `TECH-026` establishes, rather than opening a
  second home. If `TECH-026` lands first this ticket adds a section; if this lands first it creates
  the file. Either way there is one contract document, not two.
  - *Clause 1 — format.* `SF-` followed by exactly two zero-padded digits (`SF-01`, never `SF-1`).
    Document filenames use `_sfNN_` to match. Project-wide, no exceptions.
  - *Clause 2 — qualification.* A bare `SF-NN` is legal only inside a document under
    `features/<topic>/<STORY-ID>/`, where the path supplies the owner. Everywhere else — the master
    roadmap, topic docs, another story's folder, dev guides, commit messages — it is written
    `<STORY-ID> SF-NN`.
- **Retire the four hand-copied `FR-N` notes** by folding them into the same contract, so the
  qualification rule covers both identifier families and is stated once. Verify per document that
  nothing else in the note is load-bearing before deleting.
- **Ship `scripts/check_sf_identifiers.py`** in the `doc` gate. Clause 2 is decidable from the file
  path alone, which is what makes it enforceable rather than aspirational: for any `.md` under
  `features/<topic>/<ID>/`, bare `SF-NN` is legal; anywhere else it must be preceded by a story ID.
  Clause 1 is a pure regex over both prose and filenames.
- **Rename the 16 unpadded files and sweep the 40 prose files.** Every rename breaks inbound links,
  so the sweep and the rename are one commit per story, never bundled.
- **Decide the interaction with `TECH-026`'s checker.** The two rules are complementary, not
  overlapping — a nested roadmap line written `✅ TECH-001 SF-01:` satisfies qualification and still
  violates `TECH-026`'s placement rule. But both fall out of one scan of `master_story_roadmap.md`,
  so they should share a checker rather than each walking the file.

  > **Note (2026-08-11) — `TECH-026`'s checker rule was corrected, and it changes what this ticket
  > inherits.** `TECH-026`'s design had stated its rule two ways: the principle *"a line exists only
  > for something with its own registry ID"*, and, in its Candidate Approaches bullet, a lexical
  > *"distinguish `INT-US-NN-SFxx` from a bare `SF-NN` — that distinction is the whole rule"*. The
  > second was wrong and has been struck: it flags 15 legal prose mentions of `SF-NN` and ignores
  > the ~89 capability lines at the same nesting level. The surviving, validated form is
  > **structural** — a third-level list item must name a bold registry ID, which separates 168 legal
  > lines from exactly the 11 violations.
  >
  > **Why that matters here.** A lexical rule would have collided head-on with this ticket: clause 2
  > makes a *qualified* `TECH-001 SF-04` legal in prose everywhere, so a checker that treats any
  > `SF-NN` token as suspect cannot express both contracts at once. The structural rule leaves the
  > prose plane entirely to `TECH-027`, and the list-item plane entirely to `TECH-026`. That clean
  > split is what makes one shared scan feasible — design the checker to walk the file once and
  > apply a list-item rule and a prose rule to different line classes, not to run two token scans.

## Non-Goals (proposed, pending design)

- **Not** `INT-US-NN-SFxx` sub-story IDs. Those are minted registry IDs that already carry their
  owner in the identifier; they are out of scope for both clauses and must be explicitly excluded
  from the checker, exactly as in `TECH-026`.
- **Not** a renumbering of any sub-feature. `SF-1` becomes `SF-01`; it never becomes `SF-02`.
- **Not** `TECH-026`'s roadmap placement rule, and not the design-vs-plan altitude contract parked
  in `TECH-026`'s design §"Second placement contract".
- **Not** a general sweep of every identifier family in the repo. `FR-N` is in scope only because
  the existing hand-written notes are the precedent being generalised; `AD-N`, `NFR-N`, `CB-N` and
  `T-N` are left alone until someone measures a defect in them.

## Sequencing constraints

- ~~**Collision with `TECH-025` SF-05, which is drafted and not yet started.** Its plan already
  noticed this defect and worked around it: *"Note the plan filenames are `TECH-002_sf1_…`, not
  `sf01`. The gate's glob matches either; a citation added to the wrong guess simply would not be
  found."* Normalise `TECH-002`'s four filenames and that note goes stale; leave them and SF-05
  ships citations against names this ticket forbids. **Decide the order before SF-05 starts**, not
  after.~~
- ~~`TECH-005`'s five unpadded files are the same problem one ticket later, for `TECH-025` SF-06.~~
- **Resolved 2026-08-11 — the user chose rename-first, and clause 1's filename half is delivered.**
  All 16 files renamed to `_sfNN_` and every inbound reference updated across 21 documents. SF-05's
  workaround note is struck in its plan; SF-06 will not meet the problem at all. See §Delivery below.
- All five offending stories (`TECH-002`, `TECH-005`, `TECH-007`, `C-EXEC-02`, `E-EXEC-01`) are
  delivered. Repairing them requires a waiver of finished-stories-immutable named in every commit,
  as `TECH-025` AD-4 does for the test renames — **invoked for the rename commit.**

## Delivery (partial, ahead of design)

> [!WARNING]
> **This ticket shipped work before it had a design or an implementation plan.** The user directed
> the rename on 2026-08-11 to unblock `TECH-025` SF-05, so clause 1's filename half landed out of
> the normal design → plan → dev order. Recorded here rather than hidden, because the rest of the
> ticket must not assume a clean start.

**Delivered:**

- 16 files renamed `_sfN_` → `_sf0N_` via `git mv` (history preserved), across `C-EXEC-02` (3),
  `E-EXEC-01` (2), `TECH-002` (4), `TECH-005` (5), `TECH-007` (2).
- Every inbound reference rewritten — 21 documents, 39 references.
- Verified: zero `_sfN_` filenames remain; the repo's dangling-relative-link count is **66 before
  and 66 after**, none sf-related, so the rename introduced none.

**Explicitly NOT delivered — still this ticket's work:**

- **Clause 1's prose half.** Single-digit `SF-N` still appears in ~40 documents, including inside the
  five renamed stories, so a padded filename can sit beside unpadded prose in the same file. That
  inconsistency is now visible where it was previously uniform, which is the cost of splitting the
  clause; it wants closing soon rather than eventually.
- **Clause 2 entirely.** The two live instances at `master_story_roadmap.md` are untouched.
- **The checker.** Nothing prevents a new `_sfN_` file today.
- **No FRs exist**, so nothing above is cited by a ledger. Whoever runs `specweaver-design` on this
  ticket must write FRs that account for work already done rather than assuming a green field.

## Next Step

Run through `specweaver-design`. The contract text is short and settled; the design work is in three
places:

1. **The checker's path rule** — precisely which directories confer ownership, and how a document
   that legitimately discusses two stories (a walkthrough citing its dependencies) satisfies
   clause 2 without becoming unreadable.
2. **The sequencing decision above**, which is a live blocker on `TECH-025` SF-05 and cannot be
   deferred to this ticket's own implementation.
3. **Whether the `FR-N` notes retire into the contract or stay.** Retiring them is tidier and is the
   reason the precedent is cited here; keeping them is safer if any of the four says something the
   general rule does not.

> [!IMPORTANT]
> Take the format precedent from the **166 padded filenames**, not from the 16 unpadded ones, and
> take the qualification precedent from `TECH-025`'s `FR-N` note. Both majorities are already right;
> this ticket is writing down what the repo mostly already does, then enforcing it. Sampling the
> offenders first is the failure `TECH-026`'s design documents at length.

---

## Delivery — clause 1 complete, clause 2 open (2026-08-12)

### Scope decision

**Option B, entry-scoped** (user). A bare `SF-NN` is acceptable where the enclosing entry names its
story; only genuinely orphaned references must qualify. Chosen over the per-occurrence reading
because that would have flagged 28 references in `topic_07` alone — inside entries whose own bullet
opens with the story id, which is the structure `TECH-026` had just established as *correct*.

### Clause 1 — delivered

**418 single-digit references padded across 43 documents**, on top of the 16 filenames renamed
earlier. Verified: the repo's dangling-relative-link count is **66 before and 66 after**, and all
five FR ledgers still exit 0 after a sweep that touched five delivered stories' designs.

Two exclusions, both earned rather than assumed:

- **Legacy numbering.** `Feature 3.32 SF-4` and `3.14a … (SF-1)` belong to a pre-registry scheme
  where a sub-feature hung off a decimal feature number, not a story id. Padding them would invent
  identifiers for something that no longer exists. A first attempt excluded these by *line*, using
  any decimal as the marker — which wrongly caught `**5.0 Pre-check**: All 4 FRs assigned to SF-2` (a real reference needing `SF-02`),
  where `5.0` is a section number and the reference is a real one. The marker is now the literal
  word `Feature`.
- **Demonstration lines.** A document stating the rule must quote the form it forbids. The sweep
  turned *"(`SF-01`, never `SF-1`)"* into *"(`SF-01`, never `SF-01`)"* in this very file, and the
  same in `TECH-026`'s. Both restored, and the guard now exempts a line showing the padded form
  beside the single-digit one — the same carve-out `check_conventions` R5 makes for citation tags,
  for the same reason: a rule that cannot be written down cannot be enforced.

The guard is `tests/unit/test_sub_feature_identifiers.py`: prose, filenames, a test that the legacy
exclusion is still exercised rather than dead, and one pinning that the demonstration exemption is
narrow.

### Clause 2 — deliberately not shipped

**Detecting it lexically was attempted and abandoned, and that is the finding.** Four successive
measurements each reported a different number, and each refinement showed the previous one had been
counting correct references as violations:

| Attempt | Reported | What was wrong |
|---|---|---|
| 1 | 122 | Missed the backtick form — `` `TECH-025` SF-05 `` counted as unqualified |
| 2 | 113 | One population, actually three |
| 3 | 79 / 19 / 15 | Split by category; the 79 are legal under option B |
| 4 | 19 | Inspected individually — most name their story on the same line, just not adjacently (`` `TECH-001` corrected to 🟡 — SF-04 outstanding ``) |

A rule whose violations cannot be counted without judgement cannot be enforced by a regex, and
asserting it badly is worse than not asserting it — a checker that cries wolf gets disabled, and
then the rule it protects is gone too. `TECH-026` reached the same conclusion from the other
direction and solved it by going **structural** rather than lexical.

**What clause 2 needs before it can ship:** a definition of "enclosing entry" precise enough to
compute — almost certainly markdown structure (the nearest heading or list item), not a line window.
That is the same walker `TECH-026`'s checker needs, which is the argument for building them together
rather than guessing one now.
