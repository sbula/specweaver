# Walkthrough: TECH-082 SF-02 — Implementation home

## CB-1: task files, frameworks and contracts in their new home (FR-3, NFR-2, NFR-3, NFR-4)

**What changed**
- `task_files.py`, `frameworks.py` (from `core/flow/engine`) and `contract_renderers.py` (from
  `core/flow/handlers`) moved by `git mv` to `workflows/implementation`. No shim (AD-6).
- `task_files_for` no longer detects: its `language` is a `str`. The new
  `core/flow/engine/run_language.py` holds `run_language(project_root, language)` (the named
  language, else `detect_language`) and `run_task_files(context)` (D-6). The 9 callers that could
  pass `None` use them: 6 handler calls, `isolation.derive_allowed_paths`, `POST /implement`,
  `sw implement`.
- `workflows/implementation` declares every name `src/` imports from it, and tach checks the list
  with a new `[[interfaces]]` block (D-8). Probed: dropping `task_files.task_brief` from it makes
  `tach check` fail on `generation.py:163`.
- tach edges: `workflows.implementation → core.config` (`frameworks.py`), `interfaces.api` and
  `workflows.implementation.interfaces → workflows.implementation`. The `sw implement` manifest
  consumes its parent; its `core/flow` widening now names the run's language.
- 5 unit test files moved to `tests/unit/workflows/implementation/`; the "None detects" case moved to
  `test_run_language.py`. `test_logging_rollout.py` lists `contract_renderers` under workflows.
- Docs: `language_support_guide.md` step 7; `TECH-079`'s design names `run_language` as the one place
  to change.
- Mutants: 10 re-pointed (B-FLOW-01 1, TECH-078 1, D-INTL-08 7, TECH-081 1). 3 anchors changed with
  the code and were re-anchored on the new line (`allow-list-stays-python`, `contract-detects-again`,
  `python-tests-looked-for-in-src`); `flow-uses-a-private-detector` now anchors in `run_language`.
  All 4 still object. Every mutant whose symbol changed was refreshed (25 in all). 0 stale.

**Tests**: guard `test_implementation_has_its_own_home.py` (11), red first with 7 failures (old paths
imported, new paths missing). `test_run_language.py` (12), red first (no module).
`tests/integration/core/flow/engine/test_run_language_agrees_with_qa.py` (8): with no language
named, the task files and the QA runner take the same language for each of the 5 manifests (gap found
in Phase 2: both turn "no language" into one).

**Mutant** (FR-3, `generation-skips-the-run-language`): generation passes the raw setting to
`task_files_for` → the integration and e2e tests of 4 languages object.

**Coverage matrix**

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `run_language` | ✅ | ✅ `test_run_language_agrees_with_qa.py` | ✅ `test_implement_in_every_language_e2e.py` |
| `run_task_files` | ✅ | ✅ `test_task_files_agree.py`, `test_step_files_java.py` | ✅ same |
| moved functions | ✅ (moved tests) | ✅ `test_one_language_table.py` | ✅ same |
| the import guard | ✅ | — | — |

**Red/blue (7.5)**, 2 cycles
- R1 (MEDIUM, accepted) the duplication baseline was re-frozen: 4 clones in `contract_renderers.py`
  were already frozen and only got new keys from the move; 1 new pair is two `TYPE_CHECKING` import
  blocks (`generation.py`, `review.py`) that ruff sorts alike. Imports cannot be extracted.
- R2 (LOW, accepted) a caller that still passes `None` to `task_files_for` gets the Python layout
  silently; mypy in the `cb` gate refuses it, and no caller does.
- R3 (LOW, fixed) `task_files_for` kept a `chosen = language` alias; removed.
- Cycle 2: challenged D-6 (does the API now reach `sandbox`?) — only through the engine, whose edge
  exists; the boundary rule judges direct imports. No new finding above LOW.

## CB-2: the lint repair leaves the handler (FR-4)

**What changed**
- New `workflows/implementation/lint_repair.py`:
  `repair_lint(adapter, config, code, lint_errors, language, project_dir) -> str` builds the same
  prompt, asks the model, strips the fence and puts back a dropped lineage tag. Adapter errors
  propagate; the handler's `_model_fix` still turns them into an ERROR result.
- `LintFixHandler._llm_fix` is now thin: it reads the file, gets the language and the model, calls
  `repair_lint`, writes the result and logs the lineage. The loop stays in the handler (FR-4).
- `tag_content` moved from `core/flow/handlers/artifact_lineage.py` to `commons/lineage.py` (D-7);
  `generation.py`, `decomposition_artifacts.py` and `artifact_lineage.py` import it from there. Its
  4 tests moved to `tests/unit/commons/test_lineage.py`.
- `repair_lint` is in the module's `exposes` and tach's `[[interfaces]]` block (D-8).
- Mutants: the 4 D-INTL-08 FR-6 lint mutants re-pointed to `repair_lint`; 2 anchors changed with
  the code and keep their meaning (tag hard-coded to Python; fence kept). All 4 object. 1 more
  refreshed (`plan-not-saved`, its function changed only by an import). 0 stale.
- Docs: `module_dependency_graph.md` has a paragraph on implementation work; the design's guides
  row says SF-02 is done.

**Tests**: `test_lint_repair.py` (8), red first (no module). The handler test
`test_the_handler_never_calls_the_model_itself`, red first. The guard now also scans
`lint_repair.py`, red first (no file). `tests/unit/commons/test_lineage.py` red first (no
`tag_content` there). Phase 2 found no test where the real linter, the handler and the repair work
together with a model fix: 2 new tests in `tests/integration/sandbox/test_lint_fix.py` (the fix is
written, keeps its tag and passes the re-lint; a model that fixes nothing exhausts the loop).

**Mutants** (FR-4): the error lines left out of the prompt → the unit tests object; the handler
writes the old text back → the new integration test objects.

**Coverage matrix**

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `repair_lint` | ✅ | ✅ `test_lint_fix.py` (real ruff) | ✅ `test_implement_in_every_language_e2e.py` |
| `LintFixHandler._llm_fix` | ✅ | ✅ same | ✅ same |
| `tag_content` | ✅ | ✅ through the handlers | — |

**Red/blue (7.5)**, 2 cycles
- R1 (LOW) the handler reads the lineage id after the write; it reads it from the text it held
  before the call, so the id is the same. No change.
- R2 (LOW) `llm_for` now runs after the file is read, not after the prompt is built; both are inside
  `_model_fix`'s `try`, so a missing model still gives the same ERROR. No change.
- Cycle 2: no new finding above LOW.
