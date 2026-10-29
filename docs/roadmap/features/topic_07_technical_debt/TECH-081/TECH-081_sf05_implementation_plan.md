# Implementation Plan: The Layer Check Reports Clean While the Layers Are Broken [SF-05: The CLIs stop importing the shell]
- **Feature ID**: TECH-081
- **Sub-Feature**: SF-05 — The CLIs stop importing the shell
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-05
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_sf05_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-15: no domain CLI imports `interfaces/cli`. The shared helpers move to `interfaces/cli_kit`, the
run doors to `interfaces/run_doors`; only the shell imports the domain CLIs (AD-9). `hitl_provider`
stays in the shell and reaches `sw draft` by injection, as `set_context_provider_factory` already
does for `core/flow`. The 10 `deprecated` edges `<domain>.interfaces → interfaces.cli` and their
ledger rows go. No command, option or output changes (NFR-1); no `deprecated` edge added (NFR-2);
one home per symbol (NFR-3).

## Research Notes

Read 2026-10-29.

- **What the domain CLIs take from the shell** (grep of `from specweaver.interfaces.cli` outside
  the shell):

  | Domain module | `_core` | `run_doors` | `hitl_provider` | Edge goes in |
  |---|---|---|---|---|
  | `graph.interfaces` | yes (+ `console`, `get_db` by name) | — | — | CB-1 |
  | `core.config.interfaces` (`cli.py`, `llm_show.py`) | yes | — | — | CB-1 |
  | `infrastructure.llm.interfaces` (`cli.py`, `command.py`, `settings_show.py`) | yes | — | — | CB-1 |
  | `workspace.project.interfaces` (`cli.py`, `cli_hooks.py`, `cli_constitution.py`) | yes | — | — | CB-1 |
  | `assurance.standards.interfaces` | yes | `run_one_step` | — | CB-2 |
  | `assurance.validation.interfaces` (`cli.py`, `cli_drift.py`) | yes | `run_one_step` | — | CB-2 |
  | `core.flow.interfaces` (`cli.py`, `resume_policy.py`, `run_summary.py`) | yes | several | — | CB-2 |
  | `workflows.implementation.interfaces` | yes | `build_run_or_exit`, `refuse_unstarted_worktree` | — | CB-2 |
  | `workflows.review.interfaces` | yes | `build_run_or_exit` | — | CB-2 |
  | `workflows.drafting.interfaces` | yes | `build_run_or_exit`, `refuse_unstarted_worktree` | `HITLProvider` (`cli.py:173`) | CB-3 |

  `cli_hooks.py:29` names `-m specweaver.interfaces.cli.main` in a hook script: the entry point,
  not an import; it stays.
- **`interfaces/cli/_core.py`** (225 lines): `app` (the root `sw` Typer) and `_version_callback`
  are the shell's own; only `main.py` uses them. Everything else is shared: `console`, `get_db`,
  `run_repo_op`, `_require_active_project`, `project_root`, `existing_project_root_or_exit`,
  `registered_project_at`, `load_section_at`, `project_sections_at`, `file_or_exit`,
  `project_path_or_exit`, `load_active_llm_settings`, `print_error`, `refuse_settings`,
  `stdin_is_interactive`, `ask_to_spend`, `spend_asker`. Imports: `core.config.bootstrap`
  (`get_db`), `workspace.project.discovery`, lazy `workspace.store`, `core.config.*`.
  Its docstring: callers import the module, not names, so `monkeypatch.setattr("…_core.get_db")`
  works. Tests patch `interfaces.cli._core.get_db` (33), `run_repo_op` (15),
  `stdin_is_interactive` (4), `resolve_project_path` (4); 38 test files name `_core`, `run_doors`
  or `hitl_provider` by path.
- **`interfaces/cli/run_doors.py`** (128 lines): `build_run_or_exit`, `run_one_step`,
  `refuse_unstarted_worktree`, `recorded_project_root`, `_say_no_model`. Imports `_core`, lazy
  `interfaces.run_setup.builder`, `infrastructure.llm.interfaces.command.tell_missing_at_end`,
  `core.flow.engine.*`, `core.flow.handlers.registry`, `workspace.store`.
- **`hitl_provider.py`**: `HITLProvider(console=…)`, a `ContextProvider` over Rich prompts; imports
  only `rich` and `workspace.context.provider`. `sw draft` sets it unconditionally
  (`drafting/interfaces/cli.py:179`). The shell's `_interactive_context_provider` (`main.py`) gives
  `core/flow` one only on a TTY, through `set_context_provider_factory` (`core/flow/interfaces/cli.py:53`).
  Tests patch `specweaver.interfaces.cli.hitl_provider.HITLProvider` and run the shell `app`
  (`test_lifecycle.py:242`, `test_drafter_loop_e2e.py:233`).
- **tach**: `interfaces.cli` depends on every domain CLI and on `run_setup`. Each of the 10 domain
  CLIs carries `{ path = "specweaver.interfaces.cli", deprecated = true }`. The ledger table "Owed by
  TECH-081" holds exactly those 10 rows (`known_boundary_violations.md:26-35`);
  `test_tach_sees_every_module` keeps the two equal. Layout: `interfaces/run_setup/` is a directory
  module with `context.yaml` and no `__init__.py` (the repo uses namespace packages).
