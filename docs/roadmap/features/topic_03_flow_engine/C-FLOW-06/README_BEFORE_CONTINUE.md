# STOP! READ BEFORE CONTINUING SF-2

## Current State of SF-2 (Impact-Aware Testing & DAL Enforcements)

We attempted to push SF-2 through the `/pre-commit` gate, but it was **HALTED during Phase 2 (Test Gap Analysis)** due to severe missed requirements and an architectural violation in the original design.

### 1. FR-2 (Test Limiting) was COMPLETELY MISSED
The previous implementation plan for SF-2 (`feature_3_32d_sf2_implementation_plan.md`) completely forgot to include FR-2. 
- Only FR-3 (DAL Enforcements) was implemented.
- `QARunnerTool` and test impact-caching have NOT been built yet.
- You must resume development to implement FR-2.

### 2. CRITICAL: Architectural Switch required for AD-1
The original design document explicitly stated:
> *AD-1: Query TopologyGraph statically in QARunnerTool*

**DO NOT DO THIS.**
- `QARunnerTool` lives in the `loom` layer (the isolated executor environment).
- `TopologyGraph` lives in the `graph` layer.
- If `loom` imports `graph`, it violates the strict dependency isolation where execution tools are ignorant of the codebase's logical bounds. 
- **The Fix:** Query `TopologyGraph` natively inside the Orchestrator (`flow/handlers/_validation.py` -> `ValidateTestsHandler`). The orchestrator legally consumes `graph`. It can resolve the targeted stale files and pass them directly as filesystem paths to `QARunnerAtom.run_tests(targets=...)`.

### 3. Missing Tests
Because FR-2 was missed and pre-commit was aborted, we are missing critical test coverage:
- **Unit/Integration:** Need tests for `ValidateTestsHandler` resolving topology correctly.
- **E2E:** Need a pipeline execution test proving that DAL threshold breaches (`DAL_A` warnings) trigger a hard pipeline stop.
- **E2E:** Need a test proving that `QARunnerAtom` correctly executes only targeted file subsets.

## Next Steps for the Resuming Agent
1. Read the newly generated `implementation_plan.md` artifact from the previous session (or refer to the fixes above).
2. Fix the architectural flaw in `feature_3_32d_design.md` (Update AD-1).
3. Implement FR-2 following the architecture rules.
4. Write the missing Integration and E2E tests.
5. Re-run the ENTIRE `/pre-commit` gate from Phase 1.
