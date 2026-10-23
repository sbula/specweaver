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
