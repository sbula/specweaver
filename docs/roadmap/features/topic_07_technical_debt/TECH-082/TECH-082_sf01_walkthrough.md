# Walkthrough: TECH-082 SF-01 — Validation orchestration home

## CB-1: validation policy in its new home (FR-1, NFR-2, NFR-3, NFR-4)

**What changed**
- `validation_hydrator.py`, `archetype_pipelines.py` (from `core/flow/handlers`) and
  `project_paths.py` (from `core/flow/engine`) moved by `git mv` to the new module
  `assurance/validation/orchestration` (AD-1). Its manifest is an `orchestrator` that declares
  `widens: specweaver/sandbox` with a reason (FR-15).
- Importers re-pointed: the validation CLI, `POST /check`, the API's path helper, and 4 handlers
  (`validation.py`, `lint_fix.py`, `qa_targets.py`, `review.py`). No shim (AD-6).
- `tach.toml`: the new module, its `[[interfaces]]` block, edges from the validation CLI, the API
  and the handlers; the validation CLI lost its `core.flow.handlers` edge. Manifests match; the
  validation CLI narrowed `core/flow` to `core/flow/engine` in `consumes` and `widens`.
- 7 test files moved to mirror the source; 9 others changed only their import or `mock.patch` line.
- Mutants: 12 re-pointed to the new files and refreshed; 11 more refreshed whose symbol changed only
  by an import line. `stale_mutants.py`: 0 stale.
- `tests/unit/test_layer_import_isolation.py`: the validation tree may import the sandbox only
  where a manifest declares it in `widens`; the folders that do are pinned (the CLI and the new
  module). Before, it allowed one named file only. Probed: a sandbox import planted in
  `executor.py` fails it.

**Tests**: new guard `test_validation_has_its_own_home.py` (11), red first with 7 failures (the CLI
and the API imported the handlers; the old paths imported). Full suite after the fix: see the gated
commit. `tach check` passes.

**Mutant** (FR-1): a handlers import put back in the validation CLI → 3 tests object.

**Coverage matrix**

| Unit | Unit | Integration | E2E |
|---|---|---|---|
| moved functions | ✅ (moved tests) | ✅ (moved tests) | ✅ `test_architecture_pipeline.py` |
| the import guard | ✅ | — | — |

**Red/blue (7.5)**
- R1 (MEDIUM, for the user's review) the sandbox-isolation guard (`TECH-002` FR-5) now accepts
  imports a manifest declares in `widens`, not one named file. This follows FR-15; the declared
  folders are pinned, so a new widening still changes the test.
- R2 (LOW) file names stay the same in the new home; renames belong to SF-06.
- No decision needed.
