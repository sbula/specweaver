# C-FLOW-02 SF-01 — Core Router Implementation

**Status**: APPROVED · **Feature ID**: 3.25 · **FRs owned**: FR-1, FR-2, FR-3, FR-4, FR-5 ·
**Depends on**: none · Design: [C-FLOW-02_design.md](C-FLOW-02_design.md) §Sub-features → SF-01

FR ownership recorded 2026-08-17 under `specweaver-dev` §3.2c, from `INT-US-06-MIG`: the plan
predates the FR ledger, so `check_fr_coverage.py` had read all five as unplanned.

## Goal

Conditional branching in SpecWeaver pipelines. Beyond linear execution (Step 1 -> Step 2) and
rollback loops (Gates), a step's `router` jumps to an independent `target` track based on the
structured contents of `StepResult.output`. All options were resolved in the Phase 4 HITL Gate.

**Since moved** (checked 2026-09-25): `flow/` is now `src/specweaver/core/flow/engine/`
(`models.py`, `routers.py`, `runner.py`); `PipelineRun.route_to_step` lives in `state.py`.

## Changes

### Commit 1 — models [✅ Implemented, as designed, no deviations]

`src/specweaver/flow/models.py` [MODIFY] — pipeline/step structure, meeting NFR-1 (Safe Evaluation,
no eval):

1. `RuleOperator` enum: `EQ` ("=="), `NEQ` ("!="), `LT` ("<"), `GT` (">"), `CONTAINS` ("contains"),
   `IN` ("in"), `IS_EMPTY` ("is_empty"), `NOT_EMPTY` ("not_empty").
2. `RouterRule(BaseModel)`: `field: str`, `operator: RuleOperator`, `value: Any`, `target: str`.
3. `RouterDefinition(BaseModel)`: `rules: list[RouterRule]`, `default_target: str`.
4. `router: RouterDefinition | None = None` on `PipelineStep`.
5. `PipelineDefinition.validate_flow()` checks every `router` target and `default_target` names an
   existing step. Plus `PipelineDefinition.get_step_index()`.

`src/specweaver/flow/routers.py` [NEW] — evaluation kept out of the Pydantic models, avoiding cyclic
dependencies (AD-1):

1. `RouterEvaluator.evaluate(router: RouterDefinition, result: StepResult) -> str`.
2. Resolve `result.output` by dotted-path `field` lookup (e.g. `complexity` →
   `result.output.get("complexity")`).
3. Apply the `RuleOperator` mappings without Python's `eval()` (NFR-1). Return the first matching
   `RouterRule.target`. Stay under 20ms (NFR-2).
4. No rule true → `router.default_target`. A type mismatch (e.g. `LT` < on a string) logs an error
   and falls back to `default_target`.

### Commit 2 — execution engine [✅ Implemented]

1. `PipelineRun.route_to_step(self, result: StepResult, next_step_idx: int)` (planned under
   `routers.py` [NEW]) — marks the active record with `result`, then sets
   `self.current_step = next_step_idx` instead of `+= 1`. Out-of-bounds `next_step_idx` → COMPLETED.
2. `src/specweaver/flow/runner.py` [MODIFY] — `RouterEvaluator` in the main loop (AD-2, Gate
   Precedence). In `PipelineRunner._execute_loop()`, "Success — advance" block:
   1. If `verdict == "advance"` (from the gate) or there is no gate, and
      `if step_def.router is not None:`
   2. `RouterEvaluator.evaluate(step_def.router, result)` → `target_name`.
   3. `next_idx = self._pipeline.get_step_index(target_name)` (the `get_step_index` helper on
      `PipelineDefinition` in `models.py`).
   4. Record: `self._log(run, "step_routed", step_def.name, details=str({"target": target_name}))`.
   5. Emit: `self._emit("step_routed", ...target_name)`.
   6. `run.route_to_step(result, next_idx)`, then `continue` so the loop jumps to the routed step.
   7. `step_def.router` is `None` → unchanged `run.complete_current_step(result)` (NFR-3).

   `RouterEvaluator` uses no `eval()`; the implicit-fallback-gate edge cases hold.

### Documentation [MODIFY] — Developer Guide

The Router docs get a clarifying block, for developers and prompt context:

- **Decomposition** (Feature 3.1): divides payload context blobs that exhaust token and context
  size limits.
- **Routing** (Feature 3.25): pivots standard workflows toward Fast Tracks, Heavy Review Tracks, or
  Specialized tools.

## Tests

| Test | Proves |
|---|---|
| `test_routers.py` | `RouterEvaluator.evaluate()` with 100% of operators: outcomes, nesting, bad types fall back to default |
| `test_models.py` | `PipelineDefinition.validate_flow()` traps invalid targets (bad step name) |
| `test_runner.py` | a `MockStepHandler` emitting `StepResult(output={"c": "low"})` → `PipelineRunner` follows the router and skips the un-routed middle steps |
| Ruff | flags `eval()` / `exec()` if ever introduced to `routers.py` |

## As built

Proof and the mutants that verify it: `tests/unit/core/flow/engine/test_routers.py` (FR-3),
`test_router_integration.py` (FR-1, FR-2, FR-4), `test_runner_routing.py` (FR-5).

FR-5 needed a new assertion: the only routing assertion was on the emitted event, so its store half —
the `step_routed` audit row — could be deleted with the whole suite green.

## Backlog

- Multi-field logic (`AND` / `OR` gates). For speed, routing relies on the LLM emitting explicit
  classification fields (Phase 4 decision Option 1A).
