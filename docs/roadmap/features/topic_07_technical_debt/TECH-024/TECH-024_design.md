# Design: RunContext God Object (TECH-006 Finding 3 Regrew, Not Fixed)

- **Feature ID**: TECH-024
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Code-verified audit of the TECH registry, 2026-07-31
  (`docs/analysis/tech_registry_audit_2026-07-31.md`, Part 3)

## Problem Statement

`TECH-006` (🟢 Completed, finished and immutable) documents three findings from a D-INTL-06 Red
Team analysis. Findings 1 (business logic misplaced in CLI interface layers) and 2
(cross-interface spider-web imports) are confirmed fixed. **Finding 3 — the `RunContext` god
object — is not fixed; it grew.** `TECH-006`'s own text documented it at 23 fields and a 67-line
`model_post_init`. Measured directly in `src/specweaver/core/flow/handlers/base.py` on
2026-07-31:

- `RunContext` (class starts line 30) now has **32 fields** (lines 47-90) — nine more than
  documented, including `db`, `llm_router`, `project_metadata`, `pipeline_runner`, `run_id`,
  `step_records`, `pipeline_name`, `dal_level`, `stale_nodes`, `parsers` added since.
- `model_post_init` spans **lines 92-159 — 68 lines** of side-effect-heavy initialization
  (parser factory injection, `ProjectMetadata` construction, environment/platform introspection,
  YAML-based archetype detection), one more line than documented and structurally unchanged: every
  new context source still lands here as another field plus more `model_post_init` branching.

`TECH-006`'s own recommended remediation — loading constitution/standards inside a shared
`build_base_prompt()` factory — was explicitly superseded by its own 2026-07-21 direction update
(constitution/standards move to domain loaders + canonical on-disk files under `C-INTL-06`/
`C-FLOW-11` instead), so Finding 3's fix was never actually attempted under either direction. Per
finished-stories-immutable, `TECH-006`'s own entry is not edited — this ticket tracks Finding 3 as
new, current work.

## Candidate Approaches (not yet designed)

- Group `RunContext`'s fields by concern (project/spec identity, LLM/adapter wiring, isolation
  policy, plan/decomposition state, telemetry/lineage, prompt-context payloads) and extract
  cohesive sub-objects, composed onto `RunContext` rather than flattened into it.
- Re-evaluate against the settled `C-INTL-06`/`C-FLOW-11` direction (envelope-vs-content,
  domain loaders + on-disk files) so this refactor doesn't propose the same centralization its
  own predecessor ticket already reversed.
- Coordinate with `TECH-015` (`runner_utils.py` / grab-bag module split), which explicitly flagged
  this same file as adjacent scope to avoid collision.

## Non-Goals (proposed, pending design)

- Not a re-litigation of Findings 1/2 — those are confirmed fixed and out of scope here.
- Not a reversal of the 2026-07-21 direction update (no centralizing content loading inside a
  prompt factory).

## Next Step

Run through `specweaver-design` to group the 32 fields by concern and produce an extraction plan.
