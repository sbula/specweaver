# Implementation Plan: Paths From Outside Can Leave the Project [SF-02: API paths stay in the project]
- **Feature ID**: TECH-075
- **Sub-Feature**: SF-02 — API paths stay in the project
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-075/TECH-075_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-075/TECH-075_sf02_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-2 (pipeline run `spec`), FR-3 (`resolve_file_in_project`), FR-7 (stored project paths), FR-10
(pipeline name). Kind `bugfix`. Depends on SF-01 (committed `b6dfede6`). NFR-1, NFR-2, NFR-3, NFR-5
apply.

## Research Notes

- **Measured 2026-10-22, after SF-01.**
  - `POST /pipelines/{name}/run` (`interfaces/api/v1/pipelines.py:175-211`): resolves the project,
    then `load_pipeline(Path(name))`, then `spec_path = project_root / body.spec` and
    `spec_path.exists()` → 404 `FILE_NOT_FOUND`. So today the answer tells whether an outside file
    exists.
  - `resolve_file_in_project` (`interfaces/api/v1/paths.py:52-74`): `validate_relative_path`
    (text: absolute or `..` refused, `PATH_TRAVERSAL` 400), then `project_root / file_path`, then
    `exists()`. A link inside the project that points outside passes. Callers: `implement.py:35`,
    `review.py:34`, `validation.py:79-80` (which also calls `validate_relative_path` first).
  - `load_pipeline(Path(name))` → `_resolve_path` (`core/flow/engine/parser.py:80-110`): tries
    `path.exists()` (relative to the server's working folder), then `path.with_suffix(".yaml")`,
    then the bundled template `path.stem`. So `name` reads a YAML file beside the server.
  - Bundled pipelines: `list_bundled_pipelines()` → `feature_decomposition`, `new_feature`,
    `scenario_integration`, `scenario_validation`, `validate_only`. `GET /pipelines` lists exactly
    these.
  - **New finding, probed 2026-10-22:** `POST /check` field `pipeline` reaches
    `load_pipeline_yaml(name, project_dir=project_root)` (`assurance/validation/pipeline_loader.py:32,
    69-82`), which reads `{project}/.specweaver/pipelines/{name}.yaml`. With
    `name = "../../../outside/evil"` it loaded a YAML file outside the project. Not in the audit.
    See audit Q1.
  - `POST /projects` (`projects.py:45-70`) checks `Path(body.path).exists()`, stores
    `str(Path(body.path))` unresolved. `PUT /projects/{name}` (`projects.py:105-131`) stores
    `body.path` unresolved and **does not check that it exists**. See audit Q3.
  - **CLI writers of the same column:** `sw init` stores `resolve_project_path(path)` (resolved,
    `workspace/project/interfaces/cli.py:53-60`); `sw update <name> path <value>` stores `value`
    unresolved (`cli.py:209`). See audit Q2.
  - `WorkspaceRepository.register_project` / `update_project_path` (`workspace/store.py:128, 215`)
    compare `root_path` text for duplicates, so `./p` and `/abs/p` count as two projects today.
- Layer rules: `interfaces.api` depends on `core.flow` (`tach.toml:65-66`) and may not import
  `sandbox` (NFR-5). `core.flow` consumes `sandbox/security` (`core/flow/context.yaml:32`). SF-01's
  `WorkspaceBoundary.contains` / `resolve_relative` are what the helper calls; the boundary logs the
  resolved path at WARNING (NFR-2's log half).
- Tests to follow: `tests/unit/interfaces/api/v1/test_implement.py` (`client`,
  `_project_with_spec`), `tests/e2e/capabilities/interfaces/test_api_pipeline_run_models_e2e.py`
  (real app, `tests.api_token.AUTH`), `tests/integration/interfaces/api/test_api_max_runs.py`.

## Decisions (Phase 4, user answered "all A" 2026-10-22)

1. `POST /check` `pipeline` is in FR-10: a bare name only `[agreed 2026-10-22]`.
2. FR-7 covers the CLI `sw update <name> path` too `[agreed 2026-10-22]`.
3. `PUT /projects/{name}` checks the folder exists, like `POST` `[agreed 2026-10-22]`.
4. A name that is not allowed answers 404 `PIPELINE_NOT_FOUND` `[agreed 2026-10-22]`.
5. Rows already stored with a relative path stay as they are; every new write is resolved. The
   design records the limit `[agreed 2026-10-22]`.
6. `POST`/`PUT /projects` answer with the resolved path that was stored `[agreed 2026-10-22]`.
7. `extends:` in a project pipeline stays out of scope `[agreed 2026-10-22]`.
8. Dev found 6 tests that run their own pipeline file over the API (`two_steps.yaml`, …). The run
   route also loads the project's own `<project>/.specweaver/pipelines/<name>.yaml`, by bare name
   and inside the project; a file beside the server stays refused `[agreed 2026-10-22]`.

## Approach (pseudocode, ordered)

**Helper (AD-2)** — `core/flow/engine/project_paths.py`: `project_file(project_root: Path, relative:
str) -> Path`, and `ProjectPathError(ValueError)`.
1. Build `WorkspaceBoundary([project_root])`. 2. If `not boundary.contains(Path(relative))` (or
`relative` is blank) raise `ProjectPathError` naming the input only. 3. Return
`boundary.resolve_relative(relative)`.
`core.flow` may use only `WorkspaceBoundary` from `sandbox.security` (SF-01: `WorkspaceBoundaryError`
is not exposed), so the helper asks `contains` — never widen `tach.toml` (NFR-5). `core.flow` has no
tach `expose` list, so the API may import the helper.

> [!CAUTION]
> Blank must be checked by hand: `Path("")` is `.`, which `contains` calls inside. A link that
> changes between `contains` and `resolve_relative` raises `WorkspaceBoundaryError` (not a
> `ValueError`) and answers 500: accepted, AD-6.

**FR-2 — pipeline run `spec`** (`pipelines.py:175-211`)
1. Resolve the project. 2. Load the pipeline (FR-10). 3. `project_file(project_root, body.spec)`;
`ProjectPathError` → 400 `PATH_TRAVERSAL`, before `exists()` and before any run row. 4. `exists()` →
404 as today. 5. The run uses the path the helper returned, never `project_root / body.spec`, so the
path checked is the path used.

**FR-3 — `resolve_file_in_project`** (`paths.py:52-74`)
1. Keep `validate_relative_path` (text check). 2. `project_file(...)` (resolved check). 3. `exists()`.
4. Return the helper's path as `abs_path`.

**FR-10 — pipeline names**
1. Run route and resume route (`pipelines.py:195`, `:55`), in order: the name is a bare name
   (step 4); then `project_file(project_root, ".specweaver/pipelines/<name>.yaml")` — if it exists,
   load it (decision 8); else, if the name is in `list_bundled_pipelines()`, load
   `parser.load_bundled_pipeline(name)` (packaged template only); else 404 `PIPELINE_NOT_FOUND`,
   naming the input only. A `ProjectPathError` (the folder links outside) is also 404.
2. `load_pipeline(Path)` stays for the CLI (`sw run my.yaml` is a local user's own file).
3. Move the 6 tests' YAML into `<project>/.specweaver/pipelines/` and call them by bare name:
   `test_api_pipeline_run_models_e2e.py`, `test_api_gate_resumes_the_run_e2e.py`,
   `test_tablet_journey_e2e.py`, `test_api_runs_read_the_doc_policy.py`, `test_ws_ends.py`,
   `test_api_max_runs.py`.
3b. `POST /check`: an explicit `pipeline` must be a bare name: non-empty, no `/`, `\`, NUL, no
   leading `.`. Otherwise 404 `PIPELINE_NOT_FOUND`. A project-local
   `.specweaver/pipelines/<name>.yaml` still loads. A missing name also answers 404 (today
   `load_pipeline_yaml`'s `FileNotFoundError` is not caught in the route; dev checks today's answer
   first).
4. The bare-name rule lives once, in `interfaces/api/v1/paths.py`.

> [!CAUTION]
> The run route checks a name against the list, not by text. `validation_*` and `context` are not
> in `GET /pipelines`, so the run route refuses them; they are not run pipelines.

**FR-7 — project paths** — one resolver for every writer: `resolve_project_path(path)`
(`workspace/project/discovery.py:21`, exposed in tach; `sw init` already uses it).
1. `POST /projects`: resolve; `FileNotFoundError`/`NotADirectoryError` → 400 `PATH_NOT_FOUND`
   naming `body.path` (never the resolved path); store, scaffold and answer the resolved path.
2. `PUT /projects/{name}`: the same.
3. CLI `sw update <name> path <value>`: the same resolver; error → exit 1; print the stored path.

> [!WARNING]
> The resolver also refuses a file (not a folder). `POST` accepted one before. A project that is a
> file never worked, so this is intended; a test pins it.

> [!NOTE]
> Duplicate detection compares stored text (`workspace/store.py:128, 215`). Once every write is
> resolved, `./p` and `/abs/p` are one project. Old relative rows are not touched (decision 5).

## Proposed Changes

| Tag | File | Change |
|---|---|---|
| [NEW] | `src/specweaver/core/flow/engine/project_paths.py` | `project_file`, `ProjectPathError` |
| [MODIFY] | `src/specweaver/interfaces/api/v1/paths.py` | FR-3; `ProjectPathError` → `PATH_TRAVERSAL` 400; the bare-name rule |
| [MODIFY] | `src/specweaver/interfaces/api/v1/pipelines.py` | FR-2; FR-10 run + resume |
| [MODIFY] | `src/specweaver/core/flow/engine/parser.py` | FR-10: `load_bundled_pipeline(name)` |
| [MODIFY] | `src/specweaver/interfaces/api/v1/validation.py` | FR-10 for `/check` |
| [MODIFY] | `src/specweaver/interfaces/api/v1/projects.py` | FR-7 POST, PUT |
| [MODIFY] | `src/specweaver/workspace/project/interfaces/cli.py` | FR-7 `sw update` |
| [NEW] | `tests/unit/core/flow/engine/test_project_paths.py` | the helper |
| [NEW] | `tests/e2e/capabilities/interfaces/test_api_run_spec_stays_inside_e2e.py` | P-1 journey |
| [NEW] | `tests/integration/interfaces/api/test_api_file_fields_stay_inside.py` | P-2 (FR-3) |
| [NEW] | `tests/integration/interfaces/api/test_api_pipeline_names.py` | P-1b (FR-10) |
| [NEW] | `tests/integration/interfaces/api/test_api_project_paths_resolved.py` | P-6 (FR-7) |
| [MODIFY] | the existing `sw update` unit test file (dev finds it) | FR-7 CLI |
| [MODIFY] | the 6 run tests listed under FR-10 step 3 | their pipeline moves into the project |
| [MODIFY] | `TECH-075_mutants.json` | FR-2, FR-3, FR-7, FR-10 campaigns |

## Test Plan

| FR | Tier | Test file | Cases (bucket) |
|---|---|---|---|
| helper | unit | `test_project_paths.py` | inside (happy); `.` (boundary); `..`, absolute, escaping link, null byte, blank (hostile); message names the input only (NFR-2). NFR-1 (root unknown) is the API's: unknown project → 404 `PROJECT_NOT_FOUND`, no run (in the e2e) |
| FR-2 | e2e | `test_api_run_spec_stays_inside_e2e.py` | real app + token: `../x` to an outside file that exists, absolute, escaping link → 400 `PATH_TRAVERSAL`, no run row, no absolute path in the body; inside spec → run starts and its `spec_path` is the resolved path (happy); unknown project → 404, no run (degradation). Red on today's code: the outside file passes the check |
| FR-3 | integration | `test_api_file_fields_stay_inside.py` | `/implement`, `/review`, `/check`: escaping link → 400 (hostile); link inside → passes (boundary, NFR-3); missing inside file → 404 (degradation) |
| FR-10 | integration | `test_api_pipeline_names.py` | run: YAML beside the server, `foo.yaml`, `../x`, `validation_spec_default`, unknown → 404 (hostile); bundled name → runs (happy); project pipeline by bare name → runs (happy); `.specweaver/pipelines` a link outside → 404 (hostile); resume of a run row with a non-bundled name → 404 (degradation). `/check`: `../../x` (outside YAML exists) → 404, never loaded; project-local name → loads (happy); unknown → 404 |
| FR-7 | integration | `test_api_project_paths_resolved.py` | POST and PUT with a relative path and `a/../b` → stored and answered resolved (happy); one folder by two spellings → 409 (boundary); PUT missing path → 400 `PATH_NOT_FOUND`, row unchanged; a file → 400 (hostile); an error body never holds the resolved path (NFR-2) |
| FR-7 | unit (CLI) | `sw update` test file | relative path → stored resolved; missing → exit 1, row unchanged |
| agreement | integration | `test_api_project_paths_resolved.py` | `POST`, `PUT` and `sw init`'s resolver store the same text for one folder |

Mutants to write to `TECH-075_mutants.json`:
- FR-2: skip the spec check; check after `exists()`.
- FR-3: drop the resolved check (keep the text check).
- FR-10: the run route loads any name again (`load_pipeline(Path(name))`); `/check` skips the bare-name rule.
- FR-7: POST stores `body.path` unresolved; `sw update` stores `value` unresolved.

## Commit Boundaries

| CB | Tasks | Done when |
|---|---|---|
| CB-1 | helper + FR-2 + FR-3. The e2e is written first and is red on today's code | unit + integration + e2e green; FR-2, FR-3 mutants killed |
| CB-2 | FR-10: run, resume, `/check` | integration green; FR-10 mutants killed |
| CB-3 | FR-7: POST, PUT, CLI. Closes SF-02: stops for the user's acceptance | integration + unit green; FR-7 mutants killed |

## Documentation

`security_guardrails.md` ("one boundary for paths from outside" gains the API); the REST API user
guide where it documents `path` / `pipeline` (bare names, resolved paths); the design's Findings
table and FR-7 / FR-10 rows (done at Phase 4).

## Audit (Phase 2) — answered: all A, 2026-10-22

| # | Question | Options | Proposal | Severity |
|---|---|---|---|---|
| 1 | **New escape:** `POST /check` `pipeline` reads any `*.yaml` outside the project (probed). Not in the audit, not in an FR. | A: add it to FR-10 here (same class: a pipeline name must be a bare name). B: a new ticket. | A — same broken promise, same fix, one more call site | HIGH |
| 2 | `sw update <name> path <value>` (CLI) stores an unresolved path, like the API. FR-7 names only the API. | A: FR-7 covers the CLI too. B: API only. | A — same column, same bug | MEDIUM |
| 3 | `PUT /projects/{name}` stores a path that does not exist; `POST` refuses one. | A: PUT checks existence like POST (400 `PATH_NOT_FOUND`). B: leave. | A | MEDIUM |
| 4 | FR-10 answer for a name that is not a bundled pipeline | A: 404 `PIPELINE_NOT_FOUND` (as for an unknown name). B: 400. | A — no new code for a client to learn; says nothing about the server's files | MEDIUM |
| 5 | Rows already stored with a relative path cannot be repaired: the folder they were relative to is unknown. | A: leave them; new writes are resolved; note it in the design. B: refuse to load a relative row. | A | LOW |
| 6 | `POST`/`PUT /projects` answers with the path as given today. | A: answer the stored, resolved path. B: echo the input. | A — the answer matches what is stored | LOW |
| 7 | A project pipeline's `extends:` names a base the same unchecked way. | A: out of scope: the file is the project's own, and agents cannot write `.specweaver/`. B: check it too. | A | LOW |

## Architecture Verification (Phase 3)

| Change | Module · archetype | I/O & state | Execution | LLM | Dependencies | Domain | Verdict |
|---|---|---|---|---|---|---|---|
| path helper | `core/flow` · orchestrator | path resolution | none | none | `sandbox/security` (already consumed) | run inputs | ok |
| API routes | `interfaces/api` · delivery | none new | none | none | `core.flow` (already a dependency) | HTTP mapping | ok, NFR-5 |
| bundled-name loader | `core/flow/engine/parser.py` | reads packaged YAML | none | none | none new | pipelines | ok |
| `/check` name rule | `assurance/validation` or the API route | none new | none | none | none new | validation pipelines | ok |
| CLI update | `workspace/project/interfaces` · delivery | path resolution | none | none | none new | projects | ok |

No new module edge, no cycle, no `tach.toml` change (NFR-5). No CRITICAL architecture finding.

## Consistency Check and Red/Blue (Phase 5)

Two cycles, proportionate. Cycle 1: 3 MEDIUM, 2 LOW. Cycle 2: no new finding.

| # | Severity | Finding | Fix |
|---|---|---|---|
| RB-1 | MEDIUM | FR-2 checked one path and the run would use another (`project_root / body.spec`) | the run uses the helper's path (FR-2 step 5) |
| RB-2 | MEDIUM | `resolve_file_in_project` would check one path and return another | return the helper's path (FR-3 step 4) |
| RB-3 | MEDIUM | `contains(Path(""))` is true, so blank would pass | blank checked by hand (caution under Helper) |
| RB-4 | LOW | the helper test "root does not exist → refused" asked the helper for NFR-1, which the API owns | moved to the e2e as unknown project → 404 |
| RB-5 | LOW | a race between `contains` and `resolve_relative` gives a 500 | accepted (AD-6) |

FR/NFR/AD cover: FR-2, FR-3, FR-7, FR-10 each have an approach step, a test row, a mutant and a
CB. NFR-1 (e2e unknown project), NFR-2 (body names the input only: helper, FR-2, FR-7 rows), NFR-3
(link inside passes, link out refused: FR-3 row), NFR-5 (no `tach.toml` change; helper uses
`contains`; resolver is exposed). AD-1 (boundary only), AD-2 (helper in `core.flow`), AD-6 (race
accepted).
