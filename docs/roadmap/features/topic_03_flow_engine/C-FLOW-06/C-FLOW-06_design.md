# C-FLOW-06 — Phase 3 Optimizations

**Status**: ✅ Finished — signed off by the user 2026-10-13. · **Phase**: 3 (Feature 3.32d)

| | |
|---|---|
| Touches | `assurance/graph/changes.py` · `core/flow/handlers/` (`changed_code.py`, `validation.py`, `prompting.py`, `lint_fix.py`) · `core/flow/interfaces/cli.py` · `workspace/project/scaffold.py` |
| Plan | [as built](C-FLOW-06_implementation_plan.md) |

## What it does

Four things that make runs cheaper or safer:

- **Contract outlines.** The API contracts a run writes reach the code-writing and review prompts
  as outlines (signatures, no bodies).
- **Tests of what changed.** A test step over the whole project runs only the tests of the modules
  changed since the last green test run, and of the modules that use them
  `[agreed 2026-10-13]`.
- **DAL gates.** Validation follows the target's DAL; on a strict DAL a warning fails the check.
- **Starter boundaries.** `sw init` writes `context.yaml` for the root, `src` and `tests`.

Runs never skip a whole step because its target looks unchanged, and lint-fix always lints its whole
target `[agreed 2026-10-13]`: a step that checked nothing must not read as green.

## How "what changed" is found

`sw run` and `sw resume` save the hash cache (`.specweaver/topology.cache.json`, `A-SENS-01`) after a
completed run whose whole-project test step passed — and only then. The next test step compares
each file's hash with that cache:

- a changed test file runs its own folder;
- a changed code file runs the tests of its closest module (`tests/<kind>/<module path>`) and of every
  module that uses it;
- a changed file of the root or `src` module, or a module with no test folder, runs the whole tier;
- nothing changed, no cache, or an unreadable cache: every test runs.

A file is compared per file, not per module hash, because a module's hash covers every module below
it: comparing those would mark the root changed for any change. In a run's worktree, the code there
is compared with the cache of the real project.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Contract outlines | Generation and review steps | SHALL add each recorded API contract to the prompt as its outline, and leave out a contract that cannot be read | the model writes against the real signatures for a few tokens |
| FR-2 | Tests of what changed | Test step; `sw run` | SHALL narrow a whole-project test step as described above, never to nothing, and SHALL save the hash cache only after a completed run whose whole-project test step passed | runs test what changed; untested code is never marked tested |
| FR-3 | DAL gates | `sw check`, runner | SHALL resolve the target's DAL and, on a strict DAL (`DAL_A`, `DAL_B`), fail the check on a warning (exit 1) | critical code is held to a higher bar without a flag |
| FR-4 | Starter boundaries | `sw init` | SHALL write `context.yaml` for the root, `src` and `tests`, with no model call, keeping a file that exists | the topology graph has modules from the first run |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Performance | Outlining one file takes under 1.0 s. |

## Live demo

`tests/e2e/capabilities/assurance/test_incremental_semantics_e2e.py`: in a `sw init` project with
two modules, `sw run` runs both modules' tests; after one module and its test change, the next
`sw run` runs 1 test; with nothing changed, both run again. A `validate_only` run saves no cache.
