# Implementation Plan: Domain Logic Lives in the Flow Engine [SF-01: Validation orchestration home]
- **Feature ID**: TECH-082
- **Sub-Feature**: SF-01 — Validation orchestration home
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_sf01_implementation_plan.md
- **Status**: APPROVED (the user, 2026-11-03)

## Scope

Validation policy and the drift model call leave `core/flow` for the new module
`specweaver.assurance.validation.orchestration` (AD-1). FRs: **FR-1, FR-2**. NFRs carried:
NFR-1 (same behaviour), NFR-2 (boundaries hold), NFR-3 (old paths do not import), NFR-4 (mutants
re-pointed). Kind: `refactor`.

| Moves | From | To |
|---|---|---|
| validation policy | `core/flow/handlers/validation_hydrator.py` (379 lines) | `assurance/validation/orchestration/validation_hydrator.py` |
| pipeline choice | `core/flow/handlers/archetype_pipelines.py` (197) | `assurance/validation/orchestration/archetype_pipelines.py` |
| project boundary | `core/flow/engine/project_paths.py` (26) | `assurance/validation/orchestration/project_paths.py` (AD-4) |
| drift model call | `DriftCheckHandler._analyze_drift` (`core/flow/handlers/drift.py:152-180`) | `assurance/validation/orchestration/drift_analysis.py` |

File names stay the same: this SF moves code; names are SF-06's job.

## Decisions (Phase 4)

- **D-1 The new module under a pure parent** `[agreed 2026-11-03]`: settled by the design amendment
  (FR-15) and built in SF-08. `assurance/validation/orchestration/context.yaml` declares
  `widens` for `specweaver/sandbox` ("runs the QA, structure and protocol atoms") and
  `specweaver/infrastructure/llm` ("asks the model for the drift root cause"). `assurance/validation/io`
  and `assurance/validation` are siblings inside the parent's folder and need no widening;
  `core/config` lies inside the parent's `consumes`. `tests/unit/test_boundary_rule_holds.py` checks it.
- **D-2 `review.py:382` also uses `project_paths`**: recorded in the design's AD-4 (2026-11-03).
  `review.py` imports from the new home.

### D-3 The drift split

- `explain_drift(adapter, config, findings, file_path) -> str | None` in
  `orchestration/drift_analysis.py`: builds the prompt, calls `adapter.generate`, returns the text;
  `SpendLimitReachedError` → `None`; any other error → `"LLM analysis failed: <exc>"` with
  `logger.exception`.
- `DriftCheckHandler` calls `llm_for(context, TaskType.REVIEW)` inside its own `try`, so a missing
  model still yields `"LLM analysis failed: …"` as today (`test_drift.py:319` pins the text).
- `_load_plan`, the tree-sitter parse and `detect_drift` stay in the handler: they are not the
  model call, and FR-2 names only the model part.


### D-4 tach and manifest edges

| Module | Change |
|---|---|
| new `specweaver.assurance.validation.orchestration` | `depends_on`: `assurance.validation`, `assurance.validation.io`, `core.config`, `sandbox`, `infrastructure.llm`; `utility` `commons` needs no edge |
| `assurance.validation.interfaces` | + orchestration; − `core.flow.handlers` (no other user); manifest `core/flow` → `core/flow/engine` in `consumes` **and** in its `widens` key (`cli_drift.py` still uses the engine), else the guard reports a stale widening |
| `interfaces.api` | + orchestration (keeps `core.flow.handlers`: `pipelines.py`, `_llm.py` use the registry) |
| `core.flow.handlers` | + orchestration; keeps `assurance.validation.io` (`review.py`) and `sandbox` |
| `core.flow.engine` | keeps `sandbox` (`sandboxed_execution.py`, `session.py`, …) |

- The new module's `exposes` lists only the names `src/` imports from outside it (tach checks
  `src` only). The plan lists them at CB-1 from a grep, not from memory.
- No cycle: the new module imports nothing from `core/flow` (AD-3).
- NFR-2: tach gets an `[[interfaces]]` block for the new module whose `expose` equals the
  manifest's `exposes` (the same pairing `test_validation_context_exposes.py` pins for the parent).
- New test folders get an `__init__.py`, as their siblings under `tests/unit/assurance/validation/`
  and `tests/integration/assurance/validation/` have.


### D-5 Tests move, and 13 mutants are re-pointed

