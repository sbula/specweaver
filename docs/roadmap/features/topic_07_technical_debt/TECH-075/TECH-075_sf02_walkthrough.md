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
