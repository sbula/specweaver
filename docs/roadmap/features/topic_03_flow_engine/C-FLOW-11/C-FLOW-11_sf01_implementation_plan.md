# Implementation Plan: Graduated Autonomy [SF-01: The project's policy]
- **Feature ID**: C-FLOW-11
- **Sub-Feature**: SF-01 — The project's policy
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/C-FLOW-11/C-FLOW-11_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_03_flow_engine/C-FLOW-11/C-FLOW-11_sf01_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-20

**FRs owned**: FR-1, FR-2, FR-6, FR-7 · **NFRs**: NFR-1, NFR-2 · **Depends on**: none
(`C-EXEC-08` ✅ supplies the strict `specweaver.toml` reader and the run-root wiring this reuses)

## Shape

| Piece | Where | Tag |
|---|---|---|
| `AutonomyPolicy(mode: "oneshot" \| "agentic" = "oneshot", agentic_max_dal: DALLevel \| None = None)`, strict; `parse_autonomy(text, source)` raising `SettingsFileError` with the key and line, as `parse_doc_policy` does | `core/config/autonomy_policy.py` | NEW |
| `load_autonomy(project_root)` through `read_settings_text` | `core/config/bootstrap/` beside `doc_policy_loader.py` | NEW |
| `IsolationPolicy.autonomy: AutonomyPolicy` (default: the empty policy) replaces `autonomy: Any` | `core/flow/handlers/run_context.py` | MODIFY |
| The run roots pass it where they pass the doc policy: `sw run`/`sw resume` (`_build_run_context`), `sw implement`, the API's start and resume (`_doc_policy` → one helper returning both). A broken `[autonomy]` stops the command, naming the line; the API answers `error_code="AUTONOMY_POLICY"`, status 500, as `DOC_POLICY` does | `core/flow/interfaces/cli.py`, `interfaces/cli/_core.py`, `workflows/implementation/interfaces/cli.py`, `interfaces/api/v1/pipelines.py` | MODIFY |
| `apply_isolation_policy` stops copying `settings.autonomy`; `AutonomySettings` and `SpecWeaverSettings.autonomy` go — never read from any file, so nothing a user wrote is lost | `core/flow/engine/isolation.py`, `core/config/settings.py` | MODIFY / DELETE |
| At load: an unknown `mode`, or `mode: agentic` on any step but `generate` with target `code` or `tests`, is a pipeline error naming the step (FR-7) | `PipelineDefinition.validate_flow` (`core/flow/engine/models.py`) | MODIFY |
| At run start: a `generate` step whose mode resolves to `agentic` (its own, else the project's) with no `agentic_max_dal` refuses the run, naming `[autonomy] agentic_max_dal` in `specweaver.toml` (FR-2) | `core/flow/engine/security.py` beside `verify_doc_blocks`; called by `run` and `resume` | MODIFY |
| `resolve_execution_mode` returns the mode and, when it refused `agentic`, why ("agentic refused: DAL_B is above the ceiling DAL_D") — SF-02 puts that reason in the step's result (Q1). The project's `mode` applies to `generate code` and `generate tests` steps only; the built-in `DAL_D` goes | `core/flow/engine/autonomy.py` | MODIFY |

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | `AutonomyPolicy`, the parser, the loader; the roots carry it; the old install setting goes | FR-6, NFR-2 (broken file) | `[autonomy]` in `specweaver.toml` is ignored today |
| CB-2 | load-time refusal; run-start refusal; resolution | FR-1, FR-2, FR-7, NFR-1 | `mode: agentic` on a `review` step loads today; an unset ceiling is read as `DAL_D` |

| CB | Tier | Test |
|---|---|---|
| CB-1 | unit | each key, its refusal and line; an absent section is the empty policy |
| CB-1 | integration | `_build_run_context`, `sw implement` and the API's start and resume carry a project's `[autonomy]`; a broken one stops each, naming the line (extends `test_runs_read_the_doc_policy.py` and its API twin) |
| CB-2 | unit | resolution: step mode wins; else project mode for `generate code`/`tests` only; DAL at, below and above the ceiling, the reason named above it; load refusals for an unknown mode and for `agentic` on `review`, `draft`, `bash`, `generate contract` and `generate scenario` |
| CB-2 | integration | a run whose `generate` step asks `agentic` with no ceiling is refused before any step, naming the setting; with no `mode: agentic` anywhere the run is unchanged (NFR-1) |
| CB-2 | e2e | `sw run` of a pipeline with an agentic `generate` step on a project without `agentic_max_dal`: exit 1, the setting named, no step ran |

## Mutants (into `C-FLOW-11_mutants.json`)

| CB | Neutralise | Killed by |
|---|---|---|
| CB-1 | a root drops the policy; an unknown key accepted | CB-1 tests |
| CB-2 | the non-generate refusal; the unset-ceiling refusal; the project mode applied to every step; the DAL comparison (existing `dal-ignored`, re-anchored) | CB-2 tests |

## Research Notes

- `resolve_execution_mode(step_def, context)` and `_requested` (`core/flow/engine/autonomy.py:37-82`)
  read `isolation.autonomy` with `getattr` and fall back to `DAL_D`; an unknown mode raises only at
  resolution, which no production code calls yet.
- `AutonomySettings` (`core/config/settings.py:92-111`) is reached only through
  `SpecWeaverSettings.autonomy`; `settings_loader.py` never reads `[autonomy]` from a file, so the
  setting has only ever had its built-in values.
- `apply_isolation_policy` copies it best-effort (`isolation.py:78-95`); the doc policy is loaded
  strictly beside it by every root (`C-EXEC-08` SF-02), which this plan follows.
- `PipelineStep.mode: str | None` (`models.py:246-248`); `validate_flow` (`models.py:325-399`)
  already collects per-step errors, e.g. `bash_param_errors`.
- The run's DAL is always set before the first step (`seed_dal_level`, `runner.py:102`), so the
  "DAL unresolved" branch is a guard, not a path.
- Existing tests that change: `tests/unit/core/flow/engine/test_autonomy_dial.py`,
  `test_autonomy_settings.py`, `test_autonomy_policy_seam.py`,
  `tests/integration/core/flow/engine/test_autonomy_policy_integration.py` — they build the old
  install setting. The corpus's `dal-ignored` mutant moves with `resolve_execution_mode`.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | A step asks `agentic`, and the run's DAL is riskier than the ceiling: what happens? | it runs one-shot, and its result says why, naming the DAL and the ceiling `[agreed 2026-10-20]` |

## Backlog

none
