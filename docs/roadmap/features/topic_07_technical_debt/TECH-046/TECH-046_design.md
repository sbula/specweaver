# Design: `C-INTL-01` Shipped Without the Recursion It Was Designed For

- **Feature ID**: TECH-046
- **Epic**: Topic 07 (Technical Debt)
- **Status**: 🟢 **RESOLVED 2026-08-13.** Both halves of the decision taken: `FR-3` descoped, and
  the recursion minted as `C-INTL-07` to be built properly.
- **Origin**: `TECH-038`, 2026-08-13. That ticket asked which of two sides was wrong — the registry
  description, or the scope. The evidence says the scope. This is the follow-up it promised to
  file rather than implement.

## Problem Statement

`C-INTL-01` is marked ✅ and its design is titled **"Automated iterative decomposition
(multi-level)"**. It specifies recursive, multi-level decomposition — feature → sub-features →
components — with:

- **FR-3 Component Fan-out:** *"Automatically spawns a sub-pipeline iteration for each approved
  component; N individual L3 pipelines are launched."*
- **AD-2 Automated Recursive Spawn:** *"`flow/runner.py` will allow a pipeline step to dynamically
  queue new L3 sub-pipelines."*
- An **agent-sized heuristic**: a sub-feature is recursively split if it handles more than 5 FRs,
  touches more than 3 modules, or integrates more than 1 external API.

**None of it was built.** `FeatureDecomposer.decompose` is a single LLM call from a single call
site, and `DecompositionPlan` is flat — `components: list[ComponentChange]` with
`dependencies: list[str]` — so a component cannot itself decompose. Recursion is not merely absent
from the implementation; it is unrepresentable in the type the capability returns.

**And it was never descoped.** Neither implementation plan records a decision to drop it. There is
no note, no deferral, no superseding ticket. It simply is not there, while the entry says ✅.

## This was mechanically detectable the whole time

`scripts/check_fr_coverage.py C-INTL-01` — which has existed since `TECH-025` — reports:

```
FR-1    NO PLAN  NO TEST
FR-2    plan     NO TEST
FR-3    NO PLAN  NO TEST
FR-4    plan     NO TEST
FR-5    plan     NO TEST
BLOCKED: C-INTL-01 must not be declared finished.
```

FR-1 and FR-3 were never carried by any implementation plan. All five FRs are cited by no test.

**This is the third instance of one disease**, and that is the finding worth keeping: a correct
check that nobody invokes. `check_story_preconditions.py` would have caught `INT-US-25`'s
delivered-with-no-proof state any day and never ran; `check_class_health.py` reported *"nothing in
scope"* for a whole session while 23 classes failed; and this gate has been able to block
`C-INTL-01` since it was written. All three are story-scoped, and a story-scoped check only fires
when a human remembers the story.

## Candidate Approaches (not yet designed) — the decision this ticket needs

Exactly one of these, and it should be taken explicitly rather than by default:

1. **Build the recursion.** It needs a nestable schema (`ComponentChange` cannot nest), a
   termination rule, a per-level cost model — a single decomposition already costs one LLM call —
   and its own story. Note that `C-FLOW-12` covers FR-3's **fan-out execution** but says nothing
   about multi-level splitting, so it is not a substitute.
2. **Formally descope it.** Delete the unbuilt rows from the design's FR table, which is what
   `check_fr_coverage.py`'s own failure message instructs: *"If an FR is genuinely out of scope,
   delete the row from the design's FR table so the descoping is visible."* Then `C-INTL-01`'s ✅
   becomes true, and `TECH-038`'s registry wording follows from it.

Option 2 is likely correct — nothing consumes recursion today, the single-pass journey is proven by
24 e2e scenarios, and `C-FLOW-12` is the scheduled next consumer — but it is a scope decision, not
a documentation edit, which is why this is a ticket rather than a fix.

## Non-Goals (proposed, pending design)

- Editing `C-INTL-01`'s roadmap entry. Finished-stories-immutable: the correction lands as this
  ticket's outcome, not as a rewrite of a delivered line.
- The registry **wording**, which is `TECH-038`'s and follows whichever decision is taken here.
- The 46-of-103 capability-wide FR-coverage failure measured on 2026-08-13 — recorded in
  `TECH-017`, whose per-story matrix is that work.

## Decision, 2026-08-13

**Neither option alone — both, split along the line the evidence actually drew.**

**`FR-3` descoped.** *"Component Fan-out — spawns a sub-pipeline per approved component"* was never
built and never planned, but the scope did not vanish: it is `C-FLOW-12`, registered and sequenced.
The row is **deleted** from `C-INTL-01`'s FR table rather than annotated, so the descoping is
visible in the artifact — which is what `check_fr_coverage.py`'s own failure message instructs.
`C-INTL-01` now declares 4 FRs, not 5.

**The recursion is minted as `C-INTL-07`, not descoped.** `AD-2` (Automated Recursive Spawn), the
design's *multi-level* title and the agent-sized split heuristic describe a capability nothing else
covers — `C-FLOW-12` executes a flat DAG and says nothing about splitting a sub-feature. Option 2
alone would have quietly redefined `C-INTL-01` as what it turned out to be, and lost the intent.

`C-INTL-07` carries the three things that make it more than a control-flow change: the schema
(`DecompositionPlan.components` is flat, and the persisted artifact is a frozen `INT-US-21` seam
`C-FLOW-12` consumes, so migration is required), termination with an explicit depth cap, and a cost
model — the single-pass journey costs exactly one LLM call and recursion multiplies that per level.

Its design also fixes its own closure bar up front, because shipping without one is why this ticket
exists: **a recursion capability whose recursion is untested is the exact defect being corrected.**

### Correction, same day: a descope is only honest if the requirement is re-stated

The first version of this decision said `FR-3`'s scope "moved to `C-FLOW-12`" and deleted the row.
That was asserted, not verified. **`C-FLOW-12` declared no Functional Requirements at all** — its
design is Problem Statement / Seams / Non-Goals / Sequencing, describing per-component spec
synthesis and race-hardened fan-out in prose only.

So the descope had converted a **testable stated requirement** into a **prose mention**. Nothing
would have failed if the fan-out were never built; there was no longer a requirement to be uncited.
That is a traceability regression wearing the appearance of a tidy hand-off.

`C-FLOW-12` now declares four FRs, `FR-1` being `C-INTL-01`'s `FR-3` carried across verbatim in
substance. The rule this establishes: **deleting an FR row is legitimate when the work is genuinely
out of scope, or when the receiving capability states it as a requirement — never merely because
another document mentions the subject.**

It also exposed a flaw in `TECH-047`'s ratchet, fixed the same day. It counted uncited FRs across
*every* design, so adding these four to an unbuilt capability raised the total and blocked the
commit — **punishing the act of writing requirements down before building**. The sweep now counts
delivered stories only; an unbuilt capability's requirements are correctly uncited.
