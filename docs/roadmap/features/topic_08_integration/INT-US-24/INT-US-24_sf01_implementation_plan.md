# Implementation Plan: INT-US-24 [SF-01: Make the Chain Executable]

- **Feature ID**: INT-US-24
- **Sub-Feature**: SF-01 — Make the Chain Executable (dispatch + evidence + false-green)
- **Design Document**: docs/roadmap/features/topic_08_integration/INT-US-24/INT-US-24_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_08_integration/INT-US-24/INT-US-24_sf01_implementation_plan.md
- **Status**: APPROVED <!-- Phase 4 (Q1–Q5 + E1–E4) and Phase 5 approved by user 2026-07-23 -->

## Scope (from design)

Make `scenario_integration.yaml` executable end-to-end with real handlers:

- **FR-1** — dual-pipeline dispatch: `OrchestrateComponentsHandler` delegates
  `step.params["mode"] == "dual_pipeline"` to `ArbitrateDualPipelineHandler`; every other
  invocation stays byte-identical. Dual handler gets registered in `handlers/registry.py`
  `__all__`/imports (it already structurally satisfies the `StepHandler` runtime-checkable
  Protocol — `base.py:154-158` — no base-class change needed).
- **FR-2** — arbiter evidence contract: for `kind == "scenario"` runs `ValidateTestsHandler`
  ALWAYS publishes the QA export under the reserved key
  `context.feedback["scenario_test_failures"]`; `ArbitrateVerdictHandler` POPs it
  (consume-once): `failed == 0` → PASSED with **zero** LLM calls; key absent → ERROR
  ("scenario evidence missing — wiring defect"); failures present → arbitrate with real,
  stack-trace-filtered evidence.
- **FR-3** — scenario false-green fix: `kind == "scenario"` → no pytest `-m` marker filter and
  0-collected → FAILED. Scenario-kind-scoped only; unit/integration/e2e kinds byte-identical.

Out of scope (SF-02/SF-03/add-ons): scenario-regeneration feedback, opacity e2e pins, CLI proof,
`max_retries_hitl` revival, arbiter JSON-parsing hardening.

## Research Notes (Phase 0)

Cited facts an implementer must build against (all verified 2026-07-23):

1. **Dispatch site**: `OrchestrateComponentsHandler.execute` (`core/flow/handlers/decompose.py:91`)
   currently fails first on `if not context.plan:` (`:104`) — the delegation check must come
   BEFORE that guard, since dual mode needs no DecompositionPlan. `step.params` is a plain dict
   on `PipelineStep`.
2. **Dual handler**: `ArbitrateDualPipelineHandler` (`core/flow/handlers/dual_pipeline.py:26`) is a
   plain class with `async def execute(self, step, context) -> StepResult` — satisfies the
   `StepHandler` Protocol structurally. It fans out `new_feature.yaml` + `scenario_validation.yaml`
   via `PipelineRunner(..., context=context.pipeline_runner._context, registry=..., store=...,
   on_event=...)` and compares sub-run status against `(StepStatus.PASSED, "completed")` —
   `RunStatus` is a `StrEnum` (`state.py:38`), so `RunStatus.COMPLETED == "completed"` holds.
   It requires `context.pipeline_runner` (set by the runner at `runner.py:320`) and
   `context.spec_path` — currently unguarded if `pipeline_runner` is None (see task T2 edge test).
3. **Evidence producer**: `ValidateTestsHandler.execute` (`core/flow/handlers/validation.py:371`)
   returns `output=result.exports` on both PASSED and FAILED. The QA export dict shape
   (`qa_runner/core/atom.py:225-235`):
   `{"passed", "failed", "errors", "skipped", "total", "duration_seconds", "failures": [asdict...]}`
   (+ optional `"coverage_pct"`), where each failure is `TestFailure` — `nodeid`, `message`,
   `stdout`, `stacktrace`, `rule_uri` (`commons/qa.py:15-22`).
