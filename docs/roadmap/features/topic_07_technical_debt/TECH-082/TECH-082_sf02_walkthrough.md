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
