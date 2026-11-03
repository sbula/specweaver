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

## CB-2: the drift model call leaves the handler (FR-2)

**What changed**
- `assurance/validation/orchestration/drift_analysis.py` (new): `explain_drift(adapter, config,
  findings, file_path)` builds the prompt, calls the model, returns the text; the spend brake →
  None; any other error → `"LLM analysis failed: …"`. A finding's text is folded onto one line.
- `DriftCheckHandler._analyze_drift` now only gets the adapter (`llm_for`) and calls
  `explain_drift`. **Deviation**: the plan said delete the method; it stays as the thin step that
  gathers the adapter, so `llm_for` failing (no model) still reports "LLM analysis failed" as today.
- The new module's manifest declares `widens: specweaver/infrastructure/llm`; tach gets the edge
  and the two new `expose` names.
- Docs (D-6): `special_patterns_and_adaptations.md`, `adding_framework_guide.md`,
  `adding_validation_rules.md`, `security_guardrails.md`, the `TECH-084` design and
  `module_dependency_graph.md` name the new home. `subprocess_execution.md` names the file only, so
  it stays right. `TECH-079`'s design names files with line numbers from its own measurement day;
  left as measured.

**Tests**: `test_drift_analysis.py` (7) red first (no module); the handler test
`test_the_drift_handler_asks_no_model_itself` red first (the handler called `generate`).
`test_cli_drift.py`, `test_spend_brake_parks_run.py`, `test_drift.py` unchanged and green.

**Mutants**: B-FLOW-05 `drift-stop-is-a-failure` re-pointed to `explain_drift` and killed (2 tests);
FR-2 `findings-left-out-of-the-prompt` killed (4 tests). `stale_mutants.py`: 0 stale.

**Edge cases**: a finding with a newline, prompt-like text, or empty text; no findings; brake stop;
another error; no model at all (through the handler, `test_drift.py`).

**Red/blue (7.5)**
- R1 (LOW) the prompt now folds a multi-line finding onto one line; the model sees the same words.
  Intended (the plan's hostile bucket), not a user-visible output.
- R2 (LOW) the handler's `except Exception` around `llm_for` logs with a traceback, as the old
  single `try` did.
- R3 (LOW, fixed) the duplication gate matched the drift handler's import block against
  `standards.py`. The handler's imports of `explain_drift`, `llm_for` and `TaskType` moved from inside
  the method to module level (no hidden inline imports; no cycle, `tach check` passes); the no-model
  test patches `drift.llm_for`.
- Added in Phase 3: `test_no_model_for_the_analysis_is_reported_not_raised` (the handler's `llm_for`
  failure branch).

**Gate**: full suite 12068 passed, 9 skipped; `quick` 9/9; `cb` 17/17; `doc` 14/14; `tach check`
passes; 0 stale mutants.
