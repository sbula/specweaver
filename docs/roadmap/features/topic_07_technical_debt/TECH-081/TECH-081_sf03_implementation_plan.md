# Implementation Plan: The Layer Check Reports Clean While the Layers Are Broken [SF-03: The sandbox sits below the workflows]
- **Feature ID**: TECH-081
- **Sub-Feature**: SF-03 — The sandbox sits below the workflows
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_sf03_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-9 (`commons` depends on nothing and reads no files) and FR-10 (`sandbox` imports nothing from
`workflows` or `core.flow`), with AD-5 (scenario
models to `commons`), AD-6 (evaluator-schema loader to `sandbox`), AD-14 (a Protocol in
`security.py`). Kind `refactor`: no command, option or output changes (NFR-1). Four `deprecated`
edges and their ledger rows go.

## Research Notes

Read 2026-10-28.

- **`commons` file reading** (FR-9): `prepare_plan.py` (`detect_toolchain` `:133`, `plan_for`
  `:181`, `_plan_for_other` `:255`) checks and reads manifests and lockfiles; `tooling_sources.py`
  (`declared_pytest` `:60`, `_read` `:69`, `_from_tox` `:109`) reads requirements files and
  `tox.ini`. `prepare_plan` imports `tooling_sources`; nothing else in `commons` uses either.
- **Their users**: `sandbox/execution/sandbox_image.py:21`, `container_executor.py:23,39`
  (same module); `core/flow/handlers/dual_pipeline.py:33` (`core.flow → sandbox` is allowed);
  `interfaces/cli/routers/sandbox_router.py:23` (`plan_for`), registered in
  `interfaces/cli/main.py:127-129`. Tests: `tests/unit/commons/test_prepare_plan.py`,
  `test_prepare_plan_languages.py`, `test_tooling_sources.py`,
  `tests/unit/sandbox/execution/test_container_executor_prepare.py`,
  `tests/integration/sandbox/execution/test_container_executor_integration.py`, the e2e
  `test_preflight_reports_the_prepare_plan_e2e.py`.
- **Scenario models** (`workflows/scenarios/scenario_models.py`, 71 lines) import only pydantic:
  safe in `commons`. Users: the 5 converters in `sandbox/language/core/*/scenario_converter.py`
  (type-only), `workflows/scenarios/scenario_generator.py:19`, `core/flow/handlers/scenario.py:175`.
- **The Python converter** is split: `sandbox/language/core/python/scenario_converter.py:40`
  imports `ScenarioConverter` from `workflows/scenarios/scenario_converter.py` (299 lines, pure),
  lazily, "to break a circular import". No `src` caller uses `ScenarioConverter` directly; five test
  files do.
- **Evaluator loader** (`workflows/evaluators/loader.py`, 86 lines) uses
  `core.config.settings.deep_merge_dict` and reads the YAML as a package resource
  (`importlib.resources.files("specweaver.workflows.evaluators.frameworks")`, a string tach does not
  see). Users: `sandbox/dispatcher.py:234`, `core/flow/handlers/archetype_pipelines.py:114,164`.
- **`security.py:22`** imports `RunContext` under `TYPE_CHECKING` for `from_run_context` (`:153`),
  which reads `context.project_path` and `context.graph.api_contract_paths`. One caller:
  `core/flow/handlers/review.py:52`.
- **tach**: `specweaver.sandbox` has an `[[interfaces]]` list (`tach.toml:203-205`); a new import
  of a sandbox name from another module must be exposed there. `commons` is `utility`,
  `depends_on = []`.
- **The refactor gate** (`scripts/_refactor_diff_safety.py:313`) accepts a staged test file whose
  diff is a pure addition or a path-only change; an untracked file has no diff and blocks. Moved
  tests go with `git mv`, then their imports change.
- **`test_tach_architectural_boundaries`** (`tests/unit/test_architecture.py:38`) runs `tach check`
  in the suite, so a mutant that re-adds a removed import fails a test.
