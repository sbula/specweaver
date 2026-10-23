# Implementation Plan: Project Settings Are Read Two Ways, and One Fails Open [SF-02: Every door stops on a broken setting]
- **Feature ID**: TECH-076
- **Sub-Feature**: SF-02 — Every door stops on a broken setting
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-076/TECH-076_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-076/TECH-076_sf02_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-4 (`sw run` / `sw resume`, the API run, resume and gate routes, the validation handler's DAL
merge) and FR-5 (every CLI command that loads project settings). Kind `bugfix`. Depends on SF-01
(committed `a1c24f2f`): `load_settings` now raises `SettingsFileError` for a broken `[sandbox]`,
`[standards]` or `dal_definitions.yaml`. NFR-1, NFR-3 apply.

## Research Notes

- **CLI run root** (`core/flow/interfaces/cli.py`): `_build_run_context` (`:244-290`) reads
  `[docs]`, `[autonomy]`, `[implement]` first through `_core.load_*_at`, which already refuse with
  exit 1, so a TOML syntax error stops there. Then `_apply_isolation_policy` (`:318-340`) calls
  `load_settings` inside `except Exception` and returns with isolation off (the hole). `_wire_models`
  (`:296-315`) calls `load_settings` with no handler for pipelines whose steps use a model.
  `sw run` and `sw resume` both go through `_build_run_context`.
- **API** (`interfaces/api/v1/pipelines.py`): `start_pipeline_run` (`:126-190`) and
  `_resume_existing_run` (`:48-75`, used by resume and gate answers) build the context with
  `project_policy(project_root)` first (refuses `DOC_POLICY` / `AUTONOMY_POLICY` /
  `IMPLEMENT_POLICY` 500, so a syntax error stops there), then `await _apply_isolation(...)`
  (`:104-123`), which catches every exception and returns (the hole). The run starts after it, so a
  raise in `_apply_isolation` starts no run. Error shape: `SpecWeaverAPIError(detail, error_code,
  status_code)` as in `run_settings.py:39-58`.
- **Error to code** (decision 6 and Q7 of the design): key `sandbox` or `sandbox.*` → `SANDBOX_SETTINGS`,
  `standards` or `standards.*` → `STANDARDS_SETTINGS` (a whole table of the wrong type has the bare name), a source ending in `dal_definitions.yaml` →
  `DAL_DEFINITIONS`. A `(syntax)` key in `specweaver.toml` cannot reach `_apply_isolation` (the
  policy read above refuses it first); see audit #1.
- **Validation handler** (`core/flow/handlers/validation.py:52-72`): `_resolve_merged_settings`
  catches every exception while layering the tier and returns the unmerged settings. Both callers
  (`ValidateSpecHandler.execute :164`, `ValidateCodeHandler.execute :258`) already wrap it in
  `except Exception → _error_result(str(exc), started)`, so letting the error out of
  `_resolve_merged_settings` makes the step an ERROR with the message, and the run stops there.
- **Other `load_settings` callers with no handler** (FR-5): `workflows/implementation/interfaces/cli.py:275`,
  `workflows/review/interfaces/cli.py:198, 292`, `assurance/standards/interfaces/cli.py:163`,
  `assurance/validation/interfaces/cli_drift.py:95`, `core/flow/interfaces/cli.py:314` (`_wire_models`).
  Every one of these modules already imports `_core`.
- **CLI refusal**: `_core.refuse_llm_settings(err) -> NoReturn` prints `Error: <message>` (no markup,
  never cut) and exits 1. SF-03 renames it (FR-8); SF-02 uses it as it is.
- **e2e pattern**: `tests/e2e/capabilities/core/test_agentic_without_a_ceiling_e2e.py`
  (`CliRunner`, `sw init`, then `sw run <pipeline> <spec> --project`, `_mock_db` fixture,
  `tests.rendering.shows`).

## Decisions (Phase 4, user answered "all A" 2026-10-23)

