# Implementation Plan: Domain Logic Lives in the Flow Engine [SF-02: Implementation home]
- **Feature ID**: TECH-082
- **Sub-Feature**: SF-02 — Implementation home
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_sf02_implementation_plan.md
- **Status**: APPROVED (the user, 2026-11-03)

## Scope

Task files, framework choice, contract rendering and the lint repair leave `core/flow` for
`specweaver.workflows.implementation`. FRs: **FR-3, FR-4**. NFRs carried: NFR-1 (same behaviour),
NFR-2 (boundaries hold), NFR-3 (old paths do not import), NFR-4 (mutants re-pointed). Kind: `refactor`.

| Moves | From | To |
|---|---|---|
| task files | `core/flow/engine/task_files.py` (227 lines) | `workflows/implementation/task_files.py` |
| framework choice | `core/flow/engine/frameworks.py` (116) | `workflows/implementation/frameworks.py` |
| contract rendering | `core/flow/handlers/contract_renderers.py` (533) | `workflows/implementation/contract_renderers.py` |
| lint repair (prompt, model call, fence strip, tag restore) | `LintFixHandler._llm_fix` (`lint_fix.py:295-361`) | `workflows/implementation/lint_repair.py` |

File names stay: names are SF-06's job. `LintFixHandler` keeps the loop, the file write and the
lineage log (FR-4).

## Decisions (Phase 4, the user 2026-11-03)

- **D-6 One language helper in the engine** `[agreed 2026-11-03]` (F-1 A): new
  `core/flow/engine/run_language.py`, `run_language(project_root, language) -> str` = the named
  language, else `detect_language(project_root)`. The API forbids `sandbox/*` and the `sw implement`
  CLI has no `sandbox` edge; both already depend on the engine, which already depends on `sandbox`.
  The 9 callers that can pass `None` use it: `generation.py:135,404,512`, `lint_fix.py:318`,
  `qa_targets.py:82,89`, `engine/isolation.py:58`, `api/v1/implement.py:89`,
  `implementation/interfaces/cli.py:176`. AD-5 holds: detection stays out of the moved code; the
  callers ask the engine for it. `TECH-079` then has one place to change.
- **D-7 `tag_content` moves to `commons/lineage.py`** `[agreed 2026-11-03]` (F-2 A), beside
  `extract_artifact_uuid` and `wrap_artifact_tag`. Its users (`generation.py`,
  `decomposition_artifacts.py`, `artifact_lineage.py`, `lint_repair.py`) import it from there. Its
  tests move from `tests/unit/core/flow/handlers/test_artifact_lineage.py` to
  `tests/unit/commons/test_lineage.py`. No mutant anchors it.
- **D-8 `workflows/implementation` declares what it exposes, and tach checks it**
  `[agreed 2026-11-03]` (F-3 A): the manifest's `exposes` lists every name `src/` imports from
  outside the module, from a grep at CB-1, not from memory. Expected: `Generator`, `strip_fences`,
  `generation_prompt` (generator); `language_guide`, `LanguageGuide` (languages); `TaskFiles`,
  `task_files_for`, `task_brief`; `project_framework`, `FrameworkChoice`; the
  `contract_renderers` names the handlers use; `repair_lint` (CB-2). tach gets the matching
  `[[interfaces]]` block (TYPE_CHECKING imports count). `test_manifests_are_complete.py` checks each
  name exists.

## Decisions (no user choice needed)

### D-1 The lint split