4. **Evidence consumer**: `ArbitrateVerdictHandler.execute` (`core/flow/handlers/arbiter.py:116-131`)
   currently `context.feedback.get("run_scenario_tests", {}).get("output", {}).get("results", [])`
   — a shape nothing writes. It filters the raw text through
   `create_stack_trace_filter(context.project_path).filter(...)` (keep) and adds it to the prompt
   as label "Failures" (keep). Dead statement `if context.spec_path.exists(): pass`
   (`arbiter.py:133-134`) is removed in SF-02, NOT here.
5. **Marker mechanics**: `kind` flows `ValidateTestsHandler` → `QARunnerAtom` →
   `PythonQARunner.run_tests` where `if kind: cmd.extend(["-m", kind])`
   (`sandbox/language/core/python/runner.py:164-168`). Passing `kind=""` suppresses the marker
   filter without touching any sandbox code (AD-3: flow-layer fix only). The atom's
   `targets == []` → "All nodes pristine" SUCCESS path (`atom.py:149-163`) is unreachable for
   scenario kind because `_resolve_targets` (`validation.py:441-445`) returns `[target]` whenever
   the target is not one of the generic roots — the scenario target is the converter's concrete
   output path.
6. **Feedback-dict cohabitation**: `_extract_prompt_feedback` pops **step-name** keys
   (`generation.py:75-93`); `ConvertScenarioHandler` already publishes the non-step key
   `scenario_test_path` (`scenario.py:147`). The reserved key `scenario_test_failures` collides
   with neither (no pipeline step bears that name — enforced by a pin, task T5).
7. **Existing tests that move**:
   - `tests/unit/core/flow/handlers/test_arbiter.py` — fixture seeds the OLD fictional
     `feedback["run_scenario_tests"]["output"]["results"]` shape (line ~57); the 4 execute-path
     tests migrate to the new reserved-key QA shape. The vocabulary-guard and model tests stay.
   - `tests/unit/core/flow/handlers/test_validate_tests_handler.py` — covers happy/fail/params/
     coverage/sandbox-settings/execution_root; no scenario-kind coverage yet (new class added).
   - `tests/unit/core/flow/handlers/test_dual_pipeline.py` — 5 direct handler tests exist; none
     cover registry/dispatch reachability.
   - `tests/unit/core/flow/handlers/test_decompose.py` — orchestrate tests must gain the
     byte-identical-when-not-dual pin.
   - `tests/integration/core/flow/handlers/test_scenario_integration_e2e.py` — all-handlers-mocked
     sequencing test. Its expectation "arbitrate always visited" remains true at the engine level
     (the step still executes; it short-circuits INSIDE the handler, which is mocked there) → no
     change needed in SF-01.
8. **No new imports across module boundaries**: delegation uses a lazy in-function import of
   `ArbitrateDualPipelineHandler` inside `decompose.py` (matching the lazy-import pattern used
   throughout the handlers); `dual_pipeline.py` does not import `decompose.py` → no cycle.
   `tach check` unaffected (all edits inside `core/flow/handlers/`).

## Resolved Decisions (Phase 4 merge — pending HITL)

| Q | Decision | Resolution |
|---|----------|-----------|
| Q1 | Delegation placement | Top of `OrchestrateComponentsHandler.execute`, BEFORE the `context.plan` guard; lazy import; log the delegation at INFO. A `mode` that is set but unrecognized logs a WARNING and falls through to the existing plan path (byte-identical behavior, better diagnosis than "No DecompositionPlan" on a typo) |
| Q2 | Evidence payload shape | Raw QA export dict, untransformed (single source of truth = QA contract; arbiter adapts) |
| Q3 | Green short-circuit output | `StepResult(PASSED, output={"verdict": "no_failures", "passed": <n>, "total": <n>})` — report/state-DB friendly, no LLM call |
| Q4 | Parked/failed sub-run | Keep dual handler's current FAILED-with-message behavior; pin it with a test (NFR-5) |
| Q5 | 0-collected detection | `exports.get("total", 0) == 0` → FAILED, applied only when `kind == "scenario"`, in `ValidateTestsHandler` after the atom returns |