- **Corpora pointing at moved files**: `TECH-031_mutants.json` (`prepare_plan.py`,
  `tooling_sources.py` and their tests), `B-FLOW-01_mutants.json` (`scenario_converter.py` and the
  scenario tests). Re-pointed in the same commit (`.tmp/stale.py`).
- **Docs**: `docs/dev_guides/language_support_guide.md:61,83`,
  `docs/architecture/05_delivery_mechanisms/cli_architecture.md:26`.

## Approach (pseudocode, ordered)

**CB-1 — `commons` is pure (FR-9)**
1. Test first (red): `tests/unit/test_pure_modules_do_no_io.py` — for each module in a short list
   (today: `commons`), parse every file and fail on file or process calls (`open`, `.read_text`,
   `.read_bytes`, `.write_*`, `.is_file`, `.exists`, `.is_dir`, `.iterdir`, `.glob`, `.rglob`;
   imports of `subprocess`, `shutil`, `os`). Red: `prepare_plan.py`, `tooling_sources.py`. The list
   is a constant; SF-07 adds `assurance/validation`.
2. `git mv` both files to `workspace/project/`; fix the imports in `src` and the moved tests
   (`tests/unit/commons/test_{prepare_plan,prepare_plan_languages,tooling_sources}.py` →
   `tests/unit/workspace/project/`). `tach.toml`: `sandbox` and `core.flow` gain the plain edge to
   `workspace.project`; its interfaces expose `prepare_plan`. The router stays in the shell
   (AD-4 dropped `[agreed 2026-10-28]`: `TECH-002` FR-6 bars `interfaces/` from the sandbox).
3. Manifests: `commons` → `pure-logic`; `sandbox`, `core/flow` consume `workspace/project`.
4. Re-point the `TECH-031` corpus; fix the router's docstring.
5. Mutant `commons-reads-again`; pre-commit; commit.

**CB-2 — the sandbox imports no workflow (FR-10, AD-5, AD-6, AD-14)** — closes SF-03
6. Red first: delete the 4 `deprecated` edges (`core.flow → workflows.evaluators`,
   `sandbox → workflows.scenarios`, `sandbox → workflows.evaluators`, `sandbox → core.flow`) from
   `tach.toml` and their ledger rows. `test_tach_architectural_boundaries` goes red.
7. AD-5: `git mv workflows/scenarios/scenario_models.py commons/scenario_models.py`; fix the 8 `src`
   imports and the tests; `commons` exposes `ScenarioDefinition`, `ScenarioSet`; `test_scenario_models.py`
   moves to `tests/unit/commons/`.
8. The Python converter: `ScenarioConverter` (class name kept, so tests change only imports) moves
   into `sandbox/language/core/python/scenario_converter.py`; `PythonScenarioConverter.convert`
   calls it directly (the lazy import and the back-compat note go); the old file is deleted
   (NFR-3). Its tests move to mirror the new path.
9. AD-6: `git mv workflows/evaluators/loader.py sandbox/evaluator_schemas.py`; the YAML stays;
   `dispatcher.py` and `archetype_pipelines.py` import the new path; expose `evaluator_schemas` in the
   sandbox interfaces. `workflows/evaluators` keeps its `frameworks/` data: manifest
   `archetype: data`, no `consumes`; its tach module keeps no `depends_on`.
10. AD-14: `security.py` defines a Protocol (`project_path`, `graph.api_contract_paths`, as read-only
    properties) and types `from_run_context` with it; the `core.flow` import goes.
11. Manifests: `sandbox` loses its owed-edge comment; `core/flow` and `workflows/scenarios`
    consumes stay true (FR-4 test). Re-point `B-FLOW-01` corpus; update
    `language_support_guide.md:61,83`.

## Test Plan

| Tier | Test | Proves | Red first because |
|---|---|---|---|
| unit | `test_pure_modules_do_no_io.py`: `commons` makes no file or process call | FR-9 | `prepare_plan.py`, `tooling_sources.py` read files |
| arch (in suite) | `test_tach_architectural_boundaries`: no `sandbox → workflows/core.flow`, no `core.flow → workflows.evaluators` | FR-10 | the 4 edges are removed before the moves |
| unit | `test_tach_sees_every_module`: deprecated edges equal the ledger rows | FR-3 (kept) | — (both shrink together) |
| all | the moved tests, unchanged except imports | NFR-1 | — |

