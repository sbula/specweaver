# Design: Multi-Level Recursive Decomposition

- **Feature ID**: C-INTL-07
- **Epic**: Topic 04 (Intelligence)
- **Design Doc**: `docs/roadmap/features/topic_04_intelligence/C-INTL-07/C-INTL-07_design.md`
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: 2026-08-13, from `TECH-046`. `C-INTL-01` was designed as *"Automated iterative
  decomposition (multi-level)"* and shipped single-pass. Rather than quietly redefine that
  capability as what it turned out to be, the unbuilt half is minted here and built properly.

## Problem Statement

`C-INTL-01` produces a **flat** plan: one LLM call reads a feature spec and returns
`DecompositionPlan.components`, a `list[ComponentChange]` whose `dependencies` are sibling names.
That is a one-level DAG.

Its design promised more, in three places:

- the title — *"Automated iterative decomposition (**multi-level**)"*;
- `AD-2` **Automated Recursive Spawn** — *"`flow/runner.py` will allow a pipeline step to
  dynamically queue new L3 sub-pipelines"*;
- an **agent-sized heuristic** — a sub-feature is recursively split if it handles more than 5 FRs,
  touches more than 3 modules, or integrates more than 1 external API.

None was built, and none was descoped. `TECH-046` established that with evidence and this
capability is its answer.

## Goal

Decomposition that goes deeper than one level: a feature splits into sub-features, each of which
splits again until the agent-sized heuristic says stop, and the result is a tree the fan-out can
walk. Today `sw run feature_decomposition` returns a flat list of components, which is correct for
a small feature and silently under-describes a large one.

## Relationship

- **`C-INTL-01`** — the single-pass planner this extends. Its `AD-2`, its *multi-level* title and
  its agent-sized heuristic are the promise; its `FR-3` was descoped to `C-FLOW-12` (`TECH-046`).
- **`C-FLOW-12`** — executes the plan and consumes the persisted artifact. It owns fan-out; this
  owns depth. Its `FR-1..FR-4` were written on 2026-08-13 so the descope had a stated home.
- **`B-FLOW-05`** — token-burn circuit breakers, the natural substrate for the per-level cost cap.
- **`INT-US-21-SF03`** — the integration contract for this capability.

## Why this is not a small change

**Recursion is unrepresentable in the current type**, so it is a schema change before it is a
control-flow change. `ComponentChange` has no field that can hold another `DecompositionPlan`, and
`build_sequence` is a flat list of component names. A recursive planner has nowhere to put its
output.

The single-pass journey also costs **exactly one LLM call**, which `INT-US-21`'s contract states
and proves. Recursion multiplies that by the number of nodes that fail the heuristic, at every
level. Cost is a design input here, not an afterthought.

## Candidate Approaches (not yet designed) — the decisions this design must take

1. **The schema.** Does a `ComponentChange` gain an optional child plan, or does the plan become a
   tree with typed nodes? The second is cleaner and breaks the persisted
   `<stem>_decomposition.yaml` schema, which `INT-US-21` froze as a seam and `C-FLOW-12` consumes —
   so a migration path is required, not optional.
2. **Termination.** The agent-sized heuristic (>5 FRs, >3 modules, >1 external API) is a
   *stopping rule*, and it is stated in prose in `C-INTL-01`'s design without a test. It needs an
   explicit maximum depth as well, because an LLM that keeps proposing sub-features would otherwise
   recurse until the budget dies.
3. **Cost.** A per-level and per-run cap, and what happens when it is hit — fail, or return the
   partial tree and say so. `B-FLOW-05` (token-burn circuit breakers) is the natural substrate.
4. **Who consumes a tree.** `C-FLOW-12` executes the flat DAG. Does it flatten a tree, or does it
   execute depth-first? Deciding this late means building the producer against a guess.
5. **HITL.** `C-INTL-01`'s `FR-2` gates one plan. A tree implies either one gate at the end, or a
   gate per level — which changes the journey `INT-US-21` proved.

## Non-Goals (proposed, pending design)

- **Component fan-out execution.** `C-FLOW-12` owns per-component spec synthesis and race-hardened
  fan-out; that was `C-INTL-01`'s `FR-3`, descoped there on 2026-08-13 and pointing here only for
  the *recursive* half.
- Changing the single-pass path. It works, is proven by 24 e2e scenarios, and must keep working —
  recursion is opt-in or depth-1 must remain exactly today's behaviour.
- Editing `C-INTL-01`'s entry beyond the `FR-3` descope already recorded there.

## Verifiable Proof — the bar this must meet

Set here deliberately, because `C-INTL-01` shipped without it and that is why this ticket exists.
Per `closure-contract.md`: **every FR proven by a test, and any FR not built deleted from the table
rather than left standing.** A recursion capability whose recursion is untested is the exact defect
being corrected — at minimum an e2e that decomposes a feature deep enough to split, and asserts the
tree's shape and the termination rule firing.

## Integration

Integrated by **`INT-US-21-SF03`**, minted 2026-08-13. Its contract owns the journey — the migrated
artifact schema, the HITL gate's behaviour across levels, and the termination rule firing end to
end — while this capability owns the planner.

## Next Step

Run the `specweaver-design` skill against this stub. Question 1 (schema and migration) gates the
rest; nothing else can be designed until the persisted artifact's shape is decided.
