# Design: Registry Claims Recursive Decomposition the Capability Does Not Implement

- **Feature ID**: TECH-038
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: `TECH-018` audit, 2026-08-13, finding 1. Filed separately because `TECH-018` is
  audit-only and forbids editing `INT-US-21-SUB`'s entry (finished-stories-immutable).

## Problem Statement

`INT-US-21-SUB` / `C-INTL-01` is registered as **"Recursive Planning"**, and its integration
description states the capability *"implements iterative decomposition, generating a structured
DecompositionPlan by resolving the AST graph into sub-tasks."*

Measured against `src/` on 2026-08-13, the shipped capability does none of the three.

| Registered claim | What the code does |
|---|---|
| **Recursive** | `FeatureDecomposer.decompose` (`workflows/planning/decomposer.py:65`) builds one prompt, makes **one** `llm.generate` call, parses one plan, returns. No self-invocation, no depth parameter, no re-entry. |
| **Iterative** | No loop anywhere in the decomposer or its caller. **One call site in all of `src/`** — `core/flow/handlers/decompose.py:66` — invoked once per run. |
| **Resolves the AST graph into sub-tasks** | The graph is **prompt context**, not a source of sub-tasks: the call site passes `topology_contexts=[context.graph.topology] if context.graph.topology else None`, which `PromptBuilder.add_topology` appends to the prompt text. The components come from the LLM reading the feature spec's markdown. |

The data model settles it. `DecompositionPlan` is **flat** — `components: list[ComponentChange]`,
each carrying `dependencies: list[str]`. That is a one-level DAG of names. **There is no nesting to
recurse into**, so recursion is not merely unimplemented, it is *unrepresentable in the type the
capability returns*. Any real recursion is therefore a schema change, not a control-flow change.

`INT-US-21`'s base contract corroborates from the opposite direction, and was written by a
different session: its delivered journey is specified and proven to cost **"exactly one LLM
call."** A recursive decomposition cannot cost one call.

**This is a registry-accuracy defect, not a live one.** The single-pass decomposer works, is
covered by `test_feature_decomposition_e2e.py`'s 24 scenarios, and is exactly what every consumer
depends on today — which is why the mismatch survived delivery and an epic closure. It becomes
live the moment a reader plans against the registry: `C-FLOW-12` / `INT-US-21-SF02` is the next
consumer of the decomposition plan, and it is currently unplanned.

## The Decision This Ticket Exists To Make

Exactly one of the two sides is wrong, and the ticket must not assume which:

- **(a) The description is wrong.** Correct it to name what shipped — single-pass, LLM-authored
  decomposition into a flat component DAG, with graph topology as prompt context. Cheap; makes the
  registry honest; forecloses nothing, since (b) can still be filed later as new scope.
- **(b) The scope is wrong.** Recursive decomposition was genuinely intended and was never built.
  Then this is not a documentation fix but an unbuilt capability, and it needs a schema
  (`ComponentChange` cannot nest), a termination rule, a per-level cost model, and its own story —
  none of which exist.

**Evidence needed before choosing:** the `C-INTL-01` design doc and the commit that delivered it,
to establish whether recursion was designed-and-dropped or never designed. Do not choose from the
registry wording alone — that wording is the artefact under suspicion.

## Constraints

- **The delivered entry is immutable.** Whatever is decided, `INT-US-21-SUB`'s existing entry is
  not edited in place beyond what the correction itself requires; if (a), the correction is the
  minimum edit that removes the false claim, recorded here with its justification.
- **Consider `OQ-1` at the same time.** The same entry already carries a documented naming
  divergence — `INT-US-21-SUB` in `US-21_integration.md` versus `INT-US-21-SF01` in
  `master_story_roadmap.md`, accepted 2026-07-25 rather than corrected because renaming a delivered
  identifier would breach finished-stories-immutable. Two accepted inaccuracies on one entry is
  worth resolving in one pass, not two.

## Non-Goals (proposed, pending design)

- Building recursive decomposition. If (b) is the answer, this ticket files the story; it does not
  implement it.
- Re-auditing `INT-US-21`'s base contract — delivered, and proven by 24 e2e scenarios.
- The add-on's **proof-claim** defect (its Verifiable Proof cites 4 unit tests and two integration
  files that patch `FeatureDecomposer` out). That is `TECH-018` finding 2 and is handed to
  `TECH-017` as its result for this add-on. Do not double-cover it here.

## Guardrail to Ship With the Fix

A registry entry describing behaviour that does not exist is the same defect class as `TECH-019`
(instructions ordering the agent to read a deleted file) and `TECH-026` (registry placement with no
written contract) — both closed by shipping a checker, and both would have regrown without one.

The honest difficulty: *"does this prose match this code"* is not mechanically checkable in
general. So scope the guardrail to what **is** checkable, and say plainly in the design what it
does not cover. Candidate: a delivered capability whose registered description names a structural
property (recursive, streaming, incremental, parallel) must cite the test that demonstrates it —
the same shape as `check_fr_coverage.py`, applied to capability descriptions rather than FRs.

## Next Step

Run the `specweaver-design` skill against this stub before any implementation.