- **Import order is a DAG**: `cli_kit` imports no CLI. `infrastructure.llm.interfaces` imports
  `cli_kit` only. `run_doors` imports `cli_kit`, `llm.interfaces`, `run_setup`, `core.flow.*`;
  nothing it imports imports `run_doors`. Domain CLIs import `cli_kit` and `run_doors`. The shell
  imports all of them.
- **Proof of FR-15 today**: none cites it. `tach check` (the `[FAIL]` gate) plus the ledger test are
  the check once the edges go; a mutant proves they see a domain CLI importing the shell again.
- **Guide**: `docs/dev_guides/domain_driven_cli_creation.md` shows
  `from specweaver.interfaces.cli._core import get_db, _require_active_project` (design doc table:
  ⬜ SF-05).

## Approach (pseudocode, ordered)

**CB-1 — the shared helpers move to `interfaces/cli_kit`** — kind `refactor` (a non-path test edit makes it `tooling`, Q1 `[agreed 2026-10-29]`)
1. Red: `tach.toml` registers `specweaver.interfaces.cli_kit` (`depends_on` `core.config`,
   `core.config.bootstrap`, `workspace`, `workspace.project`); delete the `deprecated` shell edge
   from `graph.interfaces`, `core.config.interfaces`, `infrastructure.llm.interfaces`,
   `workspace.project.interfaces`. Tach red on their `_core` imports.