1. A `(syntax)` error in `specweaver.toml` reaching `_apply_isolation` maps to `SANDBOX_SETTINGS`.
2. A failed DAL merge makes the validation step an ERROR naming the tier; the run stops there.

## Approach (pseudocode, ordered)

**FR-5 — one CLI helper first** (the doors below use it)
1. `_core.load_project_settings(db, project) -> SpecWeaverSettings`: `load_settings(db, project)`;
   on `SettingsFileError` → `refuse_llm_settings(err)`. Other errors pass through unchanged.
2. Replace the bare `load_settings(...)` in the six CLI callers listed above with it.

**FR-4 — the run doors**
3. CLI `_apply_isolation_policy`: catch `SettingsFileError` first and refuse (exit 1 with the
   message); keep the existing best-effort `except Exception` for anything else (decision 5 of the
   design).
4. API `_apply_isolation`: catch `SettingsFileError` first and raise `SpecWeaverAPIError(detail=str(exc),
   error_code=<code by key/source>, status_code=500)`; keep the best-effort catch for anything else.
   Resume and gate answers share `_resume_existing_run`, so they are covered by the same line.
5. `_resolve_merged_settings`: drop the catch-all; let the error reach the handler's existing
   `_error_result`, with a message naming the tier (`cannot apply the DAL_X rules: …`).

## Proposed Changes

| File | Change |
|---|---|
| `src/specweaver/interfaces/cli/_core.py` [MODIFY] | `load_project_settings` |
| `src/specweaver/core/flow/interfaces/cli.py` [MODIFY] | `_apply_isolation_policy` refuses a settings error; `_wire_models` uses the helper |
| `src/specweaver/interfaces/api/v1/pipelines.py` [MODIFY] | `_apply_isolation` maps a settings error to 500 with its code |
| `src/specweaver/core/flow/handlers/validation.py` [MODIFY] | `_resolve_merged_settings` stops on a merge failure |
| `src/specweaver/workflows/implementation/interfaces/cli.py`, `workflows/review/interfaces/cli.py`, `assurance/standards/interfaces/cli.py`, `assurance/validation/interfaces/cli_drift.py` [MODIFY] | use the helper |

## Test Plan

| FR | Tier | Test file | Cases (bucket) |
|---|---|---|---|
| FR-4 | e2e | `tests/e2e/capabilities/core/test_broken_sandbox_stops_the_run_e2e.py` [NEW] | P-1: `sw init`, `[sandbox]` `execution_mod = "container"`, `sw run validate_only specs/a_spec.md` → exit 1, output names `specweaver.toml:<line>: sandbox.execution_mod`, no run recorded (hostile); a valid `[sandbox]` runs (happy). Red today: the run starts with isolation off |
| FR-4 | integration | `tests/integration/interfaces/api/test_api_broken_settings_refuse.py` [NEW] | P-2: real app + token; broken `[sandbox]` → 500 `SANDBOX_SETTINGS`, the message names file, key, line, no run row (hostile); broken `[standards]` → `STANDARDS_SETTINGS`; broken DAL file → `DAL_DEFINITIONS`; resume of a parked run on a project broken after it parked → 500 `SANDBOX_SETTINGS` (boundary); valid → 200 (happy). Red today: 200 |
| FR-4 | unit | `tests/unit/core/flow/handlers/test_validation_dal_merge_stops.py` [NEW] | the merge raising (forced) → the step is ERROR naming the tier, never PASSED on the unmerged rules (degradation); a tier merges (happy); no tier for the target (boundary). Red today: PASSED |
| FR-5 | integration | `tests/integration/interfaces/cli/test_cli_broken_settings_refuse.py` [NEW] | P-3, P-4: `sw implement`, `sw review`, `sw standards scan`, `sw drift`, and `sw run` with a model step, each on a broken `[sandbox]` or DAL file → exit 1, the located message, no traceback (hostile). Red today: a traceback (SF-01 interim) |

