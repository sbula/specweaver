# Design: Repo-Wide Cyclomatic Complexity Violations (complexipy)

- **Feature ID**: TECH-023
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Found while running `python scripts/quality.py cb` for TECH-001 SF-04
  (2026-08-02) — confirmed via `git stash` to be chronic and unrelated to that commit
  (identical failure list with or without SF-04's changes applied).

## Problem Statement

`complexipy` (cyclomatic complexity, threshold 15) currently fails for **98 functions across 68
files** — reproducible via:
```
complexipy src --failed --max-complexity-allowed 15
```
This spans nearly every domain in the codebase (graph, standards analyzers, validation rules,
core.config, core.flow handlers, LLM adapters, sandbox executors, AST parsers, workflows
interfaces) — it is not localized to any one recent feature or refactor.

Two of the 98 are already the explicit, in-progress scope of other TECH tickets and are **out of
scope here**, tracked there instead:
- `PipelineRunner::_execute_loop` (52) — `TECH-020`'s exact target (`core/flow/engine/runner.py`).
- `RunContext::model_post_init` (17) — `TECH-006` SF-02's exact target
  (`core/flow/handlers/base.py`).

Worst offenders among the remaining 96 (severity ordering, not exhaustive — see the reproduction
command above for the full list):
- `OrchestrateComponentsHandler::execute` (79) — `core/flow/handlers/decompose.py`
- `drift_check_rot` (51) — `assurance/validation/interfaces/cli_drift.py`
- `find_by_glob` (49) — `sandbox/filesystem/core/search.py`
- `DependencyHasher::_hash_directory` (36) — `assurance/graph/hasher.py`
- `load_evaluator_schemas` (36) — `workflows/evaluators/loader.py`
- `tree_command` (34) — `graph/interfaces/cli.py`

Per this project's pre-commit skill: "no inherited problems are acceptable" — but 98 functions
across 68 unrelated files is not a mechanical fix incidental to any one commit; it needs its own
scoped effort(s), not to be absorbed into whichever commit happens to touch the gate next.

## Candidate Approaches (not yet designed)

- Triage by severity and domain into batches (e.g. one PR per bounded context), rather than one
  mega-refactor — matches this registry's own "own commits, never bundled" convention used
  elsewhere (TECH-015, TECH-016, TECH-020).
- For each function: extract sub-steps into named collaborators (the same pattern TECH-020
  proposes for `_execute_loop`), not just complexity-suppression comments.
- Decide whether any legitimately-irreducible functions (e.g. a large dispatch table) warrant a
  documented, reviewed exception rather than forced splitting — and if so, through what
  mechanism (this registry has no per-function complexity-baseline/allowlist today, unlike
  `check_suppressions.py`'s ratchet for `noqa`/`type: ignore`).

## Non-Goals (proposed, pending design)

- Not a rewrite of any single module's behavior — structural extraction only, zero behavior
  change, matching this registry's standard NFR for refactor-classified tickets.
- Does not include `TECH-020`'s or `TECH-006` SF-02's already-owned functions (see above).

## Next Step

Run through `specweaver-design` to decide the triage/batching strategy and produce implementation
plan(s).
