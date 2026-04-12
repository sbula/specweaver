# Design: Router-Based Flow Control

- **Feature ID**: 3.25
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/phase_3/feature_3_25/feature_3_25_design.md

## Feature Overview

Feature 3.25 adds conditional branching capabilities to the core Pipeline Engine.
It solves the problem of "one-size-fits-all" execution by adding an explicit `router` YAML key, allowing specs to take optimized paths (e.g., bypass full decomposition for simple tasks based on the Planner output).
It interacts with the YAML pipeline parser, the base Handler classes, and the execution engine, and does NOT touch language-specific AST manipulation or external integrations.
Key constraints: To prevent python evaluations on untrusted YAML, the routing condition must be configured using declarative structured operators.

## Research Findings

### Codebase Patterns
- **`PipelineRunner`**: Currently uses `while run.current_step < len(run.step_records):`. After `run.complete_current_step()`, it advances. The new logic must evaluate `step.router` (if present) and mutate `run.current_step` using the matching `RouterDefinition.target` mapped to `PipelineDefinition.get_step_index(target)`.
- **`PipelineDefinition`**: Currently `validate_flow`/`_validate_loop_back` prevents forward loops to maintain a simplistic DAG. `router` blocks are fundamentally forward-jumps (or lateral). We must add a specific exception for `router` while validating that their `target` step actually exists in the pipeline.
- **`GateEvaluator` vs `RouterEvaluator`**: The `GateEvaluator` validates step success/approval (and can loop_back or park). The `RouterEvaluator` decides where to go *next* if the gate completely passed.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Parse Router | System | Reads a `RouterDefinition` block from `PipelineStep` | Populates `step.router` with structured conditions and a default target. |
| FR-2 | Validate Router Targets | System | Runs `validate_flow()` on `PipelineDefinition` | Asserts all `target` and `default_target` in the router map to valid step names in the pipeline. |
| FR-3 | Evaluate Router | RouterEvaluator | Evaluates structured routing conditions against the generated `StepResult` output | Selects exactly one `target` step name based on the first condition match or falls back to `default_target`. |
| FR-4 | Mutate Path | PipelineRunner | Adjusts `run.current_step` to the resolved router target index upon step completion | The pipeline dynamically skips unneeded intermediate steps and resumes execution at the target. |
| FR-5 | Audit & Telemetry | System | Emits a structural runner event when routing occurs | The `StateStore` logs the parsed condition and target destination so the Dashboard can visualize why the pipeline jumped. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Safe Evaluation | Routing conditions MUST use safe structured operators (e.g. `is_empty`, `==`). `eval()` or `exec()` are strictly forbidden. |
| NFR-2 | Evaluation Latency | Evaluating the router logic MUST be synchronous and complete in < 20ms over a typical json output dictionary. |
| NFR-3 | Backward Compatibility | Existing YAML pipelines without a `router` key MUST continue to execute linearly without failing or requiring modification. |
| NFR-4 | Infinite Loop Guard | Routing mutations MUST remain strictly bound by the runner's existing `max_total_loops` safeguard to prevent accidental infinite jump cycles. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| None | N/A | N/A | Y | Structured Ops requires no new deps. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Option 1 (Structured Declarative Ops) | Prevent RCE via raw string eval() on pipeline config YAMLs. | No |
| AD-2 | Gate Precedence over Router | Gates determine if a step fundamentally worked (or needs retry/HITL). Routers determine where to go *after* it works. | No |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Guide-1 | Writing Pipeline Router Rules | How to define branching `router` keys in pipelines config YAMLs | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

Single feature — no decomposition.

### SF-1: Core Router Implementation
- **Scope**: Extend `models.py`, `runner.py`, and create `routers.py` to enable declarative flow control branching.
- **FRs**: [FR-1, FR-2, FR-3, FR-4, FR-5]
- **Inputs**: Executable `PipelineStep` objects with `router` configs, and the resulting `StepResult.result_data`.
- **Outputs**: Mutated `current_step` in `PipelineRun` and audit log tracing the routing decision.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/phase_3/feature_3_25/feature_3_25_implementation_plan.md

## Execution Order

1. SF-1 (no deps — start immediately)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Core Router Implementation | — | ✅ | ✅ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Implementation Plan APPROVED for SF-1.
**Next step**: Run:
`/dev docs/roadmap/phase_3/feature_3_25/feature_3_25_implementation_plan.md`
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume from there.