Mutants (each must turn a test red):
- `commons-reads-again`: add `Path(__file__).read_text()` to `commons/json.py` → purity test.
- `sandbox-imports-workflows`: a sandbox converter imports `ScenarioSet` from `workflows.scenarios` again → tach test (after the old file is gone, from `workflows.scenarios.scenario_generator`).
- `flow-imports-evaluators`: `archetype_pipelines.py` imports from `specweaver.workflows.evaluators` → tach test.
- `security-types-runcontext`: `security.py` imports `RunContext` under `TYPE_CHECKING` → tach test (FR-2 counts it).

## Commit Boundaries

| CB | Holds | Done when |
|---|---|---|
| CB-1 | steps 1–5 | full suite green; `commons-reads-again` killed; commit |
| CB-2 | steps 6–11 | full suite green; three FR-10 mutants killed; 4 edges and 4 ledger rows gone; stage and stop (closes SF-03) |

## Documentation

`language_support_guide.md`, the router docstring. The design's tracker and handoff.

## Architecture Verification (Phase 3)

- `workspace/project` is an `adapter` for project discovery that already reads files: the readers
  fit. `commons` becomes `pure-logic` with nothing left that does I/O. `sandbox → workspace.project`
  makes no loop (its reach: `assurance.graph`, `graph`, `workspace.*`; measured 2026-10-28).
- `sandbox/evaluator_schemas.py` reads package resources and project YAML: `sandbox` is an
  `orchestrator` that consumes `core/config` — allowed.
- Scenario models in `commons`: pydantic data, no imports from `specweaver`.
- No `deprecated` edge is added (NFR-2); four are removed.

## Audit (Phase 2) — settled

❓ **Q1 — move the two readers whole, or split them.** The design says "the file-reading parts"
move. In both files the pure parts (manifest-text parsing, tox-line sorting) are private helpers
with no other user.
- **A:** move both files whole (to `sandbox/execution/`, later `workspace/project/`, see below); one home, tests move unchanged.
- **B:** split: pure parsers stay in `commons`, readers move; two files each, tests split.

❓ **Q2 — a guard test in a `refactor` sub-feature.** FR-9's "reads no files" has no check today;
tach does not see I/O. A new test file needs kind `tooling` for CB-1 (CB-2 stays `refactor`).
- **A:** add `test_pure_modules_do_no_io.py`; CB-1 runs `--kind tooling`; the design's kind line says so.
- **B:** no new test; FR-9 rests on review and the `pure-logic` label.

The user chose A for both `[agreed 2026-10-28]`: the readers move whole; CB-1 adds the purity test
and runs `--kind tooling`.

## Consistency (Phase 5)

- Red/Blue, 2 cycles:
  - R1 (MEDIUM) the purity test matches call names, so an aliased call passes. Blue: it guards the
    shape that existed (direct calls); the `pure-logic` label and review cover the rest.
  - R2 (MEDIUM) `os` is banned, but `os.path.join` is pure. Blue: `commons` imports no `os` today; a
    future need is a visible test change, not a silent one.
  - R3 (MEDIUM) `workflows/evaluators` keeps a tach module with no Python. Blue: tach accepts a
    directory; removing the module is SF-08 cleanup if it warns.
  - R4 (LOW) `git mv` of a test plus an import edit may still trip the refactor gate in CB-2. Blue:
    stage first; if it blocks, CB-2 also runs `tooling` and the walkthrough says why.
  - Cycle 2: no new finding.

**Found in dev, 2026-10-28:** AD-4 would make `interfaces/cli/main.py` import the sandbox, which
`tests/unit/test_layer_import_isolation.py` (`TECH-002` FR-6) forbids. The user chose B
`[agreed 2026-10-28]`: the readers go to `workspace/project`, the router stays.
