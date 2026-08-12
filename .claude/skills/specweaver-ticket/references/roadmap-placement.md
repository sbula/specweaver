# Where a thing is written down

One home per fact. This is the contract for `docs/roadmap/master_story_roadmap.md` and the documents
around it, enforced by `scripts/check_roadmap_placement.py` in the `doc` gate.

It exists because it did not. Every rule below was already the convention in the file and written
down nowhere, so each agent derived it from whatever it happened to grep — and what it grepped was
Topic 07, where the convention was broken in four of twenty-four entries. Precedent in the artifact
beat the rule, repeatedly, because there was no rule to beat.

## The three documents

| Document | Holds | Does not hold |
|---|---|---|
| `master_story_roadmap.md` | One line per registry ID: id, short name, link, status. Plus a story's `Benefit` and `Sequencing` as a clause each | Measurements, `file:line` references, out-of-scope lists, rationale, a design's sub-features |
| `topics/topic_NN_*.md` | The full prose for each entry — origin, evidence, fix shape, out-of-scope | Anything the design document owns |
| `features/<topic>/<ID>/<ID>_design.md` | Everything about the ticket, including its `SF-NN` decomposition | — |

If you are about to write the same fact in two of these, it belongs in the lower one and the upper
one links to it.

## The rules

**R-PLACE — a line exists only for something with its own registry ID.**

A `US-N` entry lists capability IDs and `INT-US-NN-SFxx` sub-story IDs, one line each. A design
document's `SF-01` is internal decomposition: no registry ID, no independent existence, and it never
appears here.

> **Two different things are spelled "SF", and this is the trap.** `INT-US-21-SF01` is a *minted
> sub-story* with its own design and integration contract — it belongs. `SF-01` in a design's
> Sub-Feature Breakdown is *internal decomposition* — it never does. `US-21` lists the first and not
> the second. Getting this backwards is the original defect this contract was written for.

**R-LENGTH — a line inside an entry is at most 200 characters.**

The file is an overview. The number comes from the file's own distribution — median 58–96, p90 ~190
— so the rule ratifies what the document already does rather than imposing something new.

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

Check off the boxes for the User Story and any **sub-story add-ons** (`INT-US-NN-SFxx`) you
implemented. **"Add-Ons" here means minted sub-story IDs, never a design's `SF-NN` sub-features.**
Read as the latter, that instruction is a standing order to corrupt this file — which is how the
defect that produced this contract was introduced.
