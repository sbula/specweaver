# Walkthrough: TECH-077 SF-03 — Every CLI door uses it

Plan: [TECH-077_sf03_implementation_plan.md](TECH-077_sf03_implementation_plan.md).

## CB-1 — the CLI side of the builder; `sw run` and `sw resume` (FR-2, FR-5)

### What changed

- `run_setup/builder.py`: `RunRequest.read_only`; a read-only run gets the per-step policy only
  (decision 1).
- `interfaces/cli/run_doors.py` [NEW]: `build_run_or_exit` (project, build, errors → refusals, router
  told at the end), `refuse_unstarted_worktree`, `recorded_project_root`.
- `core/flow/engine/session.py`: `SessionWorktreeError` for "could not start" and "worktree is
  gone", so a door catches a type, not a message.
- `sw run`, `sw resume`: on the builder. `_wire_models`, `_apply_isolation_policy` and the
  hand-built context are gone. `sw resume` takes the run's recorded project and loads a YAML
  pipeline from that project's folder (before: the current folder for both).
- `tell_missing_at_end` is public (the doors call it).
- User guide: a run resumes in its own project.

### Red first

- `test_resume_uses_runs_project_e2e.py`: both cases failed — "Pipeline not found" from project A's
  folder.
- `test_run_doors.py`: import error (no module); the `read_only` case in `test_build_run.py` failed
  (session isolation on).
- The resume-worktree-gone case and the two gap cases were written after the code; each kills its
  mutant.

### Tests moved, not lost

- `test_run_isolation_settings.py` (unit, `_apply_isolation_policy`) deleted: the builder raises on
  a broken setting (`test_build_run.py`), the door refuses it (`test_run_doors.py`); TECH-076's
  mutant re-pointed to the builder.
- `test_router_e2e.py` → `tests/integration/interfaces/cli/test_run_wiring.py`, over a real project.
- `test_high_dal_project_does_not_auto_isolate_on_sw_run` flipped: `sw run` now escalates (FR-3
  reverses INT-US-03 SF-03 G2).
- Tests that ran `sw run` in an unregistered folder register it (SF-02 decision 1).

### Mutants

Re-pointed and OBJECTED: C-FLOW-01 `optional-router-never-tells`, C-FLOW-11
`sw-run-reads-another-file`, C-FLOW-13 `run-drops-run-model` and
`run-model-reads-settings-for-no-model-pipeline`, D-INTL-08 `sw-run-names-no-language`, C-EXEC-08
`sw-run-skips-the-policy`, D-EXEC-02 `folder-name-lookup`, TECH-076 `cli-run-isolation-off`.
New, OBJECTED: `read-only-ignored`, `resume-uses-current-folder`, `resume-pipeline-from-cwd`,
`unknown-project-traceback`, `resume-worktree-traceback`, `router-never-tells`,
`no-folder-no-active-root`. Drifted: 0.

### Gates

Full suite 11494 passed, 9 skipped. `quality.py sf` 18/18. `tach check` clean.

### Red/Blue (code)

- R1 (MEDIUM) `sw resume` uses `selector="direct"`; the run does not record its selector. Accepted
  (plan R3).
- R2 (LOW) `build_run_or_exit` keeps a guard for an active project with no folder; it cannot be
  reached through `sw` today. Kept: it turns a stale row into a refusal, not a crash.
- R3 (LOW) a pipeline name with a path in it (`sw run some/dir/x.yaml`) records only its name;
  resume finds it at the project root or as a bundled one. Same as before for files outside the
  root.
- Cycle 2: no new finding.

## CB-2 — `sw implement`, `sw review`, `sw draft` (FR-2, FR-3, FR-4, FR-11)

### What changed

- `sw implement`: builds through `build_run_or_exit`; standards, settings and router all from the
  project at `--project` (before: standards from the active project). The run is built before
  anything is printed, so a refusal stands alone. A worktree that cannot start is refused.
- `sw review`: through the builder with `read_only=True` (decision 1): no per-run worktree, the
  per-step policy and the sections now apply (before: no isolation, no sections).
- `sw draft`: moved to `workflows/drafting/interfaces/cli.py` (new `tach` module, registered in
  `main.py`), with its pipeline and report helpers. It now gets the rule file, standards, sections
  and isolation; the terminal provider is attached after the build. A worktree error is refused.
- `tach.toml`: the review and implementation interfaces lose four unused links each.
- `cli_architecture.md`: the draft plugin row.

### Red first

`test_cli_doors_build_alike.py`: 5 of 8 failed on the old code — `sw implement` took project A's
standards, `sw review` had no sections and no per-step policy, `sw draft` had no rule file,
`sw implement` without git ended in a traceback. `test_draft_lives_in_drafting.py`: 2 of 3 failed
(no drafting CLI). The `sw draft` no-git case was added after the code; its mutant is killed.

### Tests changed, not lost

- `test_cli_implement_isolation.py` wrote settings through a patched `load_settings`, which the
  async builder does not call; it now writes a real `specweaver.toml`.
- `test_implement_collector_wiring.py`: the refusal in an unregistered folder now names
  `sw init` (SF-02 decision 1).
- Imports of the draft helpers point at the drafting module.

### Mutants