### Edge-case sweep refinements (user gate challenge, 2026-07-23 — all code-verified)

| # | Hole found | Refined contract |
|---|-----------|------------------|
| E1 | **Collection errors false-pass**: QA marks FAILED when `failed > 0 OR errors > 0` (`atom.py:237`) — an import crash in the generated test file yields `failed == 0, errors > 0`; a `failed == 0` short-circuit would arbitrate-PASS it | Arbiter green short-circuit requires `total > 0 AND failed == 0 AND errors == 0` |
| E2 | **`total == 0` / timeout leaks green through the continue-gate**: 0-collected (or timeout — `AtomResult.exports` defaults `{}`, `base.py:44`, so no None-crash) makes `run_scenario_tests` FAILED, gate CONTINUEs, and a naive arbiter short-circuit would PASS → run completes green with zero tests executed | Evidence with `total == 0` (or missing counts) → arbiter returns FAILED ("no scenario tests executed — nothing to arbitrate"), never PASSED. Belt to T1's handler-side guard |
| E3 | **`spec_ambiguity` park → resume breaks under consume-on-read**: pop-at-read consumes the evidence, then WAITING_FOR_INPUT parks; `sw run --resume` re-executes the arbiter → key absent → ERROR instead of re-arbitration | **Consume-on-verdict**: pop the key only on terminal branches (`no_failures`, `code_bug`, `scenario_error`); on `spec_ambiguity` (park) and ERROR the key is left intact so resume re-arbitrates. Loop re-publication overwrites staleness by construction |
| E4 | Hostile evidence shapes | Non-dict evidence value, or `failures[]` entries that aren't dicts → arbiter ERROR with a clear message, never an unhandled crash (added to T4 hostile bucket) |

**Accepted risks (documented, not fixed here):**
- Shared-context stamping race: each sub-runner re-stamps `context.run_id`/`step_records`/`pipeline_runner`
  per step (`runner.py:318-320`), so logs INSIDE the concurrent dual window may cross-attribute
  run_ids; the parent re-stamps at its next step and the state DB keys off the local `run.run_id`
  — cosmetic only, and the identical pattern already ships in `OrchestrateComponentsHandler`
  fan-out. Recorded, no change.
- A hung sub-pipeline (e.g. adapter without timeout) hangs the dual step (`ALL_COMPLETED` wait) —
  timeout ownership is adapter-level, same as every LLM handler in the engine.
- Non-python language runners: flow passes `kind=""` for scenario runs; python's runner skips the
  marker on falsy kind (`runner.py:167`) — dev task verifies the other four runners' equivalent
  guard (proof project is python).

## Task Breakdown (TDD; single commit boundary CB-1)

- **T1 — FR-3 scenario-kind semantics** (`validation.py` + `test_validate_tests_handler.py`):
  red tests first: (a) `kind: "scenario"` → atom receives `kind=""` (no marker) — the
  suppression applies at the **atom-call site only**; `_resolve_targets` keeps receiving the
  original kind (its `tests/<kind>` fallback paths are unaffected, and scenario targets take the
  concrete-path early return anyway); (b) other kinds pass through unchanged; (c) scenario run
  with `total == 0` → StepResult FAILED with an actionable message; (d) scenario run with
  failures → FAILED, exports intact; (e) unit-kind `total == 0` (pristine path) still PASSES;
  (f) NFR-3 pin: `_get_atom` / `execution_root` binding untouched (existing isolation tests stay
  green). Then implement the kind mapping + guard.
- **T2 — FR-1 dispatch** (`decompose.py`, `registry.py`; `dual_pipeline.py` only if red test (d)
  proves the None-crash + `test_decompose.py`, `test_dual_pipeline.py`): red tests first: (a) step with
  `params.mode == "dual_pipeline"` → `ArbitrateDualPipelineHandler.execute` awaited, plan guard
  never hit; (b) no mode / other mode → existing "No DecompositionPlan" behavior byte-identical;
  (c) `__all__` export pin; (d) edge: `context.pipeline_runner is None` in dual mode → clean
  FAILED/ERROR StepResult, not an AttributeError crash; (e) set-but-unrecognized mode (e.g.
  `"Dual_Pipeline"` typo) → WARNING logged, existing plan-path behavior byte-identical. Then
  implement delegation (+ the None-guard inside `dual_pipeline.py` if red test (d) proves the
  crash).
