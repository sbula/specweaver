# Implementation Plan: Each Entry Point Builds Its Run by Hand, and the API Gets Less [SF-04: Every API door uses it]
- **Feature ID**: TECH-077
- **Sub-Feature**: SF-04 — Every API door uses it
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-077/TECH-077_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-04
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-077/TECH-077_sf04_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-12 (every API door builds through `run_setup`), FR-7 (`selector` honoured, `new_feature` accepted),
FR-8 (`POST /standards/scan` through `discover_files`), and the API half of FR-4 (`/check` uses the
request's project, not the active one — EP-5). NFR-1 (one agreement test across CLI and API). Kind
`bugfix`. Depends on SF-02 (committed); SF-03 is committed too, so the agreement test can compare
real doors. NFR-2, NFR-3, NFR-4 apply.

## Research Notes

- **The API doors today** (read 2026-10-23):
  - `POST /pipelines/{name}/run` and `_resume_existing_run` (used by `POST /runs/{id}/resume` and
    `POST /runs/{id}/gate`) (`interfaces/api/v1/pipelines.py:48-178`): a bare `RunContext` with
    `project_policy` (sections), `_models_for` (router via `api_router`), `_apply_isolation`
    (`apply_isolation_policy`, no DAL escalation). No rule file, no standards, no topology, no
    `config`. `body.selector` is never read. `new_feature` is refused: the spec must exist (`:143`).
  - `POST /review`, `POST /implement` (`review.py`, `implement.py`) call `_llm.run_steps`: rule file
    and standards, no sections, no isolation, no topology. `ImplementRequest.selector` is ignored.
  - `POST /standards/scan` (`standards.py:59-82`): `rglob` over five extensions, then drops any file
    whose **absolute** path has a dot part — a project under `~/.local` scans nothing.
  - `/check` (`validation.py:108`): `_active_domain_profile(db)` — the active project's profile, not
    the request's.
- **Error codes today** (AD-3: keep them): `DOC_POLICY`, `AUTONOMY_POLICY`, `IMPLEMENT_POLICY`
  (`run_settings.project_policy`), `SANDBOX_SETTINGS` / `DAL_DEFINITIONS` / `STANDARDS_SETTINGS`
  (`run_settings._settings_code`), `LLM_SETTINGS` (`_llm.api_router`), all 500. The builder raises one
  `SettingsFileError`; its `source` and `key` say which file and section, so one mapper gives the
  same codes. `max_runs` (`SETTING_NOT_SET` 409, `LLM_SETTINGS`) stays as it is.
- **Pinned by tests**: `tests/integration/interfaces/api/test_api_broken_settings_refuse.py`,
  `tests/unit/interfaces/api/v1/test_settings_error_codes.py` (TECH-076), `test_api_run_isolation_policy.py`,
  `test_api_runs_read_the_doc_policy.py`, e2e `test_api_gate_resumes_the_run_e2e.py`,
  `test_api_pipeline_run_models_e2e.py`, `test_api_llm_endpoints_e2e.py`.
- **The builder** (`interfaces/run_setup/builder.py`): `build_run` is async; the API awaits it.
  `ask=None` (the API never asks). `UnknownProjectError` cannot happen: the API names its project and
  `resolve_project_root` has already answered 404 for an unknown one.
- **Background runs**: `event_bridge.start_run` logs an exception escaping the run. Whether a
  `SessionWorktreeError` at the session start leaves the run recorded `failed` is unverified; the
  design's risk row claims it is. CB-1 tests it.
- **`new_feature`**: the CLI derives `specs/<name>_spec.md` (`spec_path_resolution.resolve_spec_path`)
  and skips the exists-check for that pipeline only. `resolve_spec_path` first tries the name as a
  path relative to the **process's** folder — wrong for a server, so the API derives the path itself
  and keeps it inside the project with `project_file_or_400`. With no interactive channel the draft
  step parks, as a headless CLI run does; `POST /runs/{id}/gate` resumes it.
- **Layering**: `interfaces.api` gains `interfaces.run_setup`; `run_setup` forbids `interfaces/api`.

## Decisions (Phase 4, user answered "all A" 2026-10-23)

1. `POST /implement` on a project whose worktree cannot start answers **409 `WORKTREE_UNAVAILABLE`**,
   naming `git init` and `auto_isolate_min_dal = "off"` — the one new error code (design AD-3
   amended) `[agreed 2026-10-23]`.
2. `POST /review` is read-only like `sw review`: no per-run worktree, the per-step policy stays
   (design FR-3 updated) `[agreed 2026-10-23]`.

## Approach (pseudocode, ordered)

**The API side of the builder** (`interfaces/api/v1/run_doors.py` [NEW])
1. `async build_api_run(project_root, spec_path, pipeline, *, project, selector, read_only)`:
   `RunRequest(ask=None)` → `await build_run`; a `SettingsFileError` → `SpecWeaverAPIError(500)` with
   the code chosen by `settings_error_code(err)`: DAL file → `DAL_DEFINITIONS`; key section `docs` →
   `DOC_POLICY`, `autonomy` → `AUTONOMY_POLICY`, `implement` → `IMPLEMENT_POLICY`, `standards` →
   `STANDARDS_SETTINGS`; the LLM settings (`settings.toml`, `[llm]`) → `LLM_SETTINGS`; else
   `SANDBOX_SETTINGS`.
2. `worktree_unavailable(err)`: a `SessionWorktreeError` → `SpecWeaverAPIError(409, "WORKTREE_UNAVAILABLE")` (decision 1), for the synchronous doors.

**Doors**
3. Run and resume: `build_api_run(..., selector=body.selector)`; delete `_models_for`,
   `_apply_isolation`, `run_settings.project_policy`, `run_settings.isolation_settings`.
4. `new_feature`: spec path `specs/<spec>_spec.md` through `project_file_or_400`; no exists-check.
5. `/review`, `/implement`: `run_steps` builds through 1 (`/review` read-only, decision 2; `/implement`
   passes its `selector` and maps the worktree error, decision 1); delete `api_router`. The spend stop (402) and the missing-calls count
   read the context's router.
6. `/check`: the request project's domain profile (`store.domain_profile_at(db, project_root)`,
   SF-01), not the active project's.
