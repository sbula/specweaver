# C-INTL-07 — Multi-Level Recursive Decomposition

**Status**: STUB — not yet run through the `specweaver-design` skill · **Topic**: 04 (Intelligence) ·
**Feature ID**: C-INTL-07 · **Origin**: 2026-08-13, from `TECH-046`

| | |
|---|---|
| Extends | `C-INTL-01` — the single-pass planner. Its `AD-2`, its *multi-level* title and its agent-sized heuristic are the promise; its `FR-3` was descoped to `C-FLOW-12` (`TECH-046`) |
| Used by | `C-FLOW-12` — executes the plan and consumes the persisted artifact. It owns fan-out; this owns depth. Its `FR-1..FR-4` were written on 2026-08-13 so the descope had a stated home |
| Builds on | `B-FLOW-05` — token-burn circuit breakers, the natural substrate for the per-level cost cap |
| Integrated by | `INT-US-21-SF03` (minted 2026-08-13) |

`C-INTL-01` was designed as *"Automated iterative decomposition (multi-level)"* and shipped
single-pass. The unbuilt half is minted here and built properly, rather than quietly redefining
`C-INTL-01` as what it turned out to be.

## What it does

Decomposition deeper than one level: a feature splits into sub-features, each of which splits again
until the agent-sized heuristic says stop. The result is a tree the fan-out can walk.

Today `sw run feature_decomposition` returns a flat list of components — correct for a small
feature, silently under-describes a large one.

## Why: the promise that was not built

`C-INTL-01` produces a **flat** plan: one LLM call reads a feature spec and returns
`DecompositionPlan.components`, a `list[ComponentChange]` whose `dependencies` are sibling names.
That is a one-level DAG. Its design promised more, in three places:

- the title — *"Automated iterative decomposition (**multi-level**)"*;
- `AD-2` **Automated Recursive Spawn** — *"`flow/runner.py` will allow a pipeline step to
  dynamically queue new L3 sub-pipelines"*;
- an **agent-sized heuristic** — a sub-feature is recursively split if it handles more than 5 FRs,
  touches more than 3 modules, or integrates more than 1 external API.

None was built, none was descoped. `TECH-046` established that with evidence.

## Why this is not small — read before scoping

- **Schema first.** Recursion is unrepresentable in the current type. `ComponentChange` has no field
  that can hold another `DecompositionPlan`; `build_sequence` is a flat list of component names. A
  recursive planner has nowhere to put its output.
- **Cost.** The single-pass journey costs **exactly one LLM call** — `INT-US-21`'s contract states
  and proves it. Recursion multiplies that by the number of nodes that fail the heuristic, at every
  level. Cost is a design input.

## Open decisions (not yet designed)

1. **Schema.** Does a `ComponentChange` gain an optional child plan, or does the plan become a tree
   with typed nodes? The tree is cleaner but breaks the persisted `<stem>_decomposition.yaml`
   schema, which `INT-US-21` froze as a seam and `C-FLOW-12` consumes — a migration path is
   required.
2. **Termination.** The agent-sized heuristic (>5 FRs, >3 modules, >1 external API) is a
   *stopping rule*, stated in prose in `C-INTL-01`'s design without a test. It also needs an
   explicit maximum depth — otherwise an LLM that keeps proposing sub-features recurses until the
   budget dies.
3. **Cost.** A per-level and per-run cap, and what happens when it is hit: fail, or return the
   partial tree and say so. Substrate: `B-FLOW-05`.
4. **Who consumes a tree.** `C-FLOW-12` executes the flat DAG. Flatten the tree, or execute
   depth-first? Deciding late means building the producer against a guess.
5. **HITL.** `C-INTL-01`'s `FR-2` gates one plan. A tree means one gate at the end or a gate per
   level — which changes the journey `INT-US-21` proved.

Decision 1 (schema and migration) gates the rest: nothing else can be designed until the persisted
artifact's shape is decided.

## Non-goals (proposed, pending design)

- **Component fan-out execution.** `C-FLOW-12` owns per-component spec synthesis and race-hardened
  fan-out. That was `C-INTL-01`'s `FR-3`, descoped there on 2026-08-13; it points here only for the
  *recursive* half.
- Changing the single-pass path. It is proven by 24 e2e scenarios and must keep working: recursion
  is opt-in, or depth-1 stays exactly today's behaviour.
- Editing `C-INTL-01`'s entry beyond the `FR-3` descope already recorded there.

## Verifiable proof — the bar

`C-INTL-01` shipped without one; that is why this ticket exists. Per `closure-contract.md`: **every
FR proven by a test; any FR not built is deleted from the table, not left standing.** Minimum: an
e2e that decomposes a feature deep enough to split and asserts the tree's shape and the termination
rule firing.

## Integration

`INT-US-21-SF03` owns the journey — the migrated artifact schema, the HITL gate's behaviour across
levels, the termination rule firing end to end. This capability owns the planner.

**Next**: run `specweaver-design` against this stub, starting with decision 1.