Re-pointed and OBJECTED: C-FLOW-11 `sw-implement-reads-another-file`, C-FLOW-13
`implement-drops-run-model`, D-INTL-08 `sw-implement-names-no-language`, C-EXEC-08
`sw-implement-drops-the-policy` (each now models the door dropping a part the builder gave it).
New, OBJECTED: `implement-worktree-traceback`, `draft-worktree-traceback`, `draft-no-terminal`,
`review-not-read-only`, `draft-not-registered`. Drifted: 0.

### Gates

Full suite 11506 passed, 9 skipped. `quality.py sf` 18/18 after one ruff fix. `tach check` clean.

### Red/Blue (code)

- R1 (LOW) `sw implement` still reads `[implement] language` once itself, to name the task files
  before the run exists. Accepted: the pipeline needs the files before the builder runs.
- R2 (LOW) `sw draft`'s topology slice is now chosen by the spec's stem (`orders` from
  `orders_spec.md`), the same name it used before.
- Cycle 2: no new finding.

## CB-3 — the one-step helper, the read-only doors, and dead code out (FR-2, FR-3, FR-11)

### What changed

- `run_doors.run_one_step`: builds the one-step pipeline, builds its run, runs it; returns the last
  step record and the context (decision 2).
- `sw drift check`, `sw drift check-rot`, the standards scan's per-scope enrichment: on
  `run_one_step` with `read_only=True` (decision 1). They now get the rule file, standards, sections
  and the per-step policy.
- `RunRequest.on_model_skipped`: the builder tells the door why an `optional` model was skipped;
  the CLI prints the same "No model used: <key>: <why>" line as before.
- Removed, no callers left: `command_router`, `optional_command_router` (the CLI's two router
  factories — the third, the API's, goes in SF-04), `_core.project_name_for`,
  `_core.load_project_settings`, `_core.load_llm_settings_at`, `core/flow/interfaces/run_topology.py`.
- Docs: `domain_driven_cli_creation.md` (build a command's run through `run_doors`),
  `pipeline_engine_guide.md` (who escalates; non-git stops), `spec_rot_pre_commit_workflow.md` (the
  hook needs a registered project and opens no per-run worktree), `apply_session_policy` docstring.

### A behavior change to know

`sw drift check-rot` — the git pre-commit hook — now refuses a folder no project is registered at,
naming `sw init`, so it stops the commit there. Before, it ran in any folder. This follows SF-02
decision 1 (no project, no run); two hook tests now register their folder.

### Deviation from the plan

The plan had `check-rot` build its run once and swap the spec per file. It builds once per staged
file through `run_one_step` instead: simpler, and a hook checks a few files.

### Red first

`test_run_one_step.py`: 3 of 3 failed (no helper). `test_cli_doors_build_alike.py`: the drift and
scan cases failed on the old code (no rule file). The no-model line was lost on the first green and
caught by `test_scan_without_brake_e2e.py`; `on_model_skipped` restored it.

### Tests re-homed

- `test_target_project.py` now runs through `build_run_or_exit`; "an unregistered folder falls back
  to the active project" became "is refused" (FR-4).
- `test_missing_calls_told.py` drives `tell_missing_at_end` directly; `run_doors` calling it is
  `router-never-tells`.
- `test_budget_from_settings.py` asks `build_router`, the seam every run uses.
- `test_run_topology.py` deleted with its module; the builder's topology is in `test_build_run.py`.

### Mutants

Re-pointed from deleted code and OBJECTED: B-FLOW-07 `command-without-history`, C-FLOW-01
`optional-router-never-tells`, C-FLOW-13 `router-reads-active-project`,
`target-name-is-active-project`, `command-drops-run-model`, `skipped-model-unnamed`,
`scan-skips-wrong-settings`, TECH-076 `cli-settings-error-escapes`. TECH-077 `optional-model-refuses`
re-anchored. New, OBJECTED: `no-model-said-nothing`, `drift-check-wrong-folder`,
`check-rot-opens-worktree`, `scan-opens-worktree`, `one-step-drops-params`. Drifted: 0.

### Gates

Full suite 11511 passed, 9 skipped. `quality.py sf` 18/18 after one import-order fix. `tach check`
clean (three modules lose unused links; `interfaces.cli` gains `core.flow` for the helper).

### Red/Blue (code)

- R1 (MEDIUM) the hook now blocks commits in an unregistered repo. Accepted: SF-02 decision 1, and
  the message says how to register. Recorded above and in the hook guide.
- R2 (LOW) a scan with several scopes and no model prints "No model used" once per scope.
  Accepted: one line per scope run, each true.
- R3 (LOW) `sw implement` reads `[implement] language` itself once more (CB-2 R1).
- Cycle 2: no new finding.

### SF-03 coverage

| FR | Proof |
|---|---|
| FR-2 | `test_run_doors.py`, `test_cli_doors_build_alike.py` (all eight doors), `test_run_wiring.py` |
| FR-3 (doors) | `test_cli_doors_build_alike.py` — the per-run worktree list is exact |
| FR-4 (doors) | `test_cli_doors_build_alike.py` — `sw implement` in B while A is active |
| FR-5 | `test_resume_uses_runs_project_e2e.py`, `test_run_doors.py` (worktree gone) |
| FR-11 | `test_draft_lives_in_drafting.py`, `test_run_one_step.py` |