7. `/standards/scan`: `discover_files(project_root, AnalyzerFactory)`, then the scanner.

## Proposed Changes

| File | Change |
|---|---|
| `src/specweaver/interfaces/api/v1/run_doors.py` [NEW] | `build_api_run`, `settings_error_code`, the worktree refusal |
| `src/specweaver/interfaces/api/v1/pipelines.py` [MODIFY] | run, resume, gate on the builder; `selector`; `new_feature` |
| `src/specweaver/interfaces/api/v1/_llm.py` [MODIFY] | `run_steps` on the builder; `api_router` removed |
| `src/specweaver/interfaces/api/v1/review.py`, `implement.py` [MODIFY] | pass read-only / selector |
| `src/specweaver/interfaces/api/v1/run_settings.py` [MODIFY] | keep `max_runs`; the rest moves to `run_doors` |
| `src/specweaver/interfaces/api/v1/validation.py` [MODIFY] | request project's profile |
| `src/specweaver/interfaces/api/v1/standards.py` [MODIFY] | `discover_files` |
| `tach.toml` [MODIFY] | `interfaces.api` → `interfaces.run_setup` |

## Test Plan

| FR | Tier | Test file | Cases (bucket) |
|---|---|---|---|
| FR-12 | integration | `tests/integration/interfaces/api/test_api_doors_build_alike.py` [NEW] | real DB, project with `CONSTITUTION.md`, `[docs]`, standards, DAL_B, git, `enforce_worktree_isolation`: run, gate-resume, `/review`, `/implement` each hand the runner the rule file, standards, sections and per-step policy (happy, the runner spied on); run and `/implement` get the per-run worktree, `/review` not (boundary, decision 2); a broken `[docs]` / `[sandbox]` / `settings.toml` answers 500 with `DOC_POLICY` / `SANDBOX_SETTINGS` / `LLM_SETTINGS` (hostile) |
| FR-12 | integration | same file | a background run on a DAL_B project with no git ends `failed`, the worktree message on the run (degradation); `/implement` there answers 409 `WORKTREE_UNAVAILABLE` (decision 1) |
| NFR-1 | integration | `tests/integration/interfaces/test_cli_and_api_agree.py` [NEW] | the same pipeline and project through `sw run` and `POST /pipelines/{name}/run`: equal rule file, standards, sections, isolation, topology (agreement) |
| FR-7 | integration | `tests/integration/interfaces/api/test_api_selector_and_new_feature.py` [NEW] | `selector` reaches the topology slice (`nhop` ≠ `direct` on a project with a neighbour) (happy); `new_feature` with a module name starts, its spec path inside the project (boundary); `new_feature` with `../x` → 400 `PATH_TRAVERSAL` (hostile); the draft step parks with no channel and the gate resumes it (degradation) |
| FR-8 | integration | `tests/integration/interfaces/api/test_api_standards_scan.py` [NEW] | a project under a dot-folder (`tmp/.local/proj`) scans its files (happy, the defect); `.specweaverignore` excludes a file (boundary); a `node_modules` file inside the project is skipped (boundary) |
| FR-4 | integration | `tests/integration/interfaces/api/test_api_check_profile.py` [NEW] | `/check` on project B while A is active uses B's domain profile (hostile, EP-5) |