- Tests mirror `src` (`tests/CLAUDE.md`). Unit: `tests/unit/core/flow/test_validation_hydrator.py`,
  `tests/unit/core/flow/handlers/test_archetype_languages.py`,
  `tests/unit/core/flow/engine/test_project_paths.py` →
  `tests/unit/assurance/validation/orchestration/`. Integration:
  `tests/integration/core/flow/handlers/test_engine_paths_stay_inside.py`,
  `test_contract_discovery_stays_inside.py`, `test_one_archetype.py`,
  `test_archetype_spec_pipeline.py` → `tests/integration/assurance/validation/orchestration/`.
  Other tests only change their import line or `mock.patch` string
  (`test_validate_code_languages.py:41,78`).
- Mutants anchored in moved code: 13 of 14. C-VAL-02 (1), B-FLOW-01 (1), TECH-075 (5),
  TECH-077 (1), TECH-078 (1, `_test_file_for`), B-INTL-01 (3), B-FLOW-05 (1,
  `drift-stop-is-a-failure` → `explain_drift`). TECH-078's `DriftCheckHandler.execute` mutant
  stays: that code does not move. Each `file`, `symbol`, `scope` is edited, then
  `python scripts/_corpus.py --corpus <file> --refresh <derived id>` once per mutant.


### D-6 Which documents change

- Living documents: `docs/dev_guides/special_patterns_and_adaptations.md`, `subprocess_execution.md`,
  `adding_validation_rules.md`, `adding_framework_guide.md`,
  `docs/architecture/01_foundational_principles/security_guardrails.md`,
  `docs/architecture/02_bounded_contexts/domain_flow_engine.md`,
  `docs/architecture/03_system_topology/module_dependency_graph.md`; open designs `TECH-079`,
  `TECH-084`.
- Closed stories' documents keep the old paths (`finished-stories-immutable`).


### D-7 Out of scope here

- `archetype_pipelines.language_of` duplicates `commons.languages.language_of`, and its
  `LANGUAGE_SUFFIXES` alias stays. Both are `TECH-079`'s merge.


## Path List rows this SF owns

| Row | Interface first exists | Test |
|---|---|---|
| P-1 `sw check` → new home | CB-1 | existing `tests/integration/assurance/validation/test_rules_share_the_root.py`, re-imported; the guard below goes red first |
| P-2 `POST /check` → new home | CB-1 | existing API tests under `tests/integration/interfaces/api/` |
| P-3 handler → new home | CB-1 | `tests/e2e/capabilities/assurance/test_architecture_pipeline.py` |
| P-6 drift → `explain_drift` | CB-2 | `tests/integration/interfaces/cli/test_cli_drift.py` (seam: CLI → handler → function) |

## Commit Boundaries

### CB-1 (interior): validation policy in its new home — FR-1, NFR-2, NFR-3, NFR-4

**Red first** (run, watch fail, record the reason):

1. `tests/unit/assurance/validation/orchestration/test_validation_has_its_own_home.py`
   (`Proves: TECH-082 FR-1, TECH-082 NFR-3`):
   - an AST scan finds no import of `specweaver.core.flow.handlers` in any `.py` under
     `src/specweaver/assurance/` or in `interfaces/api/v1/validation.py`. Red today: `cli.py:139,290`,
     `validation.py:107`.
   - `importlib.import_module` on each old path raises `ModuleNotFoundError`. Red today: they exist.
   - each new path imports and names the moved public functions. Red today: no module.
   - 4 buckets: happy (new path imports), boundary (a lazy import inside a function is still found),
     degradation (a file that fails to parse is named, not skipped), hostile (an aliased
     `import specweaver.core.flow.handlers as h` is still found).

**Green**, in this order (each step keeps `tach check` the last thing to fix):

1. Create `src/specweaver/assurance/validation/orchestration/context.yaml` (`archetype:
   orchestrator`, `consumes` as D-4, `widens` as D-1, `exposes`).
2. `git mv` the three files; fix their own imports (`archetype_pipelines.relative_to_root` →
   the new `project_paths`).
3. Re-point every importer: `assurance/validation/interfaces/cli.py:139,290`,
   `interfaces/api/v1/validation.py:107`, `interfaces/api/v1/paths.py:14`,
   `core/flow/handlers/validation.py:204,305,310,355`, `lint_fix.py:70`, `qa_targets.py:27,137`,
   `review.py:382`.
4. Update the module docstring of `validation_hydrator.py` (it says it lives in `core.flow`).
5. `tach.toml` and the touched `context.yaml` files as D-4.
6. Move the tests (D-5) and fix imports and `mock.patch` strings.
7. Re-point the 12 mutants in moved files of this CB; refresh each.

**Done when**: the guard is green; `tach check` and `tests/unit/test_boundary_rule_holds.py` pass; `stale_mutants.py` reports none stale;
the mutant below is killed.