- `async def repair_lint(adapter, config, code, lint_errors, language, project_dir) -> str` in
  `workflows/implementation/lint_repair.py`: reads the guide's `name` (`language_guide(language,
  project_dir)`), builds the same prompt, adds the keep-the-tag line when the code carries a
  lineage id, calls `adapter.generate`, strips fences, restores the tag, returns the text. Errors
  propagate: `_model_fix` already turns them into an ERROR result (`lint_fix.py:220-230`).
- The handler keeps: reading the file, `llm_for(context, TaskType.CHECK)`, the write, the lineage
  log with `config.model`.
- The handler still gets `language` from `task_files_for(...).language`, not from `run_language`:
  `task_files_for` maps a language outside its table to `python`, and NFR-1 keeps that.

### D-2 tach and manifest edges

| Module | Change |
|---|---|
| `specweaver.workflows.implementation` | + `core.config` (`frameworks.py` uses `ArchetypeResolver`); the manifest already consumes `core/config`. No cycle: `core.config` depends on nothing. |
| `specweaver.core.flow.engine` | keeps `workflows.implementation` (`isolation.py`) and `sandbox` (`run_language`) |
| `specweaver.core.flow.handlers` | keeps `workflows.implementation`; drops nothing (other handlers still use `sandbox`) |
| `specweaver.interfaces.api` | + `workflows.implementation` (the manifest already consumes it; `implement.py` imports `TaskFiles` / `task_files_for`) |
| `specweaver.workflows.implementation.interfaces` | + `workflows.implementation` |

- The moved code imports neither `sandbox/*` nor `core/flow` (FR-3, AD-3). The guard below checks both.
- `tests/unit/test_boundary_rule_holds.py` re-checks the manifests (FR-21).

### D-3 Tests move, and 14 mutants are re-pointed

- Unit tests move to `tests/unit/workflows/implementation/`: `core/flow/engine/test_task_files.py`,
  `test_task_brief.py`, `test_frameworks.py`, `core/flow/handlers/test_contract_renderers.py`,
  `test_contract_methods.py`. The `None`-detects case (`test_task_files.py:154`) moves to a new
  `tests/unit/core/flow/engine/test_run_language.py`.
- Import-only edits: `tests/integration/test_one_language_table.py:50`,
  `tests/unit/test_logging_rollout.py:333,364` (`contract_renderers` leaves the handlers list).
- The `_llm_fix` tests in `test_lint_fix_handler.py` (prompt, fence, tag) keep running through the
  handler (they prove the seam); new unit tests prove the function alone.
- Mutants in moved code: B-FLOW-01 (1, `_method_at`), TECH-078 (1), D-INTL-08 (3 task files,
  4 frameworks, 4 `_llm_fix` → `repair_lint`), TECH-081 (1, `flow-uses-a-private-detector` → its
  anchor moves to `run_language`). Each `file`, `symbol`, `scope` is edited, then
  `python scripts/_corpus.py --corpus <file> --refresh <derived id>`.

### D-4 Which documents change

- Living: `docs/dev_guides/language_support_guide.md`,
  `docs/architecture/03_system_topology/module_dependency_graph.md`, open design `TECH-079`.
- Closed stories' documents keep the old paths (`finished-stories-immutable`).

### D-5 Out of scope

- One detection for the whole product: `TECH-079`. This SF only moves the call out of the moved code.

## Path List rows this SF owns

| Row | Interface first exists | Test |
|---|---|---|
| P-4 `sw implement` → generation → new home | CB-1 | existing `tests/integration/core/flow/handlers/test_step_files_java.py`, `test_plan_names_the_language.py`, `tests/integration/test_one_language_table.py`, re-imported; the guard goes red first |
| P-5 `lint_fix` step → handler → `repair_lint` → model | CB-2 | existing `tests/integration/sandbox/test_lint_fix.py` and `test_lint_step_tool_did_not_run.py` pass unchanged |

## Commit Boundaries

### CB-1 (interior): task files, frameworks and contracts in their new home — FR-3, NFR-2..4

**Red first**:

1. `tests/unit/workflows/implementation/test_implementation_has_its_own_home.py`
   (`Proves: TECH-082 FR-3, TECH-082 NFR-3`):
   - each old path (`core.flow.engine.task_files`, `core.flow.engine.frameworks`,
     `core.flow.handlers.contract_renderers`) raises `ModuleNotFoundError`. Red: they exist.
   - each new path names its public functions. Red: no module.
   - an AST scan of the three moved files finds no import of `specweaver.sandbox` or
     `specweaver.core.flow`. Red: no files yet (then `task_files.py:60` would fail it).
   - 4 buckets: happy (new paths import), boundary (a lazy import is found), degradation (an
     unparsable file is named), hostile (an aliased import is found).
2. `tests/unit/core/flow/engine/test_run_language.py` (`Proves: TECH-082 FR-3`): a named language
   is returned as is; `None` in a Cargo project → `rust`; `None` in an empty folder → the detector's
   default. Red: no module.

**Green**: `run_language` (D-6); `git mv` the three files; drop the detector from
`task_files_for` (its `language` becomes `str`); re-point the 9 callers to `run_language` (D-6); tach and
manifests (D-2, D-8); move the tests (D-3); re-point 10 mutants.

**Done when**: the guard and `test_run_language.py` are green; `tach check` and
`test_boundary_rule_holds.py` pass; `stale_mutants.py` reports none stale; this mutant is killed:
in `generation.py:135`, pass `context.isolation.language` straight to `task_files_for` (no
`run_language`) → a test with no configured language goes red. If it survives, add an integration
test first: the generation handler in a Cargo project with no `[implement] language` writes
`src/<stem>.rs`.

### CB-2 (closes SF-02, HITL): the lint repair leaves the handler — FR-4

**Red first**:

1. `tests/unit/workflows/implementation/test_lint_repair.py` (`Proves: TECH-082 FR-4`), red (no module):
   - happy: the fake adapter's fenced text comes back unfenced; the prompt names the guide's
     language name and every error.
   - boundary: no lint errors still asks; code without a lineage id gets no tag line.
   - degradation: an adapter error propagates (the handler turns it into ERROR).
   - hostile: the model drops the tag → the tag is put back; the model returns a different tag →
     kept, not doubled.
2. In `test_lint_fix_handler.py`: the handler has no `.generate(` call (red today).
3. `tag_content` tests move with it to `tests/unit/commons/test_lineage.py` (D-7).
4. The CB-1 guard's AST scan adds `lint_repair.py` (no `sandbox`, no `core.flow` import).

**Green**: `tag_content` to `commons/lineage.py`; write `lint_repair.py`; `_llm_fix` becomes a thin
method (read, `llm_for`, `repair_lint`, write, log). Re-point the 4 `_llm_fix` mutants. Add `repair_lint` to `exposes` and the tach block (D-8). Docs (D-4).

**Done when**: `tests/integration/sandbox/test_lint_fix.py` passes unchanged; the re-pointed
mutants are killed; this mutant is killed: in `repair_lint`, drop the error lines from the prompt →
the unit test goes red.

**Gate**: `python scripts/tests.py cb TECH-082 --kind refactor`, then `specweaver-pre-commit`,
stage, **STOP** for the user.

## Research Notes

- `task_files_for(project_root: Path, spec_path: Path, language: str | None) -> TaskFiles`
  (`task_files.py:57`); imports `commons.spec_names`, `commons.languages` (utility, no edge).
- `project_framework(project_root, code_path, language) -> FrameworkChoice | None`
  (`frameworks.py:43`); imports `workflows.implementation.languages` (same module after the move)
  and, lazily, `core.config.archetype_resolver.ArchetypeResolver`.
- `contract_renderers.py` imports only `logging`, `re`, `dataclasses`: no edge needed.
- tach today: `workflows.implementation` depends only on `infrastructure.llm`; `core.flow.engine`
  already depends on `workflows.implementation` and `sandbox`; `interfaces.api` depends on
  `core.flow.engine`, not on `workflows.implementation`.
- `RunContext.isolation.language` is `str | None`, "None lets its manifests decide"
  (`run_context.py:64-65`).
- `task_files_for` maps any language outside python/java/kotlin/typescript/rust to `python`
  (`task_files.py:74`); `detect_language` can name more. D-1 keeps the handler on
  `task_files_for(...).language` for that reason.
- `mock.patch` strings on `LintFixHandler.execute` (`test_cli_implement.py:115,227`,
  `e2e/conftest.py:93`, `test_drafter_loop_e2e.py:134`) stay valid: the handler does not move.

## Red/Blue (Phase 5), 2 cycles

- R1 (MEDIUM) The CB-1 mutant could survive: no test may run generation with no configured
  language in a non-Python project. Fixed: CB-1 adds that integration test when the mutant survives.
- R2 (MEDIUM) The guard scanned only the three CB-1 files, so `lint_repair.py` could import
  `core.flow` unseen. Fixed: CB-2 adds it to the scan.
- R3 (LOW) `run_language` returns any of the 5 detector languages, while `task_files_for` maps an
  unknown configured language to `python`. Not a change: the handler keeps
  `task_files_for(...).language` (D-1); `detect_language` names only the 5 (`detect.py:44`).
- R4 (LOW) A tach `[[interfaces]]` block counts TYPE_CHECKING imports; `generation.py:29,31,35`
  import `FrameworkChoice`, `TaskFiles`, `LanguageGuide` that way. Covered: D-8 lists them.
- Cycle 2: challenged D-6 (does the API gain a hidden `sandbox` path?) — the API imports only the
  engine; the boundary rule judges direct imports, and the engine's `sandbox` edge already exists.
  Challenged D-7 (is `commons` the right home?) — `commons/lineage.py` already holds the two
  functions `tag_content` is built from; it stays pure. No new finding above LOW.

## Backlog