Expected reds: every FR-12 part case fails today (no rule file, no topology, no DAL escalation);
NFR-1 fails on the rule file; `selector` and `new_feature` fail; the dot-folder scan returns `[]`;
`/check` takes A's profile.

Mutants: `build_api_run` drops `selector` (FR-7); `new_feature` exists-check kept (FR-7); scan goes
back to `rglob` with absolute dot filter (FR-8); `/check` reads the active profile (FR-4); an error
code mapped to the wrong section (FR-12); `/review` not read-only (decision 2); the worktree error not mapped (decision 1).

## Commit Boundaries

| CB | Tasks | Done when |
|---|---|---|
| CB-1 | `run_doors` (builder + error codes); run, resume, gate; `selector`, `new_feature`; background worktree failure recorded | green; FR-12 run cases, FR-7 |
| CB-2 | `/review`, `/implement` (decisions 1, 2); `/check` profile; `/standards/scan`; NFR-1 agreement test; docs. Closes SF-04: stops for the user's acceptance | green; every mutant above killed |

## Documentation

`docs/dev_guides/pipeline_engine_guide.md` (API doors escalate too; "API composition roots do not
resolve the policy yet" goes); the API user guide's `POST /pipelines/{name}/run` (`selector`,
`new_feature`) and the `/implement` error.

## Audit (Phase 2) — answered: all A, 2026-10-23

| # | Question | Options | Proposal | Severity |
|---|---|---|---|---|
| 1 | `POST /implement` waits for its run. On a high-DAL project with no git the run now stops at the worktree. Which HTTP answer? AD-3 says "no new error codes". | A: a new code `WORKTREE_UNAVAILABLE`, 409, naming `git init` and `auto_isolate_min_dal = "off"` (AD-3 amended for this one code). B: the existing `GENERATION_FAILED`, 500, with the message. | A — the project's state, not a failed generation; a client can tell them apart | MEDIUM |
| 2 | `POST /review` runs the same read-only step as `sw review`. Decision 1 of SF-03 named only CLI doors. | A: `/review` is read-only too (no per-run worktree). B: `/review` isolates. | A — same action, same rule | LOW |

## Architecture Verification (Phase 3)

| Change | Module · archetype | I/O & state | Execution | LLM | Dependencies | Domain | Verdict |
|---|---|---|---|---|---|---|---|
| `interfaces/api/v1/run_doors.py` | `interfaces/api` · adapter | builds runs | none | none directly | + `interfaces.run_setup` | HTTP delivery | ok |
| doors | `interfaces/api` · adapter | unchanged | unchanged | router from the builder | − `run_settings` helpers | unchanged | ok |

No cycle: `run_setup` forbids `interfaces/api`. The engine gains nothing (NFR-2).

## Consistency Check and Red/Blue (Phase 5)

- **Coverage**: FR-12 (CB-1 run/resume/gate, CB-2 `/review`, `/implement`), FR-7 (CB-1), FR-8 (CB-2),
  FR-4 API half (CB-2), NFR-1 (CB-2, with both doors on the builder). FR-3 through the API: run and
  `/implement` escalate by DAL, `/review` read-only. NFR-2: the engine gains nothing. NFR-3: the
  API maps; the builder raises. NFR-4: the TECH-076 error-code tests stay green unchanged. AD-3: one
  new code, agreed.
- **Open questions**: none. All decisions are resolved and documented inline in the plan.
- **Handoff risk**: (a) the code mapper must give exactly today's codes — the TECH-076 tests pin them,
  run them first. (b) `resolve_spec_path` is never used by the API (it reads the server's folder).
  (c) after CB-2, `run_settings.py` holds only `max_runs`.
- **Architecture**: one new link, `interfaces.api` → `interfaces.run_setup`; no cycle.
- **DDD/KISS/DRY/hexagonal/SoC**: the three API setups and `api_router` become one builder call; the
  API keeps only its HTTP mapping.
- **Code detail limit**: no code block; pseudocode only.
- **Red/Blue**, 2 cycles:
  - R1 (MEDIUM) the mapper could misfile a section. Blue: one hostile case per code in CB-1; a
    mutant swaps two.
  - R2 (MEDIUM) a background run whose worktree cannot start may stay `running` in the store.
    Blue: CB-1 tests it; if it stays, the session start records the run `failed` with the message
    before raising.
  - R3 (MEDIUM) a project broken in two files answers with the first one the builder reads. Blue:
    the same order as today (sections first, then settings, then models).
  - R4 (LOW) `new_feature` with an existing spec. Blue: the draft step's own rule applies, as in
    `sw run new_feature`.
  - Cycle 2: no new finding. Below every threshold.