**Mutant** (into `TECH-082_mutants.json`, FR-1): in `cli.py`, put back
`from specweaver.core.flow.handlers.validation_hydrator import execute_validation_flow` beside the
new import → the guard goes red.

### CB-2 (closes SF-01, HITL): the drift model call leaves the handler — FR-2

**Red first**:

1. `tests/unit/assurance/validation/orchestration/test_drift_analysis.py`
   (`Proves: TECH-082 FR-2`), red today (no module):
   - happy: a fake adapter's text comes back; the prompt names the file and every finding.
   - boundary: no findings still gives a prompt and a call.
   - degradation: `SpendLimitReachedError` → `None`; another error → `"LLM analysis failed: …"`.
   - hostile: a finding description with a newline or prompt-like text is passed as data, one line
     per finding, never dropped.
2. In `test_drift_handler.py`, the `_analyze_drift` test moves to the function; the handler test
   asserts `DriftCheckHandler` has no method that calls `generate` (red today).

**Green**: write `drift_analysis.py`; `DriftCheckHandler._run_drift_detect` calls `llm_for` in a
`try` and then `explain_drift`; delete `_analyze_drift`. Re-point the B-FLOW-05 mutant. Update the
documents of D-6.

**Done when**: `test_cli_drift.py` and `test_spend_brake_parks_run.py` pass unchanged; the re-pointed
B-FLOW-05 mutant is killed; this mutant is killed: in `explain_drift`, delete the
`for f in findings:` prompt line → the unit test goes red.

**Gate**: `python scripts/tests.py cb TECH-082 --kind refactor`, then `specweaver-pre-commit`, stage,
**STOP** for the user.

## Research Notes

- `execute_validation_flow(pipeline, spec_text, spec_path=None, *, project_root=None,
  dal_level=None, context=None, sandbox_settings=None, language=None) -> list[Any]`
  (`validation_hydrator.py:321`).
- `project_file(project_root: Path, relative: str) -> Path`, raises `ProjectPathError(ValueError)`
  (`project_paths.py:20`); it wraps `sandbox.security.WorkspaceBoundary`.
- `archetype_pipelines` lazy-imports `core.config.archetype_resolver`, `core.config.profiles`,
  `assurance.validation.io.pipeline_loader`, `sandbox.code_structure.core.atom`,
  `sandbox.evaluator_schemas`; module-level only `commons.languages`.
- `validation_hydrator` lazy-imports `sandbox.language.core.runner_factory.qa_atom`,
  `sandbox.code_structure.core.atom`, `sandbox.base`, `sandbox.protocol.core.atom`,
  `sandbox.security`, `assurance.validation.project_root`, `assurance.validation.executor`.
- `_analyze_drift` today: builds the prompt from `report.findings`, `llm_for(context,
  TaskType.REVIEW)`, `adapter.generate(messages, config)`; all inside one `try`
  (`drift.py:152-180`).
- tach: `exact = true`, `root_module = "forbid"`, `ignore_type_checking_imports = false`,
  `forbid_circular_dependencies = true`; `commons` is `utility = true`.
- Mutant scopes naming moved tests: TECH-078 (`test_archetype_languages.py`), TECH-075
  (`test_contract_discovery_stays_inside.py`, `test_project_paths.py`,
  `test_engine_paths_stay_inside.py`, `test_archetype_spec_pipeline.py`), TECH-077
  (`test_one_archetype.py`), B-INTL-01 (`test_archetype_languages.py`).

## Red/Blue (Phase 5), 2 cycles

- R1 (MEDIUM) The manifest change of `validation/interfaces` (`core/flow` → `core/flow/engine`)
  would leave its `widens` key on `core/flow`, which the SF-08 guard reports as stale. Fixed: D-4
  changes both.
- R2 (MEDIUM) NFR-2 asks for `exposes` equal to tach's interfaces; the plan named no tach block.
  Fixed: D-4.
- R3 (LOW) New test folders need `__init__.py` like their siblings. Fixed: D-4.
- R4 (LOW) `interfaces/api/v1/paths.py` imports `project_paths` at module level, and that module
  imports `sandbox.security` at module level. The API manifest forbids `sandbox/*`; the import is
  transitive, as it was through `core/flow/engine`. No change.
- Cycle 2: challenged D-1 (does `core/flow/handlers` need a widening to use the new module?) — no:
  it lies inside `core/flow`'s `assurance/validation`. Challenged the API edge — the API's parent is
  the root, so the new module is a sibling. No new finding above LOW.

## Backlog

None.
