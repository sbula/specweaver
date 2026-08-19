# Where a thing is written down

One home per fact. This is the contract for `docs/roadmap/master_story_roadmap.md` and the documents
around it, enforced by `scripts/check_roadmap_placement.py` and `scripts/_entry_depth.py` in the `doc` gate.

It exists because it did not. Every rule below was already the convention in the file and written
down nowhere, so each agent derived it from whatever it happened to grep — and what it grepped was
Topic 07, where the convention was broken in four of twenty-four entries. Precedent in the artifact
beat the rule, repeatedly, because there was no rule to beat.

## The four layers

One home per fact. Each layer is narrower than the one above; if the same fact belongs in two, it
goes in the lower one and the upper links to it.

| # | Document | Holds | Does not hold |
|---|---|---|---|
| 1 | `master_story_roadmap.md` | One line per registry ID: id, short name, link, status. A story's `Benefit` and `Sequencing` as a clause each | Measurements, `file:line` refs, out-of-scope lists, rationale, a design's sub-features |
| 2 | `topics/topic_NN_*.md` | A **summary**: what the problem is, why it matters, how it is sequenced, current status. Four lines | Evidence tables, approach comparisons, out-of-scope lists, delivery narrative |
| 3 | `features/<topic>/<ID>/<ID>_design.md` | Problem statement, evidence, candidate approaches, non-goals, guardrail — the case for doing it | The log of having done it |
| 4 | `features/<topic>/<ID>/<ID>_*.md` | The build record: implementation plan (before), delivery record / walkthrough (after), review records | — |

**Layer 2 is where this goes wrong.** An earlier version of this contract said the topic entry
holds *"the full prose for each entry — origin, evidence, fix shape, out-of-scope"*. Agents followed
it, and topic entries grew to **5624 characters** — twenty times the median capability entry. If you
are writing evidence or comparing approaches, you are at layer 3 and should be in the design.

### Not a deeper layer: the knowledge tree

`docs/analysis/`, `docs/architecture/06_lessons_and_future/`,
`docs/architecture/07_architectural_decision_records/` and `docs/dev_guides/` are a different
**audience**, not more detail. A lesson in `anti_patterns.md` is not "deeper than the design"; it is
the part that outlives the ticket. Put a generalisable lesson there, not at layer 4.

## The rules

**R-PLACE — a line exists only for something with its own registry ID.**

A `US-N` entry lists capability IDs, one line each. A design document's `SF-01` is internal
decomposition: no registry ID, no independent existence, and it never appears here.

> **`ADR-005` removed a third kind of line.** A `US-N` entry used to list `INT-US-NN-SFxx` sub-story
> IDs beside its capabilities. The family is retired: a (sub)story's spanning tests are among its own
> tests, so its integration state is its own status and needs no separate line. Never add one back.
>
> **"SF" still spells two things, and that is still the trap.** `SF-01` in a design's Sub-Feature
> Breakdown is internal decomposition and never appears here. Getting this backwards is the original
> defect this contract was written for.

**R-DEPTH — no line in any markdown file exceeds 200 characters.**

Every `.md` in the repo, ratcheted per file. Exempt: a line whose length is one unbreakable token
(a long URL), and a markdown table row, which has no legal wrap point. This replaced `R-LENGTH`,
which capped the same 200 characters on roadmap entries alone — a strict subset, so keeping both
meant two rules and one number.

Wrapping is free: markdown renders a wrapped line identically. **Split only at spaces outside
backtick spans and outside `[text](url)` links**, or you will break a code span or a link.

**R-ENTRY — a topic entry is at most 4 lines' worth of content.**

Measured in *effective* lines — content length over the line limit — so **not wrapping is not an
escape**. Ratcheted per entry; a NEW entry gets no free first offence.

The 4 comes from pre-drift practice, not from taste: capability entries across topics 01–06 have a
median of 247 characters, and the oldest TECH cohort (`TECH-001..013`, before the inflation began)
588. A TECH entry is legitimately ~2.4× a capability entry — and not the 10× later cohorts reached.
One number covers both kinds; there is no per-kind allowance.

**When an entry is too long, redistribute — never delete.** Move each fact to the layer that owns
it and check it survives there before cutting. 39 entries were redistributed on 2026-08-13 and
**21 facts** would have been lost to a trim-by-eye.

**R-ONCE — a registry ID gets one line per story entry.**

Everything else the entry has to say — a dependency, a retirement it absorbed, a sequencing
constraint — is a **clause on that line**, never a second line. Two lines for one ID leaves no way
to say which is the entry, and if both are `` `[ ]` `` the group's flag is computed from whichever
the reader happened to find.

This is how it goes wrong: on 2026-08-16 five retirement notes were re-labelled from the retired
`INT-US-NN-SFxx` to the capability that owns the work, beside the capability's own line, which
nobody deleted. **When you rewrite an entry's ID, you are merging it into another entry — delete
the line you duplicated.** Scoped to the story, because a capability legitimately appears under
several: `US-4 Core` is cited by six.

**R-OWNER — a bare `SF-NN` must have its owner named.**

`SF-01` exists in six different stories. A reference outside its own story's folder resolves only if
the story is named on the same line, or the entry it sits in names it.

## What a TECH ticket looks like

A `TECH-NNN` is **capability-level**, alongside `C-FLOW-02` and `E-INTL-02` — not a user story. It
gets one line, no `Benefit` / `Core Required (MVS)` / `Verifiable Proof` fields, which are user-story
vocabulary:

```
### 🔧 Technical Debt (TECH)
    *   `[ ]` **TECH-030:** [An Empty FolderGrant Path Diverges by Platform](features/…)
    *   `✅` **TECH-029:** [Sandbox Process Cap Uses `RLIMIT_NPROC`](features/…)
```

**R-MARKER — a TECH line is `` `[ ]` `` when open and `` `✅` `` when delivered. Never `` `[x]` ``.**

`[x]` is user-story vocabulary, and the instruction below to "check off the boxes" is about user
stories and minted sub-stories only. Applied to a `TECH` line it produces a marker that exists
nowhere else in the file — which is exactly how it got written twice on 2026-08-12 before anyone
noticed. `check_roadmap_placement.py` now rejects it.

## Two things that look like exceptions and are not

- **A document stating a rule must quote the form it forbids.** "`SF-01`, never `SF-1`" is a
  demonstration, and the checkers exempt a line showing both forms. A rule that cannot be written
  down cannot be enforced — `check_conventions` R5 makes the same carve-out for citation tags.
- **`Verifiable Proof` has no home on a one-line entry.** That is a real open question, not an
  oversight: either those citations move to the topic doc, or they belong to the design's FR ledger,
  which `check_fr_coverage.py` already reads.

## When you are updating roadmap state after a commit

Check off the boxes for the User Story and for each **capability** you implemented. Never for a
design's `SF-NN` sub-features — read that way, this instruction is a standing order to corrupt the
file, which is how the defect that produced this contract was introduced.

A (sub)story goes green only when its spanning tests are green too, `ADR-005` clause 4. A feature
that compiles is not a (sub)story that is finished.
