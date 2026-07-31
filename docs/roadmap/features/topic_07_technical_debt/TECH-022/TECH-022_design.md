# Design: Circular Dependencies Between `core.config` and `infrastructure.llm` / `core.flow`

- **Feature ID**: TECH-022
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Code-verified audit of the TECH registry, 2026-07-31
  (`docs/analysis/tech_registry_audit_2026-07-31.md`, Part 3)

## Problem Statement

`TECH-001` (🟢 Completed, finished and immutable) claims its DDD unification "prevent[s]
'Dumping Ground' anti-patterns and circular dependencies as the team scales." A code audit found
this overstates the delivered result: `tach.toml` explicitly declares two mutual (circular)
module dependencies that are live today:

- `specweaver.core.config` ⇄ `specweaver.infrastructure.llm` — `core.config` depends on
  `infrastructure.llm` (`tach.toml:34`) while `infrastructure.llm` depends on `core.config`
  (`tach.toml:54`).
- `specweaver.core.config` ⇄ `specweaver.core.flow` — `core.config` depends on `core.flow`
  (`tach.toml:34`) while `core.flow` depends on `core.config` (`tach.toml:42`).

Both cycles are `tach`-declared (not silent violations — `tach check` passes), but a declared
cycle is still a cycle: bounded-context layout elsewhere in `src/` is real and correct
(no flat `config/`/`cli/`/`loom/`), so `TECH-001`'s bounded-context claim stands, but its
circular-dependency claim does not. Per finished-stories-immutable, `TECH-001`'s own entry is not
edited — this ticket tracks the residual gap as new work.

## Candidate Approaches (not yet designed)

- Identify which direction of each cycle is the "wrong" one (e.g. does `core.config` need to
  import from `infrastructure.llm`/`core.flow`, or can that dependency be inverted/extracted to a
  shared interface both sides implement).
- Consider whether `core.config` should stay a pure leaf module with no outbound dependencies on
  higher-level bounded contexts.

## Non-Goals (proposed, pending design)

- Not a rewrite of `TECH-001`'s delivered DDD layout — that boundary structure is confirmed
  correct and out of scope here.

## Next Step

Run through `specweaver-design` to determine the correct dependency direction and produce an
implementation plan.
