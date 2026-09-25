# C-FLOW-06 SF-02 — Read before continuing

SF-02 was **HALTED during Phase 2 (Test Gap Analysis)** of the `/pre-commit` gate: FR-2 was missing
from the plan, and the original AD-1 broke a layer rule.

## Open

1. **FR-2 (Test Limiting) is not built.** The SF-02 plan (`feature_3_32d_sf02_implementation_plan.md`,
   now [C-FLOW-06_sf02_implementation_plan.md](C-FLOW-06_sf02_implementation_plan.md)) covers only
   FR-3 (DAL Enforcements). `QARunnerTool` and test impact-caching are not built.
2. **Follow AD-1 as it stands now.** Query `TopologyGraph` inside the orchestrator
   (`flow/handlers/_validation.py` -> `ValidateTestsHandler`), which may consume `graph`. Resolve the
   stale files there and pass them as filesystem paths to `QARunnerAtom.run_tests(targets=...)`.
3. **Missing tests.**
   - Unit/Integration: `ValidateTestsHandler` resolves topology correctly.
   - E2E: a pipeline run where a DAL threshold breach (`DAL_A` warnings) stops the pipeline hard.
   - E2E: `QARunnerAtom` executes only the targeted file subset.

## Rule — do not undo

**DO NOT** query `TopologyGraph` from `QARunnerTool` (the old AD-1: *"Query TopologyGraph statically
in QARunnerTool"*). `QARunnerTool` lives in the `loom` layer (the isolated executor);
`TopologyGraph` lives in the `graph` layer. Execution tools must stay ignorant of the codebase's
logical bounds, so `loom` must not import `graph`.

## Steps to resume

1. Take the fixes above (the prior session's `implementation_plan.md` artifact, if you have it).
2. AD-1 in the design (`feature_3_32d_design.md`, now [C-FLOW-06_design.md](C-FLOW-06_design.md))
   is already updated.
3. Implement FR-2 under the architecture rules.
4. Write the missing Integration and E2E tests.
5. Re-run the ENTIRE `/pre-commit` gate from Phase 1.

Code check (2026-09-25): `ValidateTestsHandler._resolve_targets` (`core/flow/handlers/validation.py`)
already maps `context.graph.stale_nodes` to test directories, but `GraphContext.stale_nodes` is
written by nothing in production, so it is always `None` and the full target runs.
