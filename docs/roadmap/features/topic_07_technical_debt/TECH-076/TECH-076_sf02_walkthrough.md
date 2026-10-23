# Walkthrough: TECH-076 SF-02 — Every door stops on a broken setting

- **Design**: [TECH-076_design.md](TECH-076_design.md)
- **Plan**: [TECH-076_sf02_implementation_plan.md](TECH-076_sf02_implementation_plan.md)

## CB-1 — FR-5 (CLI commands) and FR-4 (the CLI run root)

### What changed

- `interfaces/cli/_core.py`: `load_project_settings(db, project)` — `load_settings`, and on a
  `SettingsFileError` the existing refusal (`Error: <file>:<line>: <key>: <message>`, exit 1).
- `sw implement`, `sw draft`, `sw review`, `sw standards scan`, `sw drift check --analyze` and the
  run's model wiring call it instead of `load_settings`.
- `_apply_isolation_policy` (`sw run`, `sw resume`) calls it too; the refusal (`typer.Exit`) passes
  through, and any other lookup failure keeps its best effort (design decision 5).
- `tach.toml`: five interface modules no longer import `core.config.bootstrap`; their unused edges
  are removed (tach reports unused edges as errors).
- Coupling: `core/flow/interfaces/cli.py` imported 25 module names before this boundary (fan-out
  above 20, inherited). The topology attach moved to `core/flow/interfaces/run_topology.py`
  (`attach_topology`), which takes `assurance.graph.loader` and `commons.spec_names` with it.

### Red first

- e2e `test_broken_sandbox_stops_the_run_e2e.py`: with `execution_mod`, the run started, executed
  `validate_spec` and recorded a run; the located message never appeared.
- `test_cli_broken_settings_refuse.py`: all six cases ended in an uncaught `SettingsFileError`
  (empty output). `drift check` first failed on a missing `--plan`, a test mistake, fixed before
  judging the red.

### Combined analysis

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `_core.load_project_settings` | — | ✅ five commands + DAL file | — |
| `_apply_isolation_policy` | ✅ loads, other failure best-effort, settings error exits | — | ✅ broken refused, valid runs |
| `attach_topology` | ✅ slice selected, no topology unchanged | — | ✅ existing run e2e |

Composition: the e2e drives `sw init` → `specweaver.toml` → `sw run` through the real loader.
Mutants (OBJECTED, pinned): FR-5 `cli-settings-error-escapes`; FR-4 `cli-run-isolation-off`
(re-pointed after the run root moved to the helper).

### Gates

- Full suite 11408 passed, 9 skipped. `quality.py sf` 18/18 after: tach unused edges (removed),
  coupling (the extraction above), duplication.
- **Duplication baseline re-frozen** (`scripts/baselines/duplication.json`): the report showed the
  same two old clone pairs (the "resolve the project or exit" preamble in `drift check`, `review`
  and `implement`) under new keys, because one import line inside them was deleted; the baseline's
  other line numbers had drifted too. Extracting the preamble into `_core` would add an
  `interfaces.cli → workspace.project` edge, which this design's NFR-4 rules out. Accepted risk;
  the clone count is unchanged (103).

### Red/Blue (code)

- R1 (MEDIUM) `typer.Exit` is a `RuntimeError`; the run root's `except Exception` would swallow the
  refusal. Fixed: `except typer.Exit: raise` first; the mutant removing it is killed by the e2e.
- R2 (LOW) `_wire_models` now refuses a broken file too, but the isolation step before it always
  refuses first. Kept for one rule on every door.
- Cycle 2: no new finding.

## CB-2 — FR-4 (the API doors and the validation step)

### What changed

- `interfaces/api/v1/run_settings.py`: `isolation_settings(db, project)` — `load_settings_async`;
  a `SettingsFileError` becomes 500 with `_settings_code`: `DAL_DEFINITIONS` (the DAL file),
  `STANDARDS_SETTINGS` (`standards` or `standards.*`), else `SANDBOX_SETTINGS` (`sandbox…`, and a
  `(syntax)` error — plan decision 1); any other failure stays best-effort (None).
