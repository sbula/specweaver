# C-FLOW-02 — Router-Based Flow Control

**Status**: APPROVED · **Feature ID**: 3.25 · **Phase**: 3 · single sub-feature, plan approved

| | |
|---|---|
| Touches | YAML pipeline parser, base Handler classes, execution engine |
| Not touched | language-specific AST manipulation, external integrations |
| External deps | none — structured ops need no new dependency |

## What it does

Adds conditional branching to the Pipeline Engine. A step's explicit `router` YAML key sends the
pipeline down an optimized path instead of one-size-fits-all execution — e.g., skip full
decomposition for a simple task, based on the Planner output.

Constraint: routing conditions are declarative structured operators, so untrusted YAML is never
evaluated as Python.

## How it fits

- **`PipelineRunner`** loops `while run.current_step < len(run.step_records):` and advances after
  `run.complete_current_step()`. With a router, it evaluates `step.router` and sets
  `run.current_step` from the matching `RouterDefinition.target` via
  `PipelineDefinition.get_step_index(target)`.
- **`PipelineDefinition`**: `validate_flow`/`_validate_loop_back` forbid forward loops to keep a
  simple DAG. Routers are forward (or lateral) jumps, so they get an explicit exception — and their
  `target` step must exist in the pipeline.
- **`GateEvaluator` vs `RouterEvaluator`**: the gate decides whether a step succeeded or was approved
  (and can loop_back or park). The router decides where to go *next*, only once the gate passed.

## Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Option 1 (Structured Declarative Ops) | Prevent RCE via raw string eval() on pipeline config YAMLs. | No |
| AD-2 | Gate Precedence over Router | Gates determine if a step fundamentally worked (or needs retry/HITL). Routers determine where to go *after* it works. | No |

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Parse Router | System | Reads a `RouterDefinition` block from `PipelineStep` | Populates `step.router` with structured conditions and a default target. |
| FR-2 | Validate Router Targets | System | Runs `validate_flow()` on `PipelineDefinition` | Asserts all `target` and `default_target` in the router map to valid step names in the pipeline. |
| FR-3 | Evaluate Router | RouterEvaluator | Evaluates structured routing conditions against the generated `StepResult` output | Selects exactly one `target` step name based on the first condition match or falls back to `default_target`. |
| FR-4 | Mutate Path | PipelineRunner | Adjusts `run.current_step` to the resolved router target index upon step completion | The pipeline skips unneeded intermediate steps and resumes execution at the target. |
| FR-5 | Audit & Telemetry | System | Emits a structural runner event when routing occurs | The `StateStore` logs the parsed condition and target destination so the Dashboard can visualize why the pipeline jumped. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Safe Evaluation | Routing conditions MUST use safe structured operators (e.g. `is_empty`, `==`). `eval()` or `exec()` are strictly forbidden. |
| NFR-2 | Evaluation Latency | Evaluating the router logic MUST be synchronous and complete in < 20ms over a typical json output dictionary. |
| NFR-3 | Backward Compatibility | Existing YAML pipelines without a `router` key MUST continue to execute linearly without failing or requiring modification. |
| NFR-4 | Infinite Loop Guard | Routing mutations MUST remain strictly bound by the runner's existing `max_total_loops` safeguard to prevent accidental infinite jump cycles. |

## Guides owed

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Guide-1 | Writing Pipeline Router Rules | How to define branching `router` keys in pipelines config YAMLs | ⬜ To be written during Pre-commit |

## Sub-features

| SF | Does | FRs | Inputs → Outputs | Depends on | Plan |
|----|------|-----|------------------|-----------|------|
| SF-01 | Extend `models.py`, `runner.py`; new `routers.py` — declarative branching | FR-1, FR-2, FR-3, FR-4, FR-5 | `PipelineStep` objects with `router` configs + `StepResult.result_data` → mutated `current_step` in `PipelineRun` + audit log of the routing decision | none | [plan](C-FLOW-02_implementation_plan.md) |

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Core Router Implementation | — | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
