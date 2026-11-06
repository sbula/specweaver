# Walkthrough: TECH-079 SF-02 — Every caller asks it

## CB-1: the run carries the profile; the refusal reaches the doors (FR-7 run part, FR-8)

**What changed**
- `IsolationPolicy.language` (the pin only) is gone. The run carries `profile: ProjectProfile | None`
  and `undecided: str | None`; the run builder sets one of them with both `[implement]` pins.
- `core/flow/engine/run_language.py` → `run_profile.py`: `run_profile(context)` returns the profile,
  raises `ProjectUndecidedError` with the stored message, or, for a context nobody decided for (one
  a test built), decides from the root with no pins and keeps it. `run_task_files` uses it. The new
  edge `core.flow.engine → workspace.project` is in tach and `context.yaml` (AD-2).
- `derive_allowed_paths(spec, root, language)`: all required; the `python` branch is gone.
- Doors: `RunRequest.needs_profile`; `sw run` and resume, `POST /pipelines/{name}/run` and resume
  pass it (Q2 `[agreed 2026-11-06]`). `build_run_or_exit` prints a refusal and exits 1;
  `build_api_run` answers 400 `PROJECT_UNDECIDED`, from any door.
- Q1 `[agreed 2026-11-06]`: `apply_session_policy` raises the refusal past its best-effort guard
  when session isolation is on (set, or by DAL) and no allow-list is configured.
- Not in the plan, taken at dev: `sw implement` builds the run first and takes its task files from
  `run_task_files`, so it decides once and needs no `workspace.project` import; the plan's door-side
  `read_project_profile` was not needed. `cli_kit._core.project_sections_at` lost its last caller
  and was deleted with its two tests. `POST /implement` decides at the door (plan F3).
- Found by red/blue: a registered folder removed since registration crashed the builder with an OS
  traceback; the builder now keeps a refusal naming the folder.

**What a user sees.** A fresh `sw init` project has no build file, so `sw run` and `sw implement`
refuse with "the project root has no build file and no code file; set [implement] language in
specweaver.toml" until it has one or the setting. This follows FR-3/FR-5 as agreed; §6c says it.

**Tests**
- Red first: `tests/unit/core/flow/engine/test_run_profile.py` (replaces `test_run_language.py`),
  `tests/integration/interfaces/run_setup/test_run_carries_the_profile.py`,
  `tests/integration/interfaces/cli/test_cli_refuses_an_undecided_project.py`,
  `tests/integration/interfaces/api/test_api_refuses_an_undecided_project.py` (red: no module, or
  the run started).
- NFR-1: 118 test files built project folders with no build file and leaned on the Python default;
  each now writes the build file its test means (mostly `pyproject.toml`, `tsconfig.json` beside
  `package.json`) or a pinned profile. No assertion was loosened; the removed `assert` lines are the
  ones rewritten for the profile. Seven QA-atom expectations of `language=None` now expect the run's
  `"python"`. The scenario e2e pins `[implement] language` instead of a pyproject, because a
  pyproject makes the sandbox build the toy project.
- Mutants, each OBJECTED: `run-profile-ignores-undecided`, `needs-profile-ignored`,
  `session-policy-swallows-undecided`, `isolation-python-default`, `cli-door-shows-a-traceback`,
  `api-resume-runs-undecided`, `api-door-answers-500`.
- NFR-5: 58 mutants in 19 corpora pointed at changed functions; 20 anchors were rewritten to the new
  code with the same claim (`TECH-081` FR-14 now probes a private import in `run_profile`), all
  re-pinned; `stale_mutants.py` reports none.

**Gap analysis (Phase 2)**

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `run_profile`, `run_task_files` | ✅ | ✅ | — |
| `derive_allowed_paths`, `apply_session_policy` (Q1) | ✅ | ✅ | — |
| strip-merge allow-list language | — | ✅ (one test; probe objected) | — |
| `builder._profile` (pins, undecided, needs, unreadable root) | — | ✅ | — |
| `build_run_or_exit` refusal, any door | — | ✅ (added) | — |
| `build_api_run` refusal, any door | — | ✅ (added) | — |
| API resume refusal | — | ✅ (added) | — |
| `implement._task_files` refusal | — | ✅ | — |

Composition: builder → `run_profile` → task files and allow-list in one test
(`test_a_pinned_mixed_root_carries_the_pin_everywhere`). Agreement: the task files and the QA runner
name one language (`test_run_profile_agrees_with_qa.py`). The journey e2e for P-1/P-3 lands with
CB-2, when every part takes the run's language.

**Red/blue**
- Fixed: the unreadable-root traceback above.
- Accepted: `sw implement` and `POST /implement` read the root at the door and again in the builder
  (two listings); NFR-4's "a run decides once" holds.
- Accepted: `run_profile`'s fallback stores its answer with `model_copy`; inside a step copy it does
  not reach the original. Only test-built contexts take it.
- Accepted: a context nobody decided for whose folder does not exist raises the OS error; the
  builder, the only `RunContext` in `src`, never leaves one undecided.
