# Implementation Plan: Router-Based Flow Control [SF-1: Core Router Implementation]
- **Feature ID**: 3.25
- **Sub-Feature**: SF-1 — Core Router Implementation
- **Design Document**: docs/proposals/roadmap/phase_3/feature_3_25/feature_3_25_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/proposals/roadmap/phase_3/feature_3_25/feature_3_25_implementation_plan.md
- **Status**: APPROVED

## Goal Description
Implement Router-Based Flow Control (Feature 3.25) to enable conditional branching in SpecWeaver pipelines dynamically. Rather than being restricted to strict linear execution (Step 1 -> Step 2) or rollback loops (Gates), this introduces the `router` step configuration allowing a pipeline to jump to independent `target` tracks based on the structured contents of a `StepResult.output`.

## User Review Required
None remaining. All options were resolved in the Phase 4 HITL Gate.

## Proposed Changes

---

### `flow` Module (Core Engine Models) [✅ Implemented]
**Commit 1 Notes**: Data schemas (`RuleOperator`, `RouterRule`, `RouterDefinition`) and `PipelineDefinition.get_step_index()` validation were implemented exactly as designed in Boundary 1. No architectural deviations.

#### [MODIFY] [models.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/models.py)
**Rationale:** Define the fundamental structure of pipelines and steps, satisfying NFR-1 (Safe Evaluation, no eval).
1. Add `RuleOperator` enum: `EQ` ("=="), `NEQ` ("!="), `LT` ("<"), `GT` (">"), `CONTAINS` ("contains"), `IN` ("in"), `IS_EMPTY` ("is_empty"), `NOT_EMPTY` ("not_empty").
2. Add `RouterRule(BaseModel)` with `field: str`, `operator: RuleOperator`, `value: Any`, and `target: str`.
3. Add `RouterDefinition(BaseModel)` with `rules: list[RouterRule]` and `default_target: str`.
4. Add `router: RouterDefinition | None = None` to `PipelineStep`.
5. Update `PipelineDefinition.validate_flow()` to map all `router` targets and ensure they point to existing step names. Also ensure `default_target` exists.

#### [NEW] [routers.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/routers.py)
**Rationale:** Encapsulate flow evaluation algorithms away from Pydantic models to prevent cyclic dependency issues (AD-1).
1. Implement `RouterEvaluator.evaluate(router: RouterDefinition, result: StepResult) -> str`.
2. Securely resolve `result.output` using dotted-path `field` lookup (e.g. `complexity` retrieves `result.output.get("complexity")`).
3. Apply `RuleOperator` mappings correctly without relying on Python's native `eval()` function to meet NFR-1 constraints. Return the first matching `RouterRule.target`. Focus on high performance (< 20ms NFR-2).
4. If no rules evaluate to true, return the `router.default_target`. Raise logging error and fallback to `default_target` if type mismatches occur (like trying to `LT` < on a string).

---

### `flow` Module (Execution Engine - Routing) [✅ Implemented]
**Commit 2 Notes**: `RouterEvaluator` logic was safely implemented without `eval()`. State mutation via `route_to_step` and execution logic directly inside `PipelineRunner._execute_loop` handled perfectly. All Edge Case scenarios regarding implicit fallback gates correctly observed.

#### [NEW] [routers.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/routers.py)
**Rationale:** Facilitate nonlinear step changes in pipeline state reliably.
1. Add `PipelineRun.route_to_step(self, result: StepResult, next_step_idx: int)`. This marks the current active record with `result`, then directly overwrites `self.current_step = next_step_idx` instead of using `+= 1`. If `next_step_idx` is out of bounds, marks as COMPLETED.

#### [MODIFY] [runner.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/runner.py)
**Rationale:** Connect the RouterEvaluator inside the main orchestration loop (AD-2 - Gate Precedence).
1. Under `PipelineRunner._execute_loop()`, modify the "Success — advance" block.
2. If `verdict == "advance"` (from the gate evaluation) or there is no gate:
3. Check `if step_def.router is not None:`.
4. Call `RouterEvaluator.evaluate(step_def.router, result)` to get the `target_name`.
5. Check pipeline structure: `next_idx = self._pipeline.get_step_index(target_name)` (Requires adding a helper method `get_step_index` to `PipelineDefinition` in `models.py` or resolving it natively).
6. Record telemetry: `self._log(run, "step_routed", step_def.name, details=str({"target": target_name}))`.
7. Emit via `self._emit("step_routed", ...target_name)`.
8. Advance State via `run.route_to_step(result, next_idx)`. Provide a `continue` to break out of the current sequential step processing and loop naturally to the routed jump.
9. If `step_def.router` is `None`, keep existing backward-compatible `run.complete_current_step(result)` logic (NFR-3).

---

### Documentation

#### [MODIFY] Developer Guide / Documentation
**Rationale:** Educate developers and prompt context about routing vs splitting boundaries.
1. Introduce a strict clarifying distinction block in the Router documentation guiding developers:
   * **Decomposition** (Feature 3.1): Used entirely to divide payload context blobs that exhaust Token constraints and Context size.
   * **Routing** (Feature 3.25): Process changes to pivot standard-workflow models toward Fast Tracks, Heavy Review Tracks, or Specialized tools.

## Verification Plan

### Automated Tests (`pytest`)
- `test_routers.py`: Direct unit testing of `RouterEvaluator.evaluate()` with 100% of operators validating logical outcomes, nesting, and erroneous types failing safely to default.
- `test_models.py`: Verify `PipelineDefinition.validate_flow()` traps invalid targets (bad step name).
- `test_runner.py`: Create dummy `MockStepHandler` that emits `StepResult(output={"c": "low"})`. Verify `PipelineRunner` successfully navigates through the router and skips un-routed central steps safely.

### Security / Quality Tests
- Ensure `eval()` and `exec()` usage triggers lint alarms via Ruff if somehow introduced to `routers.py` during DEV.

## Backlog / Postponed Items
- Complex multi-field logic evaluations (`AND` / `OR` gates). To preserve speed, we strictly rely on the LLM generating explicit classification fields. (Phase 4 decision Option 1A).
