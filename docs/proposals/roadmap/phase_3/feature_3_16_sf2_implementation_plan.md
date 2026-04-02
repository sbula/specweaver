# Implementation Plan: Unified CLI Runner [SF-2: Unified CLI Runner]
- **Feature ID**: 3.13a
- **Sub-Feature**: SF-2 — Unified CLI Runner
- **Design Document**: docs/proposals/design/phase_3/feature_3_16_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/proposals/roadmap/phase_3/feature_3_16_sf2_implementation_plan.md
- **Status**: COMPLETED
- **Completed Date**: 2026-03-29
- **Notes on Implementation**: All commands successfully refactored to use PipelineRunner. Test failures resolved by adhering to no-compound-shell rules and updating LLM mock definitions. E2E passing (3589 tests).

## Goal Description

Refactor single-shot CLI commands (`sw review`, `sw draft`, etc.) to execute via programmatic dynamic 1-step pipelines using `PipelineRunner`. This completely standardizes execution, state tracking, and telemetry hookups, removing manually-managed lifecycles from the `cli/` module. 

> [!NOTE]
> **Research Notes Synthesis**
> - `PipelineDefinition` exists in `src/specweaver/flow/models.py` and requires adding a factory method per the architectural decision.
> - `PipelineRunner` natively executes `TelemetryCollector.flush()` and persists database state automatically. CLI methods only need to configure the `RunContext` properly to benefit from this logic.

## User Review Required (HITL Phase 4 & 5)

> [!WARNING]
> Please review the architectural alignments and provide final **Consistency Check** approval to proceed with SF-2.
> 
> **Phase 5 Consistency Check (Evidence-Backed):**
> 1. **Any unresolved decisions?** No. All decisions are resolved. The user explicitly confirmed defining a `PipelineDefinition.create_single_step()` factory method inside `flow/models.py`.
> 2. **Architecture and future compatibility:** This heavily aligns with the architecture. It specifically *improves* the dependency constraints by letting `cli/` solely delegate to `flow/runner.py` for execution, removing ad-hoc domain runner orchestrations directly in the CLI commands.
> 3. **Internal consistency check:** No contradictions exist. All file modifications match the components.
> 
> **Agent Handoff Risk Evaluation:** A fresh agent jumping into `/dev` will clearly see the explicit `[NEW]` and `[MODIFY]` file directives below, avoiding guesswork on where the factory logic changes reside.

## Proposed Changes

---

### Flow Engine

This modifies the core data model of the pipeline engine to support dynamic pipeline creation outside the YAML ecosystem.

#### [MODIFY] [models.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/models.py)
- **Action**: Add a `@classmethod` factory `create_single_step(name, action, target, gate)` to `PipelineDefinition`. Add `StepAction.ENRICH` and `StepTarget.STANDARDS` to the enums and `VALID_STEP_COMBINATIONS`.
- **Purpose**: Creates an in-memory 1-step pipeline structurally identical to parsed YAML pipelines. Expands target vocabulary to support standard discovery.

#### [NEW] [_standards.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/handlers/_standards.py)
- **Action**: Create an `EnrichStandardsHandler` extending `StepHandler`.
- **Purpose**: Wraps the `StandardsScanner` and `StandardsEnricher` (LLM) execution. Takes a list of files per scope, runs the analysis, and performs the LLM enrichment. Yields the `CategoryResult` payload back to the `RunContext` for HITL review. Registration in `registry.py` is also required.

---

### CLI Layer

Refactor the CLI module entry points to route execution through `PipelineRunner`.

#### [MODIFY] [review.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli/review.py)
- **Action**: Replace direct `Reviewer` and `Drafter` initialization/execution logic inside `draft()` and `review()` Typer commands.
- **Purpose**: Construct a `RunContext`, build a single-step pipeline using `PipelineDefinition.create_single_step()`, and await `PipelineRunner(pipeline, context).run()`. Completely remove the manual `TelemetryCollector.flush()` logic, as the runner natively handles it.

#### [MODIFY] [implement.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli/implement.py)
- **Action**: Replace direct `Generator` initialization/execution logic inside the `implement()` Typer command.
- **Purpose**: Construct a `RunContext`, build a single-step pipeline using `PipelineDefinition.create_single_step()`, and await `PipelineRunner(pipeline, context).run()`. Ensure `TelemetryCollector.flush()` is removed and handled by the runner.

#### [MODIFY] [standards.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli/standards.py)
- **Action**: Replace direct `StandardsEnricher` initialization/execution logic inside the `standards_scan()` command.
- **Purpose**: For each scope with valid raw scan results, execute a single-step pipeline (`ENRICH` `STANDARDS`) via `PipelineRunner`. This ensures telemetry context correctly captures cost analysis, unifying the LLM token flushing behavior while preserving the multi-scope HITL loop.

---

## Open Questions

None. 

## Verification Plan

### Automated Tests
1. **Unit tests for `create_single_step`**: Verify that building an in-memory `PipelineDefinition` validates successfully via Pydantic model criteria.
2. **E2E execution test**: The existing CLI integration tests for `sw review` and `sw draft` should continue to pass completely unaltered since the behavior change focuses strictly on internal routing + unified state management.

### Manual Verification
1. Run `sw review <existing_spec_path>` to ensure the command functions identical to today, and logs execute successfully.