Mutants to write to `TECH-076_mutants.json`:
- FR-4: CLI `_apply_isolation_policy` returns on a settings error; API `_apply_isolation` returns on
  it; the code mapping always answers `SANDBOX_SETTINGS`; `_resolve_merged_settings` keeps the
  catch-all.
- FR-5: `load_project_settings` re-raises instead of refusing.

## Commit Boundaries

| CB | Tasks | Done when |
|---|---|---|
| CB-1 | FR-5 helper + the six CLI callers; FR-4 CLI run root. e2e and CLI integration written first, red | e2e + integration green; FR-5 and CLI FR-4 mutants killed |
| CB-2 | FR-4 API (`_apply_isolation`, code mapping) and the validation handler. Closes SF-02: stops for the user's acceptance | integration + unit green; FR-4 mutants killed |

## Documentation

REST API docs where error codes are listed (if any) gain the three codes; `1_installation_and_setup.md`
(API bullet): a run on a project with a broken setting answers 500 naming the setting.

## Audit (Phase 2) — answered: all A, 2026-10-23

| # | Question | Options | Proposal | Severity |
|---|---|---|---|---|
| 1 | A TOML syntax error in `specweaver.toml` names no section. It cannot reach `_apply_isolation` today (the `[docs]` read before it refuses with `DOC_POLICY`), but the mapping needs an answer if the order ever changes. | A: map it to `SANDBOX_SETTINGS` (the isolation read is what failed). B: reuse `DOC_POLICY`. | A — the code says which read stopped the run | LOW |
| 2 | The validation handler on a failed DAL merge. | A: the step is an ERROR naming the tier (the handlers' existing error path); the run stops there. B: raise out of the runner. | A — same path every handler error takes | LOW |

## Architecture Verification (Phase 3)

| Change | Module · archetype | I/O & state | Execution | LLM | Dependencies | Domain | Verdict |
|---|---|---|---|---|---|---|---|
| CLI helper and callers | `interfaces/cli`, domain `interfaces/` · delivery | none new | none | none | `core.config` (already) | refusals | ok |
| API mapping | `interfaces/api` · delivery | none new | none | none | `core.config.settings_file` (already imported by `run_settings.py`) | HTTP mapping | ok |
| validation handler | `core/flow/handlers` · orchestrator | none | none | none | none new | validation | ok |

No new module edge, no cycle, no `tach.toml` change. No CRITICAL architecture finding.

## Consistency Check and Red/Blue (Phase 5)

- **Coverage**: FR-4 (CLI in CB-1; API and the validation handler in CB-2), FR-5 (CB-1). NFR-1: no
  settings error leads to a run with isolation off or to rules not applied. NFR-3: the message is
  the error's own `source:line: key: message`.
- **Open questions**: none. All decisions are resolved and documented inline in the plan.
- **Handoff risk**: keep the best-effort `except Exception` for non-settings errors in both
  isolation functions (design decision 5) — catch `SettingsFileError` before it, not instead of it.
- **Architecture**: no new edge; every touched CLI module already imports `_core`.
- **DDD/KISS/DRY/hexagonal/SoC**: one CLI helper for six call sites; one mapping function for the
  API codes; the handler reuses its error path.
- **Code detail limit**: no code block; steps are pseudocode.
- **Red/Blue**, 2 cycles:
  - R1 (MEDIUM) `refuse_llm_settings` raises `typer.Exit`, a `RuntimeError` in click; an outer
    `except Exception` in `sw run` could catch it. Blue: the e2e asserts exit 1 and the located
    message; dev checks the outer handler re-raises `typer.Exit`.
  - R2 (LOW) a table of the wrong type (`sandbox = 1`) has the key `sandbox` with no dot. Blue:
    fixed in the mapping note (bare name matches too).
  - R3 (LOW) project-not-found and other errors keep today's best effort. Blue: design decision 5.
  - Cycle 2: no new finding. Below every threshold.
