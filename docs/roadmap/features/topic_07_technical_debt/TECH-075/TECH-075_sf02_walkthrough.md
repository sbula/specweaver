# Walkthrough: TECH-075 SF-02 — API paths stay in the project

- **Design**: [TECH-075_design.md](TECH-075_design.md)
- **Plan**: [TECH-075_sf02_implementation_plan.md](TECH-075_sf02_implementation_plan.md)

## CB-1 — the helper, FR-2 (run `spec`) and FR-3 (file fields)

### What changed

- New `core/flow/engine/project_paths.py`: `project_file(project_root, relative)` and
  `ProjectPathError(ValueError)`. It refuses blank, then asks `WorkspaceBoundary.contains`, then
  returns the resolved path. The error names the input only.
- `interfaces/api/v1/paths.py`: `project_file_or_400` maps the error to `PATH_TRAVERSAL` 400.
  `resolve_file_in_project` keeps its text check and now returns the helper's resolved path.
- `POST /pipelines/{name}/run` checks `spec` before `exists()` and runs on the resolved path.
- `security_guardrails.md`: the "one boundary" bullet names the API path.

### Red first

- Helper: collection error (no module) before the code.
- e2e (P-1), written before the route change: the inside case failed because the run held
  `specs/../specs/a_spec.md` unresolved; `../`, the escaping link and the absolute path each
  started a run (200).
- FR-3 seam test: written **after** the `paths.py` change (out of order). It was then run against
  the old `paths.py` (`git show HEAD:…`, then restored): the 3 hostile cases failed, because
  `/implement`, `/review` and `/check` read the outside file.

### Combined analysis

Architecture: `interfaces.api` → `core.flow` (existing edge); `core.flow` uses only
`WorkspaceBoundary` (exposed). `tach` clean; no `tach.toml` change (NFR-5).

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `project_file` | ✅ inside, `.`, link in, missing, 6 ways out, absolute, link out, message | ✅ via routes | ✅ |
| `project_file_or_400` | — | ✅ | ✅ |
| `resolve_file_in_project` | existing | ✅ three routes, link in, missing | — |
| `start_pipeline_run` (spec) | existing | — | ✅ resolved path, 4 ways out, unknown project |

Gap found while mutating and closed: the "check after `exists()`" mutant survived until a case for
an outside file that does **not** exist was added (it must be 400, not 404).

### Results

- `tests.py cb TECH-075 --kind bugfix`: unit ok, integration ok.
- Full suite: 11291 passed, 9 skipped. `quality.py cb`: format fixed in the seam test, then rerun.
- Mutants: `run-spec-unchecked`, `run-spec-checked-after-exists`, `file-field-text-check-only`,
  `blank-path-is-root` — killed, hashes pinned.

### Decisions

- Decision 8 (agreed 2026-10-22): the run route also loads the project's own
  `.specweaver/pipelines/<name>.yaml`; 6 existing tests run their own pipeline file. Built in CB-2.
- Accepted (AD-6): a link that changes between `contains` and the resolve answers 500.
- Not changed: a `spec` that is a folder inside the project still passes `exists()`; it is not a
  way out.

## CB-2 — FR-10: an API client names a pipeline, never a path

### What changed

- `paths.require_bare_pipeline_name`: empty, a leading dot, `/`, `\` or NUL → 404
  `PIPELINE_NOT_FOUND`, as for any unknown name.
- `parser.load_bundled_pipeline(name)`: only names in `list_bundled_pipelines()`, read from the
  package. `load_pipeline(Path)` is unchanged for the CLI.
- `pipelines._api_pipeline` (run, resume, gate answer): bare name → the project's own
  `.specweaver/pipelines/<name>.yaml` through `project_file` (decision 8) → else bundled → else 404.
- `POST /check`: an explicit `pipeline` must be a bare name; a missing pipeline is now 404, not an
  unhandled error. The lookup moved to `_check_pipeline` (complexity 16 → under 15).
- 6 API tests that ran their own pipeline file from the server's folder now keep it in the
  project's `.specweaver/pipelines/`. `test_ui.py::test_submit_hitl_gate` stored an absolute file
  path as the run's pipeline name; it now stores `validate_only`.

### Red first

9 of 15 cases failed on the old code for the right reason: `beside` and `beside.yaml` ran from the
server's folder, a parked run resumed with a name not allowed, `/check` loaded `../../../evil.yaml`
outside the project (200), and a bad `/check` name was an unhandled `FileNotFoundError`.
`..` and `..%2F…` never reach the route (the client and router remove them), so the run side's
bare-name rule is proven through resume: `../../in_project` lands inside the project but outside
`.specweaver/`, where agents may write.

### Combined analysis

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `load_bundled_pipeline` | ✅ bundled, 4 names not in the list, file beside the process | ✅ | ✅ (`validate_only` in P-1) |
| `require_bare_pipeline_name` | — | ✅ run (resume), `/check` | — |
| `_api_pipeline` | — | ✅ bundled, project, 6 others, invalid YAML, linked folder, resume | ✅ gate resume, models, tablet |
| `_check_pipeline` | — | ✅ project-local, 4 refusals | — |

Gaps found in the gate and closed: `load_bundled_pipeline` had no unit test; an invalid project
pipeline had no case.

### Results

- `tests.py cb TECH-075 --kind bugfix`: unit ok, integration ok.
- Mutants (FR-10): `run-name-read-beside-server`, `run-name-not-bare`,
  `project-pipelines-link-followed`, `check-name-not-bare` — killed, hashes pinned. The bundled
  list check in `load_bundled_pipeline` was killed too (not in the corpus).

### Decisions

- Decision 8 (agreed 2026-10-22) built here.
- Accepted: a project pipeline with the same name as a bundled one wins, as `/check` already does.
- Accepted: `GET /pipelines` still lists only bundled pipelines.
- Accepted: an invalid project pipeline answers 404 with the parser's message, which names the
  file in the client's own project.
