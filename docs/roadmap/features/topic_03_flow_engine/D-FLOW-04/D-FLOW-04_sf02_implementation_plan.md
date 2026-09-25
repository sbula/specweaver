# D-FLOW-04 SF-02 — Unified CLI Runner

**Status**: COMPLETED 2026-03-29 · **FRs owned**: FR-1, FR-4, FR-5 · **Depends on**: none ·
**Feature ID**: 3.13a · Design: [D-FLOW-04_design.md](D-FLOW-04_design.md) §Sub-features → SF-02

## Goal

Single-shot CLI commands (`sw review`, `sw draft`, etc.) run as programmatic 1-step pipelines through
`PipelineRunner`. Execution, state tracking and telemetry become one path; the `cli/` module stops
managing lifecycles by hand.

## Where it plugs in

- `PipelineDefinition` lives in `src/specweaver/flow/models.py` and needs a factory method (decision
  below).
- `PipelineRunner` already calls `TelemetryCollector.flush()` and persists database state. CLI
  commands only need to configure the `RunContext`.

## Decisions

- **`PipelineDefinition.create_single_step()` factory inside `flow/models.py`** (user-confirmed).
- `cli/` delegates execution only to `flow/runner.py`; no ad-hoc domain runner orchestration in the
  CLI commands. This tightens the dependency constraints.

## Changes

1. **`[MODIFY] flow/models.py`** — `@classmethod` factory `create_single_step(name, action, target, gate)`
   on `PipelineDefinition`: an in-memory 1-step pipeline structurally identical to a parsed YAML one.
   Add `StepAction.ENRICH` and `StepTarget.STANDARDS` to the enums and `VALID_STEP_COMBINATIONS`
   (standards discovery).
2. **`[NEW] flow/handlers/_standards.py`** — `EnrichStandardsHandler` extending `StepHandler`. Wraps
   `StandardsScanner` and `StandardsEnricher` (LLM): takes a list of files per scope, runs the
   analysis and the LLM enrichment, yields the `CategoryResult` payload back to the `RunContext` for
   HITL review. Register it in `registry.py`.
3. **`[MODIFY] cli/review.py`** — `draft()` and `review()` Typer commands: replace direct `Reviewer` and
   `Drafter` initialization/execution. Build a `RunContext`, a single-step pipeline via
   `PipelineDefinition.create_single_step()`, and await `PipelineRunner(pipeline, context).run()`.
   Remove the manual `TelemetryCollector.flush()`; the runner does it.
4. **`[MODIFY] cli/implement.py`** — same for the `implement()` command (replaces direct `Generator`
   use; `TelemetryCollector.flush()` removed).
5. **`[MODIFY] cli/standards.py`** — `standards_scan()`: replace direct `StandardsEnricher` use. For each
   scope with valid raw scan results, run a single-step pipeline (`ENRICH` `STANDARDS`) via
   `PipelineRunner`, so telemetry captures cost and LLM token flushing is unified, while the multi-scope
   HITL loop stays.

## Tests

1. Unit: `create_single_step` builds an in-memory `PipelineDefinition` that passes Pydantic validation.
2. E2E: the existing CLI integration tests for `sw review` and `sw draft` pass unaltered — only internal
   routing and state management change.
3. Manual: `sw review <existing_spec_path>` behaves as before and logs.

## As built (2026-03-29)

All commands refactored to `PipelineRunner`. E2E passing (3589 tests).

**Since moved**: `PipelineDefinition` → `src/specweaver/core/flow/engine/models.py`;
`EnrichStandardsHandler` → `src/specweaver/core/flow/handlers/standards.py`; `sw draft`/`sw review` →
`src/specweaver/workflows/review/interfaces/cli.py`; `standards_scan()` →
`src/specweaver/assurance/standards/interfaces/cli.py`; `implement()` →
`src/specweaver/workflows/implementation/interfaces/cli.py`, now a multi-step pipeline (`INT-US-03`)
and `sw draft` a 3-step chain (`INT-US-02`).
