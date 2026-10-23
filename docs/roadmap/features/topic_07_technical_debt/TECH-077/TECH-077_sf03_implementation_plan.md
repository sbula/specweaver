# Implementation Plan: Each Entry Point Builds Its Run by Hand, and the API Gets Less [SF-03: Every CLI door uses it]
- **Feature ID**: TECH-077
- **Sub-Feature**: SF-03 — Every CLI door uses it
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-077/TECH-077_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-077/TECH-077_sf03_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-2 (every CLI door builds through `run_setup`), FR-5 (`sw resume` uses the run's project), FR-11
(`sw draft` in the drafting workflow, one one-step helper). Kind `bugfix`. Depends on SF-02
(committed `c2a84a0d`). Carries two items SF-02 handed over: `sw implement` must refuse cleanly
when the worktree cannot start (SF-02 walkthrough CB-2 R1), and `apply_session_policy`'s docstring
must stop saying `sw run`/`sw resume` never escalate (R2). NFR-2, NFR-3, NFR-4 apply.

## Research Notes

- **The eight doors today** (read 2026-10-23):
  - `sw run` / `sw resume` (`core/flow/interfaces/cli.py:244-338`): `_build_run_context`,
    `_wire_models` (settings loaded a second time), `_apply_isolation_policy` (no DAL escalation),
    `attach_topology` after the build (`:420`). Project: registered-or-active (`:259`).
    `resume` uses `resolve_project_path(None)`, the current folder (`:550`), and no topology.
  - `sw implement` (`workflows/implementation/interfaces/cli.py:255-325`): settings and router from
    `project_name_for(project_path)`, standards from the **active** project (`:298`),
    `apply_session_policy(..., dal_auto_escalate=True)`, no `enforce_isolation`. It catches no
    exception around `runner.run()`, so a worktree that cannot start ends in a traceback.
  - `sw review` (`workflows/review/interfaces/cli.py:240-335`) and `sw draft` (`:147-237`): no
    isolation, no sections; `sw draft` attaches `HITLProvider(console=_core.console)` and has no
    rule file or standards.
  - `sw drift check` / `check-rot` (`assurance/validation/interfaces/cli_drift.py:63-95,195-217`):
    bare `RunContext`; a router only with `--analyze`. `check-rot` runs one pipeline per staged file
    and is the git pre-commit hook (`workspace/project/interfaces/cli_hooks.py:29`).
  - `sw standards scan` (`assurance/standards/interfaces/cli.py:120-170`): the active project,
    `optional_command_router(name, [TaskType.CHECK])`, a fresh context per scope (the spend brake
    is per context).
- **Routers**: `command_router` wraps the router in `_tell_missing_at_end` (a CLI-only ledger
  warning at the command's end, `infrastructure/llm/interfaces/command.py:42`) and passes
  `ask=_core.spend_asker()`. `SettingNotSetError` subclasses `SettingsFileError`, so one
  `except SettingsFileError` maps both to `refuse_settings`.
- **The run's project**: `PipelineRun.project_name` is `registered_name(context)`: the registered
  name, else the folder's name (`core/flow/engine/naming.py:17`). `store.project_root_of(db, name)`
  (SF-01) gives its root or None.
- **Session isolation** (`core/flow/engine/session.py:24`) wraps the **whole** run in one worktree
  whatever its steps, and raises `RuntimeError("... session isolation could not start ...")` on a
  non-git project.
- **One-step pipelines**: `PipelineDefinition.create_single_step(name, action, target, description,
  params)` already exists. What repeats is the rest: build the one-step pipeline, build its run, run
  it, take the last step record (`cli_drift.py` ×2, `sw review`, `standards` `_enrich_scope`).
- **Layering**: `core.flow.interfaces`, `workflows.*.interfaces`, `assurance.*.interfaces` are their
  own `tach` modules, so each may depend on `interfaces.run_setup` with no cycle (`run_setup`
  depends on `core.flow`, not on `core.flow.interfaces`). `sw draft` needs a new
  `workflows.drafting.interfaces` module. Command registration: `interfaces/cli/main.py:102-111`.
- **Tests that name old helpers**: `tests/unit/interfaces/cli/test_target_project.py`,
  `tests/unit/core/flow/interfaces/test_run_model_flag.py`,
  `tests/unit/core/flow/interfaces/test_run_isolation_settings.py`,
  `tests/integration/interfaces/cli/test_runs_read_the_doc_policy.py`. Door tests that ran in an
  unregistered folder with an active project fail on decision 1 of SF-02; they are fixed by
  registering their folder.

## Decisions (Phase 4, user answered "all A" 2026-10-23)

1. The four read-only doors (`sw review`, `sw drift check`, `sw drift check-rot`,
   `sw standards scan`) ask the builder for no session isolation: one `RunRequest` field
   `read_only: bool = False`; per-step isolation still applies. A test lists exactly these four
   (design FR-3 updated) `[agreed 2026-10-23]`.
2. One CLI helper `run_one_step` builds the one-step pipeline, builds its run, runs it and returns
   the last step record `[agreed 2026-10-23]`.

## Approach (pseudocode, ordered)

**The CLI side of the builder** (`interfaces/cli/run_doors.py` [NEW])
1. `build_run_or_exit(project_path, spec_path, pipeline, *, models, selector, run_model, named)`:
   `project_for` → `RunRequest(ask=_core.spend_asker(), read_only=...)` → `build_run_sync`; `SettingsFileError`
   → `refuse_settings`; `UnknownProjectError` → print it, exit 1. A router it returns is wrapped by
   `_tell_missing_at_end`.
2. `run_one_step(project_path, spec_path, *, name, action, target, description, params, models)`
   → the last step record: `create_single_step` → `build_run_or_exit` → `PipelineRunner.run`.
3. `refuse_unstarted_worktree(err)`: a `RuntimeError` naming a worktree that could not start →
   print it, exit 1 (used by `sw implement` and `sw resume`; `sw run` already prints and exits 1).
4. `run_setup` (SF-02 module): `RunRequest.read_only`; when set, `_apply_isolation` skips the
   session policy and keeps the per-step one (decision 1).

**Doors** (each: delete its hand-built context, call 1 or 2, keep its own output)
4a. `sw run`: `build_run_or_exit(..., selector=selector, run_model=...)`; delete
   `_build_run_context`, `_wire_models`, `_apply_isolation_policy`, `attach_topology` call; then
   `_maybe_attach_provider(context)` as today.
5. `sw resume`: the run's `project_name` → `project_root_of` → None stops, naming the project and
   `sw init`; else build for that root (FR-5) with `selector="direct"` (the run does not record
   its selector). A worktree error is refused through 3.

> [!WARNING]
> A run parked **before** this change on a high-DAL project has no session worktree; its resume now
> asks for one and the engine raises "worktree is gone". `sw resume` refuses it cleanly through 3,
> naming the run; it does not traceback.
6. `sw implement`: build with `models="required"`; catch the worktree `RuntimeError` (3).
7. `sw review`, `sw draft`: build; `sw draft` attaches `HITLProvider` after the build. `sw draft`
   moves to `workflows/drafting/interfaces/cli.py` with `_build_draft_pipeline` and its report
   helpers; the command name stays (FR-11).
8. Read-only doors (decision 1) pass `read_only=True`. `sw drift check` (`models` "required" with `--analyze`, else "none"), `check-rot` (build once,
   one `spec_path` per file through `model_copy`), standards `_enrich_scope` (`models="optional"`,
   active project): through 2.
9. `apply_session_policy` docstring: every door escalates by DAL.

## Proposed Changes

| File | Change |
|---|---|
| `src/specweaver/interfaces/run_setup/builder.py` [MODIFY] | `RunRequest.read_only`; session policy skipped when set |
| `src/specweaver/interfaces/cli/run_doors.py` [NEW] | `build_run_or_exit`, `run_one_step`, `refuse_unstarted_worktree` |
| `src/specweaver/core/flow/interfaces/cli.py` [MODIFY] | `sw run`, `sw resume` on the builder; three helpers removed |
| `src/specweaver/workflows/implementation/interfaces/cli.py` [MODIFY] | on the builder; worktree refusal |
| `src/specweaver/workflows/review/interfaces/cli.py` [MODIFY] | `sw review` on `run_one_step`; `sw draft` moved out |
| `src/specweaver/workflows/drafting/interfaces/cli.py` [NEW] + `context.yaml` [NEW] | `sw draft` |
| `src/specweaver/assurance/validation/interfaces/cli_drift.py` [MODIFY] | both doors on `run_one_step` |
| `src/specweaver/assurance/standards/interfaces/cli.py` [MODIFY] | `_enrich_scope` on `run_one_step` |
| `src/specweaver/interfaces/cli/main.py` [MODIFY] | register `sw draft` from drafting |
| `src/specweaver/core/flow/engine/isolation.py` [MODIFY] | docstring only |
| `tach.toml` [MODIFY] | `workflows.drafting.interfaces`; `interfaces.run_setup` in the doors' `depends_on` |

## Test Plan

| FR | Tier | Test file | Cases (bucket) |
|---|---|---|---|
| FR-2 | integration | `tests/integration/interfaces/cli/test_cli_doors_build_alike.py` [NEW] | real DB and project (`CONSTITUTION.md`, `[docs]`, stored standards, DAL_B, git): `sw run`, `sw implement`, `sw review`, `sw draft`, `sw drift check`, `sw standards scan` each hand the runner a context with the rule file, standards, sections and session isolation (happy, the runner spied on only to capture the context); a broken `[sandbox]` refuses with exit 1 naming the key, no traceback (hostile); an unregistered folder refuses naming `sw init` (hostile); a pipeline with no model step needs no model settings (boundary) |
| FR-2 | integration | same file | `sw implement` on a DAL_B project with no git → exit 1, the worktree message, no traceback (degradation, SF-02 R1) |
| FR-4 | integration | same file | `sw implement` in project B while A is active → B's standards and settings (P-3) |
| FR-5 | e2e | `tests/e2e/capabilities/flow/test_resume_uses_runs_project.py` [NEW] | a run parked in project B, `sw resume <id>` from project A's folder → B's rule file and topology (happy, P-4); the recorded project removed → stops naming it (hostile) |
| FR-3 | integration | `tests/integration/interfaces/run_setup/test_build_run.py` [MODIFY] | `read_only` on a DAL_B project → no session isolation, per-step policy still on (boundary) |
| FR-3 | integration | `test_cli_doors_build_alike.py` | on a DAL_B project: `sw review`, `sw drift check`, `check-rot`, `sw standards scan` run with no session isolation; `sw run`, `sw implement`, `sw draft` with it — the list is exact (decision 1) |
| FR-5 | integration | same file | a run parked with no session worktree on a DAL_B project → `sw resume` exit 1 naming the run, no traceback (degradation) |
| FR-11 | integration | `tests/integration/workflows/drafting/interfaces/test_cli_draft.py` [NEW] | `sw draft` is registered from the drafting workflow and still runs (happy); the review CLI no longer defines it (boundary) |
| FR-11 | unit | `tests/unit/interfaces/cli/test_run_one_step.py` [NEW] | the helper builds one step with the given action, target and params and returns its last record; a run with no record gives None (boundary) |

Expected reds: every FR-2 case fails today on at least one part (`sw draft`: no rule file; `sw
review`: no isolation; `sw implement`: active project's standards, traceback); FR-5 fails on the
current folder's project; FR-11 fails until the move.

Mutants: a door drops the builder for a bare `RunContext` (FR-2); `sw resume` uses the current
folder (FR-5); the worktree `RuntimeError` not caught (FR-2); `run_one_step` drops `params` (FR-11);
`read_only` ignored by the builder (FR-3); `sw review` stops passing `read_only` (FR-3).

## Commit Boundaries

| CB | Tasks | Done when |
|---|---|---|
| CB-1 | `RunRequest.read_only`; `run_doors.build_run_or_exit`, `refuse_unstarted_worktree`; `sw run`, `sw resume` (FR-5 e2e) | green; FR-5 mutant killed; old helpers' tests moved |
| CB-2 | `sw implement` (worktree refusal), `sw review`, `sw draft` moved (FR-11) | green; FR-2/FR-4 cases for these doors |
| CB-3 | `run_one_step`; drift ×2, standards scan; docs. Closes SF-03: stops for the user's acceptance | green; every FR-2 mutant killed |

## Documentation

`docs/dev_guides/domain_driven_cli_creation.md` (a command that runs a pipeline builds it through
`run_doors`); `docs/dev_guides/pipeline_engine_guide.md` (every door escalates);
`docs/dev_guides/spec_rot_pre_commit_workflow.md` (the hook is a read-only door: no session worktree).

## Audit (Phase 2) — answered: all A, 2026-10-23

| # | Question | Options | Proposal | Severity |
|---|---|---|---|---|
| 1 | Session isolation wraps a whole run in a worktree, whatever its steps. On the builder, a high-DAL project gets it in **every** door, also the four that never write or run project code: `sw review`, `sw drift check`, `sw drift check-rot` (the git pre-commit hook — one worktree per staged file) and `sw standards scan`. On a high-DAL folder with no git, those four then stop. | A: those four ask the builder for no session isolation (one `RunRequest` field; a test lists the four). Per-step isolation still applies. B: every door isolates, as FR-3 says today. | A — nothing to bound in a read-only run; B makes the commit hook slow and breaks review on non-git folders | HIGH |
| 2 | FR-11's "one helper builds a one-step pipeline". `create_single_step` exists; the repeated part is pipeline + run + runner + last record, four times. | A: one CLI helper `run_one_step` does all four. B: keep `create_single_step` as the helper; each door keeps its own run lines. | A — removes the copies, not only the first line | LOW |

## Architecture Verification (Phase 3)

| Change | Module · archetype | I/O & state | Execution | LLM | Dependencies | Domain | Verdict |
|---|---|---|---|---|---|---|---|
| `interfaces/cli/run_doors.py` | `interfaces/cli` · adapter | builds runs | runs pipelines | none directly | + `interfaces.run_setup` | CLI delivery | ok |
| doors | their `*.interfaces` modules · interface | unchanged | unchanged | unchanged | + `interfaces.run_setup` | unchanged | ok |
| `workflows/drafting/interfaces/cli.py` | new `workflows.drafting.interfaces` · interface | as `sw draft` today | runs a pipeline | through the router | `core.flow`, `interfaces.cli`, `interfaces.run_setup` | drafting | ok |

No cycle: `run_setup` forbids `interfaces/cli` and `interfaces/api`; it depends on `core.flow`, not
on any `*.interfaces` module. The engine gains nothing (NFR-2).

## Consistency Check and Red/Blue (Phase 5)

- **Coverage**: FR-2 (CB-1..3, all eight doors), FR-5 (CB-1), FR-11 (CB-2 move, CB-3 helper). FR-3
  narrowed by decision 1 and tested door by door. FR-4 proven through `sw implement` (P-3). NFR-2:
  the engine changes only a docstring. NFR-3: doors map, the builder raises. NFR-4: existing door
  tests stay; those that relied on the active-project fallback register their folder. AD-3: no new
  error codes; the refusals are the existing `refuse_settings` and `print_error`.
- **Open questions**: none. All decisions are resolved and documented inline in the plan.
- **Handoff risk**: (a) the read-only list is exactly four doors; `sw draft` writes a spec, so it is
  isolated. (b) `sw run`'s `_maybe_attach_provider` and `sw draft`'s `HITLProvider` are attached
  after the build; the builder knows no console. (c) `check-rot` builds once and swaps `spec_path`
  per file — the plan path differs, the project does not.
- **Architecture**: every new link points from a `*.interfaces` module to `interfaces.run_setup`;
  `run_setup` gains one field. No cycle.
- **DDD/KISS/DRY/hexagonal/SoC**: one CLI helper maps builder errors; the doors keep their output.
- **Code detail limit**: no code block; pseudocode only.
- **Red/Blue**, 2 cycles:
  - R1 (HIGH) a run parked before this change resumes into a session worktree that does not exist.
    Blue: refused cleanly, naming the run (step 5, test added).
  - R2 (MEDIUM) a door could pass `read_only` for a writing pipeline. Blue: the door test fixes the
    list at four; a mutant drops it from `sw review`.
  - R3 (MEDIUM) `sw resume` gets `selector="direct"` though the run may have used another. Blue:
    accepted; the run records no selector, and resume had no topology at all before.
  - R4 (LOW) the standards scan now loads settings once per scope. Blue: a few scopes; the spend
    brake needs a fresh context per scope anyway.
  - Cycle 2: no new finding. Below every threshold.
