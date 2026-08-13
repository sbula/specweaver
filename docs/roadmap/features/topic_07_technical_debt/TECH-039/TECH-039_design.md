# Design: One Identifier Names Two Delivered Add-Ons (`INT-US-05-SUB` Collision)

- **Feature ID**: TECH-039
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Found by `scripts/check_proof_tier.py` on its **first run**, 2026-08-13, while
  shipping `TECH-017`'s guardrail slice. Not looked for.

## Problem Statement

`US-05_integration.md` gives **two different delivered add-ons the same identifier**:

```
* **Intelligent Code Exclusions (`INT-US-05-SUB`)**      -> C-SENS-02, .specweaverignore engine
* **Framework Native Understanding (`INT-US-05-SUB`)**   -> B-INTL-02, Macro Evaluator
```

Both are `Status: ✅ Complete`. They integrate different capabilities, cite different proof, and
solve unrelated problems. They share one ID.

**Measured 2026-08-13** across all 28 contract documents: **31 distinct IDs across 32 entries** —
exactly one collision, this one. Only two entries in the whole tree use the `-SUB` form at all
(`INT-US-05-SUB`, `INT-US-21-SUB`); every other add-on uses the `SF{2d}` form that `TECH-027`
made the contract.

### The correct IDs already exist

`master_story_roadmap.md` names these same two add-ons **distinctly and correctly**:

| Add-on | Roadmap ID | Contract file ID |
|---|---|---|
| Intelligent Code Exclusions (`C-SENS-02`) | `INT-US-05-SF03` ✅ | `INT-US-05-SUB` |
| Framework Native Understanding (`B-INTL-02`) | `INT-US-05-SF04` ✅ | `INT-US-05-SUB` |

So this is not an open question about what the IDs *should* be. The registry already answers it;
one document disagrees with itself and with the registry.

### Why this is not the same as `OQ-1`, and must not be closed the same way

`US-21_integration.md` carries a documented, **accepted** divergence (`OQ-1`, 2026-07-25):
`INT-US-21-SUB` there versus `INT-US-21-SF01` in the master roadmap. That was accepted rather than
corrected because renaming a delivered identifier would breach finished-stories-immutable.

The reasoning does not transfer. `OQ-1` is a **divergence** — two names for one thing, ugly but
unambiguous. This is a **collision** — one name for two things, which is *ambiguous by
construction*:

- Nothing that reads `US-05_integration.md` can tell the two entries apart by ID. Any tool keying
  on the identifier processes one and silently drops the other, or merges their claims.
- This is not hypothetical. `check_proof_tier.py` had to key its ratchet on **file + title instead
  of ID** specifically to work around this entry — and its docstring says so. A defect that forces
  a tool to route around it has already cost something.
- `check_story_preconditions.py INT-US-05-SUB` resolves to whichever entry its regex reaches first.
  The other add-on's preconditions cannot be checked at all.

## Candidate Approaches (not yet designed)

1. **Adopt the roadmap's IDs in the contract file** (`SF03` / `SF04`). The registry already
   declares them, so this is reconciling a document *to* the registry rather than minting anything.
   The finished-stories-immutable question is whether correcting a **duplicated** identifier on a
   delivered entry is a rename (forbidden) or a repair of something that was never a valid
   identifier (permitted). The design must answer that explicitly and record the answer, because
   `OQ-1` set the opposite precedent for the divergence case and the two will be confused.
2. **Leave both, document the collision** as `OQ-1` did. Cheapest, and consistent with precedent —
   but it leaves an ambiguous identifier that tooling must keep routing around, and the next tool
   will not know to.
3. **Widen to a guardrail.** Whatever is decided for this instance, ship the check that makes a
   second one impossible: no identifier may name two entries. That is mechanical, has no false
   positives, and the sweep that found this already walks every contract.

## Non-Goals (proposed, pending design)

- `OQ-1` itself (`INT-US-21-SUB` vs `INT-US-21-SF01`). A divergence, already accepted and
  documented; reopening it is `TECH-038`'s business, which touches that same entry.
- The **proof** quality of either add-on — both are frozen in `scripts/baselines/proof_tier.json`
  and owned by `TECH-017`'s per-story matrix. This ticket is about the identifier only.
- Renaming anything in `master_story_roadmap.md`. The roadmap is the side that is already correct.
- Re-litigating `TECH-027`'s `SF-{2d}` format contract. This is a violation of it, not a challenge
  to it.

## Guardrail to Ship With the Fix

Approach 3, regardless of how 1 vs 2 is decided: **an identifier must name at most one entry.**
Cheapest guardrail in the debt backlog — the sweep exists, the parser exists, and the invariant has
exactly one violation to freeze or fix. Same lesson as `TECH-019` and `TECH-026`: this class of
defect regrows unless a check stops it.

Note for the design: the check must key on the *parsed entry*, not on a text grep, or it will
report the two legal mentions of an ID (heading plus a prose reference) as a collision.

## Next Step

Run the `specweaver-design` skill against this stub before any implementation.