- **T3 — FR-2 producer** (`validation.py` + tests): red tests: scenario-kind run publishes
  `context.feedback["scenario_test_failures"]` with the raw QA export on PASS and on FAIL;
  non-scenario kinds never touch `context.feedback`. Then implement.
- **T4 — FR-2 consumer** (`arbiter.py` + `test_arbiter.py` migration): red tests:
  (a) `total > 0, failed == 0, errors == 0` evidence → PASSED, `context.llm.generate` NOT
  called, output `verdict: no_failures`; (b) key absent → ERROR mentioning wiring;
  (c) failures present → prompt "Failures" block contains `message` + `stacktrace` text
  (stack-trace-filtered), and the existing code_bug/scenario_error/spec_ambiguity flows work off
  the new shape (migrate the 4 existing execute-path tests); (d) **consume-on-verdict**: key
  popped after `no_failures`/`code_bug`/`scenario_error`, RETAINED after `spec_ambiguity`
  (park→resume re-arbitrates) and after ERROR; (e) E1: `failed == 0, errors > 0` → arbitrates
  (no short-circuit); (f) E2: `total == 0` or missing counts → FAILED "no scenario tests
  executed", never PASSED; (g) E4 hostile: non-dict evidence / non-dict failures entries →
  ERROR, no crash. Then implement extraction + short-circuits.
- **T5 — cross-contract pins**: (a) no bundled pipeline defines a step named
  `scenario_test_failures` (collision guard for the reserved key); (b) integration test:
  `scenario_integration.yaml` loaded with the REAL registry — `run_dual_pipelines` reaches the
  dual handler (sub-runner construction patched at `PipelineRunner` level), `run_scenario_tests`
  + `arbitrate_verdict` execute the real handlers with a mocked QA atom + mocked LLM: green path
  completes with zero LLM calls; red path arbitrates with real evidence.

**Adversarial matrix (mandatory buckets):** happy = T1a/T2a/T3/T4a-green, T5b;
boundary = T1c/T1e 0-collected vs pristine, T4d double-consume; graceful degradation = T2d
runner-absent, T4b evidence-absent, dual sub-run parked/failed (existing dual tests + new pin);
hostile = evidence key pre-seeded with garbage (non-dict) → arbiter ERROR not crash (add to T4).

**Commit boundary CB-1** (single): all tasks + full suite + pre-commit gate →
`feat(flow): make scenario_integration executable — dual dispatch, arbiter evidence, false-green fix (INT-US-24 SF-01)`.
Direct to main.

## Architecture Verification (Phase 3)

- All edits in `core/flow/handlers/` (orchestrator archetype — delegation/adaptation is its job).
- No new module-boundary imports; lazy in-function imports only; no cycles
  (`dual_pipeline.py` ↛ `decompose.py`).
- `sandbox/` untouched (AD-3); `workflows/pipelines/*.yaml` untouched (mode param already
  shipped); registry gains an import + `__all__` entry only.
- `tach check` / mypy strict: `StepHandler` is a runtime-checkable Protocol — structural
  conformance, no typing changes required.

## Session Handoff

**Current status**: DEV COMPLETE (2026-07-24) — T1–T5 + gap tests G-a/G-b/G-c all green; full
suite 5466 passed / 0 failures; quality gates clean; walkthrough written. As-built deltas: the
arbiter's dead `spec_path.exists()` statement fell out with the extraction rewrite (was SF-02
scope); the four non-python runners were verified `kind`-agnostic (accepted-risk item closed);
4 pre-existing arbiter test files migrated off the old fictional feedback shape.
**Next step**: Phase 8 commit boundary CB-1 (HITL) → then SF-02 impl plan.