2. Green: `git mv interfaces/cli/_core.py interfaces/cli_kit/_core.py`. The file keeps its name, so
   every `_core.<name>` call stays as it is and the test edits are path strings only. `app` and
   `_version_callback` move out of it into `interfaces/cli/main.py` (shell-only, NFR-3). Every
   `from specweaver.interfaces.cli import _core` becomes `from specweaver.interfaces.cli_kit import
   _core` (all callers, the shell's own files and `run_doors.py` included); `graph/interfaces/cli.py`'s
   by-name import likewise. Tests: patch strings re-pointed; a unit test whose subject is a `_core`
   function moves to `tests/unit/interfaces/cli_kit/` (`git mv`); a test that runs `sw` stays.
   The four modules depend on `interfaces.cli_kit` (prune with tach's unused report); manifests:
   `interfaces/cli_kit/context.yaml` (archetype `adapter`: it opens the database and prints), the
   four consumers add `specweaver/interfaces/cli_kit`. Ledger: 4 rows go.

**CB-2 — the run doors move to `interfaces/run_doors`** — kind `refactor` (a non-path test edit makes it `tooling`, Q1 `[agreed 2026-10-29]`)
3. Red: register `specweaver.interfaces.run_doors` (`depends_on` `interfaces.cli_kit`,
   `interfaces.run_setup`, `infrastructure.llm.interfaces`, `core.config`, `core.flow.engine`,
   `core.flow.handlers`, `core.flow.run_state`, `workspace`); delete the shell edge from
   `assurance.standards.interfaces`, `assurance.validation.interfaces`, `core.flow.interfaces`,
   `workflows.implementation.interfaces`, `workflows.review.interfaces`. Tach red.
4. Green: `git mv interfaces/cli/run_doors.py interfaces/run_doors/doors.py`; callers import
   `specweaver.interfaces.run_doors.doors`. Tests re-pointed (paths); unit and integration tests whose
   subject is a door move to `tests/{unit,integration}/interfaces/run_doors/`. Manifest
   `interfaces/run_doors/context.yaml` (archetype `orchestrator`: it builds and runs pipelines).
   Ledger: 5 rows go.

**CB-3 — `sw draft` gets its channel from the shell (FR-15)** — kind `tooling` — closes SF-05
5. Red: a unit test in `tests/unit/workflows/drafting/interfaces/`: `sw draft` attaches the provider
   the registered factory returns; with no factory registered it attaches none. Fails: no setter.
   Delete the last shell edge (`workflows.drafting.interfaces`); tach red on `cli.py:173`.
6. Green: `drafting/interfaces/cli.py` gains `set_hitl_provider_factory(factory | None)`, the same
   shape as `core/flow`'s setter; `sw draft` calls the factory per run. `main.py` registers a
   factory that imports `hitl_provider.HITLProvider` at call time and returns
   `HITLProvider(console=console)` (no TTY check: `sw draft` is interactive today, NFR-1; the call-time
   lookup keeps the existing `HITLProvider` patches working). The ledger's "Owed by TECH-081" table
   is empty; the section says so.
7. Docs: `domain_driven_cli_creation.md` imports from `cli_kit` and `run_doors`; the design's doc row
   ✅. `interfaces/cli/context.yaml` exposes no `console`/`get_db` (they live in `cli_kit`).
8. Mutants (FR-15 campaign, corpus `TECH-081`): `cli-imports-shell-again` (a CB-1 module imports
   `interfaces.cli.main` → tach red); `door-back-in-shell` (`review` imports a name from
   `interfaces.cli` → tach red); `draft-loses-its-channel` (the shell's `set_hitl_provider_factory`
   call removed → the e2e and the new test red).

## Test Plan

| Tier | Test | Proves | Red first because |
|---|---|---|---|
| arch | `test_tach_architectural_boundaries` | FR-15 (no domain CLI → shell) | each boundary deletes the edges first |
| arch | `test_tach_sees_every_module` | FR-15, FR-5 (ledger = deprecated edges) | rows and edges go together |
| unit | `sw draft` uses the registered factory; none registered → no provider | FR-15 (AD-9 injection) | no setter exists |
| e2e | `test_lifecycle.py`, `test_drafter_loop_e2e.py` (existing) | NFR-1: `sw draft` still asks | — (kept green) |
| all | the suite | NFR-1 | — |

## Commit Boundaries

| CB | Holds | Done when |
|---|---|---|
| CB-1 | steps 1–2 | suite green; 4 edges and rows gone; commit |
| CB-2 | steps 3–4 | suite green; 5 edges and rows gone; commit |
| CB-3 | steps 5–8 | suite green; ledger table empty; three mutants killed; stage and stop (closes SF-05) |

## Documentation

`docs/dev_guides/domain_driven_cli_creation.md` (step 7). Other `docs/dev_guides/` mentions of
`interfaces/cli/_core` or `run_doors` re-pointed (grep in dev). No user-facing change.

## Architecture Verification (Phase 3)

- `interfaces/cli_kit` (`adapter`): database session, console output, settings files. No LLM, no
  process. Depends on `core.config`, `workspace`; nothing it imports reaches a CLI.
- `interfaces/run_doors` (`orchestrator`): builds a run through `run_setup` and runs one pipeline;
  same mechanisms as today, one level out of the shell. No loop: `run_setup` and `core.flow` do not
  import it.
- Zoom-out: `interfaces/run_setup` builds runs for both CLI and API; the doors are the CLI's
  error-to-exit wrapper around it, so they stay a separate module (AD-9), not part of `run_setup`.
- No `deprecated` edge added; 10 removed.

## Audit (Phase 2)

❓ **Q1 — CB kinds.** CB-1 and CB-2 change only import paths and move test files. If a test needs
more than a path edit (as `test_logging_rollout.py` did in SF-07), the `refactor` gate blocks it.
- **A:** CB-1 and CB-2 run `refactor`; a boundary that needs a non-path test edit runs `tooling`
  and says so in the design's kind line, as SF-07 did.
- **B:** all three run `tooling` from the start.

The user chose A `[agreed 2026-10-29]`.

Settled without a question (mine to take, recorded for review):
- File names: `cli_kit/_core.py` keeps its name so the 335 `_core.x` uses in `src` and the test patches change
  only their path; `run_doors/doors.py`.
- `app` and `_version_callback` stay in the shell (`main.py`).
- `sw draft` with no factory registered attaches no provider (only a test that calls
  `drafting_cli` without the shell can reach that).

## Consistency (Phase 5)

- Coverage: FR-15 (all three CBs), NFR-1 (suite and the two draft e2es), NFR-2 (no edge added, 10
  removed), NFR-3 (`app` only in the shell; each moved file has one home), AD-9 (both modules and the
  injection), FR-5 (ledger rows go with their edges). Design doc row `domain_driven_cli_creation.md`
  in step 7. The design's kind line gains "SF-05 CB-3, which adds the draft-factory test".
- Import chains: shell → domain CLIs → `run_doors` → `cli_kit`; `run_doors` → `llm.interfaces` →
  `cli_kit`; `run_doors` → `run_setup`, `core.flow`. None of the lower ones imports a higher one.
- Red/Blue, 2 cycles:
  - R1 (MEDIUM) the drafting setter is module state; a test that sets it can leak into the next test
    in the same worker. Blue: the new test resets it with `set_hitl_provider_factory(None)` in a
    fixture, as `test_main_provider_factory.py` does for `core/flow`.
  - R2 (MEDIUM) `core/flow` swallows a factory error; `sw draft` would not. Blue: deliberate. A draft
    needs its channel, and today a broken `HITLProvider` fails the command too (NFR-1). The plan
    keeps no `try`.
  - R3 (MEDIUM) the factory must look up `HITLProvider` when called, or the tests that patch
    `specweaver.interfaces.cli.hitl_provider.HITLProvider` stop seeing their double. Blue: step 6
    says so; the two e2es fail if it is wrong.
  - R4 (MEDIUM) the shell's own `depends_on` must gain `interfaces.cli_kit` and
    `interfaces.run_doors`, or tach fails on `main.py` and the routers. Blue: added in the same
    step as each module; tach is the check.
  - R5 (LOW) `interfaces/cli/context.yaml`'s "Contract" comment names `_core`. Blue: re-pointed in
    CB-1 with the move.
  - R6 (LOW) a moved test file lands in a new folder (`tests/unit/interfaces/cli_kit/`). Blue: `git
    mv` is a rename, which the refactor gate accepts (SF-07 CB-1 did the same).
  - Cycle 2: no new finding.
- All decisions are resolved and documented inline in the plan.