- `pipelines.py` `_apply_isolation` calls it; run, resume and gate answers all pass through it.
  The lookup lives in `run_settings.py` so `pipelines.py` keeps its fan-out under 20 (`TECH-075`).
- `core/flow/handlers/validation.py` `_resolve_merged_settings`: a failed tier merge raises
  `ValueError("cannot apply the DAL_X rules: …")`; both handlers already turn that into an ERROR
  step (plan decision 2), so the run stops instead of judging the file without its tier.
- `1_installation_and_setup.md` (API bullet): the three codes.

### Red first

- `test_api_broken_settings_refuse.py`: every broken case answered 200 and started a run; the
  parked run resumed.
- `test_validation_dal_merge_stops.py`: the forced merge failure returned the unmerged settings,
  and the spec step ended FAILED on the project's own rules, not ERROR.

### Combined analysis

| Function | Unit | Integration |
|---|---|---|
| `isolation_settings` | ✅ other failure best-effort | ✅ 4 broken cases + resume + valid |
| `_settings_code` | ✅ 7 keys incl. bare table names, `(syntax)`, `standardsx` | ✅ through the route |
| `_resolve_merged_settings` | ✅ layered, no entry, forced failure raises, step ERROR | — |

Mutants (OBJECTED, pinned): FR-4 `api-run-isolation-off`, `standards-code-lost`, `dal-code-lost`,
`validation-without-tier`.

### Gates

- Full suite 11426 passed, 9 skipped (one run failed the happy API case: the run starts in a
  background task after the answer; the test now waits up to 5 s for it — a race in the test, not
  the code). `quality.py sf` 18/18. `tach check` clean.

### Red/Blue (code)

- R1 (MEDIUM) `_settings_code` defaults to `SANDBOX_SETTINGS`: a future section read here would be
  mislabelled. Accepted: only `[sandbox]`, `[standards]` and the DAL file are read by
  `load_settings`; a new section is a new design question.
- R2 (LOW) the error detail carries the absolute settings path. The client named the project and
  the server owns that path; same as `DOC_POLICY` / `AUTONOMY_POLICY` today.
- R3 (LOW) the validation message embeds pydantic's text, which can name a key but never a value
  of the user's (the merged dict comes from validated models).
- Cycle 2: no new finding.

### Added to CB-2 at the user's choice (2026-10-23): the copied CLI preamble

The CB-1 note above accepted the duplicated "find the project folder or exit" block. Asked which
burden is lesser, the user chose the new dependency (`[agreed 2026-10-23]`, design NFR-4 updated):
the block stood in 10 places in 6 files, and the edge points down (delivery → project discovery),
with no loop possible (`workspace.project` depends only on parsers and analyzers).

- `tach.toml`: `specweaver.interfaces.cli` may depend on `specweaver.workspace.project`.
- `_core.project_path_or_exit(project)` replaces all 10 copies (`sw run`, `sw constitution` ×4,
  hooks, `draft`, `review`, `implement`, `drift check`); `_core.file_or_exit(given)` replaces the
  "File not found" check in `drift check` and `review` (the third copy, in `sw check`, resolves
  and also refuses an empty target, so it stays).
- Tests that patched `resolve_project_path` in `sw run` and the hooks now patch it in `_core`;
  `drift check-rot` still calls it directly, so its tests are unchanged.
- Duplication baseline: 103 → 99 clones, none new.
- Red first: `test_project_path_or_exit.py` failed on the missing helpers. Mutant
  `project-path-error-escapes` OBJECTED, pinned.
- Full suite 11432 passed, 9 skipped; `quality.py sf` 18/18; `tach check` clean.

## Decision at the SF-02 stop (user, 2026-10-23)

CB-2 accepted, with the CLI preamble extraction above.
