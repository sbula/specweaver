# Walkthrough: TECH-077 SF-04 — Every API door uses it

Plan: [TECH-077_sf04_implementation_plan.md](TECH-077_sf04_implementation_plan.md).

## CB-1 — the API side of the builder; run, resume, gate (FR-12, FR-7)

### What changed

- `interfaces/api/v1/run_doors.py` [NEW]: `build_api_run` (awaits the builder, `ask=None`) and
  `settings_error_code` — one `SettingsFileError` gives today's codes from its file and section
  (`DAL_DEFINITIONS`, `DOC_POLICY`, `AUTONOMY_POLICY`, `IMPLEMENT_POLICY`, `STANDARDS_SETTINGS`,
  `LLM_SETTINGS`, else `SANDBOX_SETTINGS`).
- `POST /pipelines/{name}/run`, `POST /runs/{id}/resume`, `POST /runs/{id}/gate`: on the builder. API
  runs now get the rule file, standards, topology, `config`, and DAL escalation (before: sections,
  router and the two isolation policies without escalation only).
- `selector` reaches the topology slice. `new_feature` starts with `specs/<name>_spec.md`, kept
  inside the project, and no exists-check.
- `core/flow/engine/session.py`: a run whose worktree cannot start (or whose resumed worktree is
  gone) is saved `failed`, its step naming why, before the error is raised. Before, a background
  API run in that state was not in the store at all (`RUN_NOT_FOUND`) — the design's risk row said
  "recorded on the run", which was not true; the CB-1 test found it.
- Removed, no callers left: `run_settings.project_policy`, `run_settings.isolation_settings`,
  `run_settings._settings_code`, `pipelines._models_for`, `pipelines._apply_isolation`,
  `core/flow/engine/isolation.apply_isolation_policy`.
- `tach.toml`: `interfaces.api` → `interfaces.run_setup`; `project_settings.PROJECT_FILE_NAME`
  exposed (the error mapper must not spell a settings file name).

### Red first

`test_api_doors_build_alike.py`: run, resume, gate failed (no rule file). `test_api_selector_and_new_feature.py`:
the selector case (no topology) and `new_feature` (404) failed. The background-worktree case failed
with `RUN_NOT_FOUND` — the gap above.

### Tests re-homed

- `test_api_run_isolation_policy.py` deleted with `apply_isolation_policy`; its claims
  (`TECH-013` FR-1, FR-2) are now asserted on the context an API run actually gets
  (`test_api_doors_build_alike.py`).
- `test_settings_error_codes.py` asks `settings_error_code`, with the three section codes and the
  machine file added; the "unknown project leaves no settings" case lives in `test_build_run.py`.
- `test_pipelines.py`'s REST-resume-gets-its-models case patches the builder's router.

### Mutants

Re-pointed and OBJECTED: B-FLOW-07 `rest-run-without-models`, `rest-resume-without-models`;
C-FLOW-11 `api-reads-another-file`; D-INTL-08 `api-names-no-language`; C-EXEC-08
`api-start-skips-the-policy`, `api-resume-skips-the-policy` (SILENT until its scope gained the API
door test); TECH-075 `run-spec-checked-after-exists`; TECH-076 `api-run-isolation-off`,
`standards-code-lost`, `dal-code-lost`. New, OBJECTED: `api-selector-ignored`,
`new-feature-needs-spec`, `new-feature-escapes`, `docs-code-lost`, `machine-settings-misfiled`,
`worktree-failure-unrecorded`. Drifted: 0.

### Gates

Full suite 11521 passed, 9 skipped (2 fr-sweep failures first: a two-ID `Proves:` line, split).
`quality.py sf` 18/18. `tach check` clean.

### Red/Blue (code)

- R1 (MEDIUM) API runs with a model step now carry `config`, so `[sandbox] execution_mode` reaches
  them as it already reached `sw run`. Accepted: EP-4 named the missing `config` as the defect.
- R2 (LOW) a `new_feature` name like `../x` stays inside the project (`specs/../x_spec.md`) and is
  allowed; a name leaving the project answers 400.
- R3 (LOW) `worktree_unavailable` (decision 1) is held back to CB-2, where `/implement` calls it.
- Cycle 2: no new finding.

## CB-2 — `/review`, `/implement`, `/check`, `/standards/scan`, agreement (FR-12, FR-3, FR-4, FR-7, FR-8, NFR-1)

### What changed

- `_llm.run_steps` builds through `build_api_run`; `api_router` removed (the last of the three router
  factories EP-4 named). `/review` is read-only (decision 2): sections and the per-step policy, no
  per-run worktree. `/implement` passes its `selector` and answers 409 `WORKTREE_UNAVAILABLE` when the
  worktree cannot start (decision 1, `run_doors.worktree_unavailable`).
- `/check` takes the request project's domain profile (`store.domain_profile_at`), not the active
  project's (EP-5).
- `/standards/scan` finds files with `discover_files`: dot-folders judged inside the project,
  `.specweaverignore` applied. A project under `~/.local` now scans its files.
- `tach.toml`: `interfaces.api` → `workspace.analyzers` (the scan's analyzers).
- User guide: what an API run gets, `new_feature`, the 409.

### Red first

`test_api_doors_build_alike.py`: `/review` and `/implement` failed on sections and the per-run worktree;
`/implement` without git reached the model call (blocked by the test network guard), not a 409.
`test_api_standards_scan.py`: the dot-folder project scanned nothing. `test_api_check_profile.py`:
project B got A's `web_app` profile.

### Written late, proven by mutant

`test_cli_and_api_agree.py` (NFR-1) and the `/implement` selector case were written after the code
they compare, so they were green on first run. Their proof is a killed mutant each:
`api-run-loses-topology`, `implement-selector-ignored`.

### Tests re-homed

`test_telemetry_wiring.py` patches `infrastructure.llm.router.build_router`, where the builder gets its
router.

### Mutants

Re-pointed and OBJECTED: C-FLOW-01 `rest-unwritten-dropped`. New, OBJECTED: `api-review-not-read-only`,
`implement-worktree-500`, `implement-selector-ignored`, `scan-drops-dot-paths`, `check-ignores-profile`,
`api-run-loses-topology`. Drifted: 0.

### Gates

Full suite 11535 passed, 9 skipped. `quality.py sf` 18/18 after a lint fix and re-freezing one
duplication clone (the shared FastAPI import lines of `constitution.py` and `standards.py`,
re-keyed when a line was removed). `tach check` clean.

### Red/Blue (code)

- R1 (MEDIUM) `/standards/scan` now hands the scanner every file `discover_files` finds, as
  `sw standards scan` does, not only five extensions. Accepted: the scanner judges files by their
  analyzer; the CLI has always done this.
- R2 (LOW) `/check`'s profile lookup runs in a thread (`asyncio.to_thread`), like the other store
  lookups (SF-01 decision 2).
- Cycle 2: no new finding.

### SF-04 coverage

| FR | Proof |
|---|---|
| FR-12 | `test_api_doors_build_alike.py` (run, resume, gate, `/review`, `/implement`), `test_settings_error_codes.py` |
| FR-7 | `test_api_selector_and_new_feature.py` |
| FR-8 | `test_api_standards_scan.py` |
| FR-4 (API) | `test_api_check_profile.py` |
| FR-3 (API) | `test_api_doors_build_alike.py` — the per-run worktree list |
| NFR-1 | `test_cli_and_api_agree.py` |
