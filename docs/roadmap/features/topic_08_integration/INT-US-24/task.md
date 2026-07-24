# Task List — INT-US-24 SF-01: Make the Chain Executable

- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-24/INT-US-24_sf01_implementation_plan.md (APPROVED)
- **FRs**: FR-1 (dual dispatch), FR-2 (arbiter evidence contract, refined), FR-3 (scenario false-green fix)
- **Commit boundary**: single **CB-1** — all tasks T1–T5, then pre-commit gate + HITL commit stop.

## Tasks (SF-01)

- [x] **T1 — FR-3 scenario-kind semantics**
  - Source: `src/specweaver/core/flow/handlers/validation.py` (ValidateTestsHandler.execute only)
  - Tests: `tests/unit/core/flow/handlers/test_validate_tests_handler.py` (new class)
  - Red: (a) kind "scenario" → atom receives kind="" (atom-call site only; `_resolve_targets`
    keeps original kind); (b) other kinds byte-identical; (c) scenario total==0 → FAILED with
    actionable message; (d) scenario failures → FAILED, exports intact; (e) unit-kind total==0
    pristine path still PASSES; (f) NFR-3: `_get_atom`/execution_root untouched (existing tests
    stay green).
- [x] **T2 — FR-1 dual dispatch**
  - Source: `src/specweaver/core/flow/handlers/decompose.py` (delegation before plan guard),
    `src/specweaver/core/flow/handlers/registry.py` (import + `__all__`),
    `src/specweaver/core/flow/handlers/dual_pipeline.py` (only if T2d proves the None-crash)
  - Tests: `tests/unit/core/flow/handlers/test_decompose.py`, `test_dual_pipeline.py`
  - Red: (a) mode=="dual_pipeline" → ArbitrateDualPipelineHandler.execute awaited, plan guard
    never hit, INFO log; (b) no mode → byte-identical "No DecompositionPlan" behavior;
    (c) `__all__` export pin; (d) context.pipeline_runner None in dual mode → clean FAILED/ERROR,
    no AttributeError; (e) unrecognized set mode ("Dual_Pipeline") → WARNING + plan path.
- [x] **T3 — FR-2 evidence producer**
  - Source: `src/specweaver/core/flow/handlers/validation.py` (ValidateTestsHandler)
  - Tests: `tests/unit/core/flow/handlers/test_validate_tests_handler.py`
  - Red: scenario-kind run publishes raw QA export under
    `context.feedback["scenario_test_failures"]` on PASS and FAIL; non-scenario kinds never
    touch context.feedback.
- [x] **T4 — FR-2 evidence consumer (arbiter)**
  - Source: `src/specweaver/core/flow/handlers/arbiter.py`
  - Tests: `tests/unit/core/flow/handlers/test_arbiter.py` (migrate 4 execute-path tests off the
    old fictional `feedback["run_scenario_tests"]` shape; vocabulary/model tests untouched)
  - Red: (a) total>0 ∧ failed==0 ∧ errors==0 → PASSED, llm.generate NOT called, output
    verdict:no_failures; (b) key absent → ERROR (wiring message); (c) failures present → prompt
    "Failures" block carries message+stacktrace (stack-trace-filtered), code_bug/scenario_error/
    spec_ambiguity flows on the new shape; (d) consume-on-verdict: popped on
    no_failures/code_bug/scenario_error, RETAINED on spec_ambiguity + ERROR; (e) E1 failed==0 ∧
    errors>0 → arbitrates (no short-circuit); (f) E2 total==0/missing counts → FAILED "no
    scenario tests executed"; (g) E4 hostile: non-dict evidence / non-dict failures entries →
    ERROR, no crash.
- [x] **T5 — cross-contract pins**
  - Tests: `tests/unit/core/flow/handlers/test_dual_pipeline.py` (reserved-key collision pin),
    `tests/integration/core/flow/handlers/test_scenario_integration_dispatch.py` (NEW)
  - Red: (a) no bundled pipeline defines a step named `scenario_test_failures`;
    (b) integration: scenario_integration.yaml + REAL registry — run_dual_pipelines reaches the
    dual handler (patch `ArbitrateDualPipelineHandler._build_runner` to return stub sub-runners —
    NOT `PipelineRunner` globally, which would collaterally patch the outer runner),
    run_scenario_tests + arbitrate_verdict run REAL handlers with mocked QA atom
    (`ValidateTestsHandler._get_atom`) + mocked LLM: green path completes with zero LLM calls
    (assert `llm.generate` never awaited); red path arbitrates with real evidence.

## Adversarial matrix (4 buckets)
- Happy: T1a, T2a, T3-pass, T4a, T5b-green.
- Boundary: T1c/T1e (0-collected vs pristine), T4d (consume-on-verdict double-execute), T4e (errors-only).
- Graceful degradation: T2d (runner absent), T4b (evidence absent), T4f (total==0/timeout shape), dual sub-run parked/failed (existing pins).
- Hostile: T4g (non-dict evidence, non-dict failures entries), T2e (typo'd mode).

## Pre-Commit Gate (CB-1)
- [x] Phase 1 — architecture: all edits core/flow-internal; tach ✅; no new imports/boundaries; no parallel mechanisms; DAG intact
- [x] Phase 2 — test gap analysis: matrix presented; gaps G-a/G-b/G-c approved
- [x] Phase 3 — G-a (timeout shape publishes {} evidence), G-b (empty-dict evidence → FAILED), G-c (string counts / non-list failures → malformed ERROR) — all green
- [x] Phase 4 — full suite re-run from scratch: unit 4805 · integration 504 · e2e 157 = 5466 passed, 0 failures
- [x] Phase 5 — ruff ✅ · mypy ✅ (303 files) · C901 ✅ · file-size 0 errors · tach ✅ · roadmap-sync ✅
- [x] Phase 6 — task.md record + impl-plan handoff updated; dev-guide currency update deferred to SF-03 (per design)
- [x] Phase 7 — INT-US-24_sf01_walkthrough.md written
- [x] Phase 7.5 — no fix-required findings; prompt-injection class = pre-existing E-VAL-03 scope; bool/int + passed-count LOW cosmetic; non-python runners verified kind-agnostic
- [ ] Phase 8 — commit boundary (HITL hard stop)
