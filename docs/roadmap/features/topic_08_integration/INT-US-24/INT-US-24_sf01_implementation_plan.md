# INT-US-24 SF-01 — Make the Chain Executable (dispatch + evidence + false-green)

**Status**: APPROVED — Phase 4 (Q1–Q5 + E1–E4) and Phase 5 approved by user 2026-07-23. Dev complete 2026-07-24. · **FRs owned**: FR-1, FR-2,
FR-3 · **Depends on**: none · Design: [INT-US-24_design.md](INT-US-24_design.md) §Sub-features →
SF-01

## Goal

Make `scenario_integration.yaml` run end-to-end with real handlers:

- **FR-1** — `OrchestrateComponentsHandler` delegates `step.params["mode"] == "dual_pipeline"` to
  `ArbitrateDualPipelineHandler`; every other invocation stays byte-identical. The dual handler is
  registered in `handlers/registry.py` `__all__`/imports. It already satisfies the `StepHandler`
  runtime-checkable Protocol structurally (`base.py:154-158`) — no base-class change.
- **FR-2** — for `kind == "scenario"`, `ValidateTestsHandler` ALWAYS publishes the QA export under
  the reserved key `context.feedback["scenario_test_failures"]`; `ArbitrateVerdictHandler` consumes
  it: green → PASSED with **zero** LLM calls; key absent → ERROR ("scenario evidence missing —
  wiring defect"); failures present → arbitrate with real, stack-trace-filtered evidence.
- **FR-3** — `kind == "scenario"` → no pytest `-m` marker filter, and 0-collected → FAILED.
  Scenario-kind-scoped only; unit/integration/e2e kinds byte-identical.

Out of scope: scenario-regeneration feedback, opacity e2e pins, CLI proof (SF-02/SF-03);
`max_retries_hitl` revival, arbiter JSON-parsing hardening (add-ons).

## Where it plugs in

Verified 2026-07-23.

| Fact | Where |
|---|---|
| `scenario_integration.yaml`'s `run_dual_pipelines` maps to `OrchestrateComponentsHandler`, which ignores `mode` | `decompose.py:88` |
| Other design-table locations: `GenerateContractHandler` at `core/flow/handlers/generation.py:505`; `ValidateTestsHandler` → `QARunnerAtom` at `core/flow/handlers/validation.py:359` | — |
| `OrchestrateComponentsHandler.execute` fails first on `if not context.plan:` — delegation must come BEFORE that guard (dual mode needs no DecompositionPlan). `step.params` is a plain dict on `PipelineStep`. | `core/flow/handlers/decompose.py:91`, `:104` |
| `ArbitrateDualPipelineHandler` is a plain class with `async def execute(self, step, context) -> StepResult`. It fans out via `PipelineRunner(..., context=context.pipeline_runner._context, registry=..., store=..., on_event=...)` and compares sub-run status against `(StepStatus.PASSED, "completed")`; `RunStatus` is a `StrEnum` (`state.py:38`), so `RunStatus.COMPLETED == "completed"` holds. Requires `context.pipeline_runner` (set at `runner.py:320`) and `context.spec_path`; unguarded if `pipeline_runner` is None. | `core/flow/handlers/dual_pipeline.py:26` |
| `ValidateTestsHandler.execute` returns `output=result.exports` on PASSED and FAILED. Export shape: `{"passed", "failed", "errors", "skipped", "total", "duration_seconds", "failures": [asdict...]}` (+ optional `"coverage_pct"`); each failure is `TestFailure` — `nodeid`, `message`, `stdout`, `stacktrace`, `rule_uri`. | `core/flow/handlers/validation.py:371`; `qa_runner/core/atom.py:225-235`; `commons/qa.py:15-22` |
| The arbiter read `context.feedback.get("run_scenario_tests", {}).get("output", {}).get("results", [])` — a shape nothing writes (the gate is `on_fail: continue`, which just advances, `gates.py:89`). It filters text through `create_stack_trace_filter(context.project_path).filter(...)` and adds it to the prompt as "Failures" (both kept). Dead statement `if context.spec_path.exists(): pass` at `arbiter.py:133-134`. | `ArbitrateVerdictHandler.execute`, `core/flow/handlers/arbiter.py:116-131` (read at `arbiter.py:118`) |
| `kind` flows `ValidateTestsHandler` → `QARunnerAtom` → `PythonQARunner.run_tests`: `if kind: cmd.extend(["-m", kind])`. `kind=""` suppresses the filter without touching sandbox code (AD-3). The converter (`workflows/scenarios/scenario_converter.py`) emits no `pytest.mark.scenario` marker. | `sandbox/language/core/python/runner.py:164-168` (`python/runner.py:167-168`) |
| The atom's `targets == []` → "All nodes pristine" SUCCESS is unreachable for scenario kind: `_resolve_targets` returns `[target]` whenever the target is not a generic root, and the scenario target is the converter's concrete output path. | `atom.py:149-163`; `validation.py:441-445` |
| `_extract_prompt_feedback` pops **step-name** keys; `ConvertScenarioHandler` publishes the non-step key `scenario_test_path`. `scenario_test_failures` collides with neither (T5 pins it). | `generation.py:75-93`; `scenario.py:147` |
| QA marks FAILED when `failed > 0 OR errors > 0`; `AtomResult.exports` defaults `{}` on timeout. | `atom.py:237`; `base.py:44` |
| `GateDefinition.max_retries_hitl` is unused; `_handle_loop_back` stops after `max_retries` (design gap 6, not fixed here). | `models.py:161`; `gates.py:194-231` |

Tests that move:
- `tests/unit/core/flow/handlers/test_arbiter.py` — fixture seeds the old
  `feedback["run_scenario_tests"]["output"]["results"]` shape (line ~57); the 4 execute-path tests
  migrate to the reserved-key QA shape. Vocabulary-guard and model tests stay.
- `tests/unit/core/flow/handlers/test_validate_tests_handler.py` — no scenario-kind coverage yet;
  new class added.
- `tests/unit/core/flow/handlers/test_dual_pipeline.py` — 5 direct handler tests; none cover
  registry/dispatch reachability.
- `tests/unit/core/flow/handlers/test_decompose.py` — gains the byte-identical-when-not-dual pin.
- `tests/integration/core/flow/handlers/test_scenario_integration_e2e.py` — all handlers mocked.
  "Arbitrate always visited" stays true at engine level (the short-circuit is inside the mocked
  handler) → no change in SF-01.

Boundaries: delegation uses a lazy in-function import of `ArbitrateDualPipelineHandler` inside
`decompose.py` (the handlers' lazy-import pattern); `dual_pipeline.py` does not import
`decompose.py` → no cycle. All edits in `core/flow/handlers/` (orchestrator archetype);
`sandbox/` untouched (AD-3); `workflows/pipelines/*.yaml` untouched (mode param already shipped);
registry gains an import + `__all__` entry only. `tach check` / mypy strict unaffected —
`StepHandler` is a runtime-checkable Protocol, structural conformance.

## Changes

TDD, red first. Single commit boundary CB-1.

1. **T1 — FR-3 scenario-kind semantics** · `validation.py` — map `kind: "scenario"` → atom
   receives `kind=""`, at the **atom-call site only**; `_resolve_targets` keeps the original kind
   (its `tests/<kind>` fallbacks are unaffected; scenario targets take the concrete-path early
   return). Scenario run with `total == 0` → FAILED with an actionable message.
2. **T2 — FR-1 dispatch** · `decompose.py`, `registry.py` (+ `dual_pipeline.py` only if red test
   (d) proves the None-crash) — delegation at the top of `execute` (Q1); `__all__` export.
3. **T3 — FR-2 producer** · `validation.py` — scenario-kind runs publish
   `context.feedback["scenario_test_failures"]` with the raw QA export on PASS and FAIL;
   non-scenario kinds never touch `context.feedback`.
4. **T4 — FR-2 consumer** · `arbiter.py` — extraction from the reserved key + short-circuits
   (Q3, E1–E4); consume-on-verdict.
5. **T5 — cross-contract pins** — reserved-key collision guard; real-registry integration test.

Commit: `feat(flow): make scenario_integration executable — dual dispatch, arbiter evidence, false-green fix (INT-US-24 SF-01)`.
Direct to main.

## Tests

| Task | Bucket | Case |
|---|---|---|
| T1 | Happy | (a) `kind: "scenario"` → atom receives `kind=""` |
| | Happy | (b) other kinds pass through unchanged |
| | Boundary | (c) scenario run, `total == 0` → FAILED, actionable message |
| | Happy | (d) scenario run with failures → FAILED, exports intact |
| | Boundary | (e) unit-kind `total == 0` (pristine path) still PASSES |
| | Isolation | (f) NFR-3: `_get_atom` / `execution_root` binding untouched (existing isolation tests green) |
| T2 | Happy | (a) `params.mode == "dual_pipeline"` → `ArbitrateDualPipelineHandler.execute` awaited, plan guard never hit |
| | Happy | (b) no mode / other mode → "No DecompositionPlan" byte-identical |
| | Pin | (c) `__all__` export |
| | Degradation | (d) `context.pipeline_runner is None` in dual mode → clean FAILED/ERROR, not `AttributeError` |
| | Boundary | (e) set-but-unrecognized mode (`"Dual_Pipeline"`) → WARNING, plan path byte-identical |
| T3 | Happy | publishes raw QA export on PASS and on FAIL; non-scenario kinds never touch `context.feedback` |
| T4 | Happy | (a) `total > 0, failed == 0, errors == 0` → PASSED, `context.llm.generate` NOT called, `verdict: no_failures` |
| | Degradation | (b) key absent → ERROR mentioning wiring |
| | Happy | (c) failures → "Failures" block has `message` + `stacktrace` (filtered); code_bug/scenario_error/spec_ambiguity work off the new shape (4 migrated tests) |
| | Boundary | (d) consume-on-verdict: popped after `no_failures`/`code_bug`/`scenario_error`; RETAINED after `spec_ambiguity` and ERROR |
| | Boundary | (e) E1: `failed == 0, errors > 0` → arbitrates, no short-circuit |
| | Boundary | (f) E2: `total == 0` or missing counts → FAILED "no scenario tests executed" |
| | Hostile | (g) E4: non-dict evidence / non-dict failures entries (key pre-seeded with garbage) → ERROR, no crash |
| T5 | Pin | (a) no bundled pipeline defines a step named `scenario_test_failures` |
| | Integration | (b) `scenario_integration.yaml` through the REAL registry — `run_dual_pipelines` reaches the dual handler (sub-runner patched at `PipelineRunner` level); `run_scenario_tests` + `arbitrate_verdict` run real handlers with mocked QA atom + LLM: green path, zero LLM calls; red path arbitrates real evidence |

Also: dual sub-run parked/failed → FAILED-with-message (existing dual tests + new pin, Q4).

## Decisions (audit)

| Q | Decision | Resolution |
|---|----------|-----------|
| Q1 | Delegation placement | Top of `OrchestrateComponentsHandler.execute`, BEFORE the `context.plan` guard; lazy import; log the delegation at INFO. A `mode` that is set but unrecognized logs a WARNING and falls through to the existing plan path (byte-identical behavior, better diagnosis than "No DecompositionPlan" on a typo) |
| Q2 | Evidence payload shape | Raw QA export dict, untransformed (single source of truth = QA contract; arbiter adapts) |
| Q3 | Green short-circuit output | `StepResult(PASSED, output={"verdict": "no_failures", "passed": <n>, "total": <n>})` — report/state-DB friendly, no LLM call |
| Q4 | Parked/failed sub-run | Keep dual handler's current FAILED-with-message behavior; pin it with a test (NFR-5) |
| Q5 | 0-collected detection | `exports.get("total", 0) == 0` → FAILED, applied only when `kind == "scenario"`, in `ValidateTestsHandler` after the atom returns |

Edge refinements (user gate challenge, 2026-07-23 — all code-verified):

| # | Hole | Contract |
|---|-----------|------------------|
| E1 | **Collection errors false-pass**: an import crash in the generated test yields `failed == 0, errors > 0`; a `failed == 0` short-circuit would arbitrate-PASS it | Green short-circuit requires `total > 0 AND failed == 0 AND errors == 0` |
| E2 | **`total == 0` / timeout leaks green through the continue-gate**: `run_scenario_tests` FAILED, gate CONTINUEs, a naive short-circuit would PASS → run green with zero tests | `total == 0` (or missing counts) → arbiter FAILED ("no scenario tests executed — nothing to arbitrate"), never PASSED. Belt to T1's handler-side guard |
| E3 | **`spec_ambiguity` park → resume breaks under consume-on-read**: pop-at-read, then park; `sw run --resume` re-runs the arbiter → key absent → ERROR | **Consume-on-verdict**: pop only on `no_failures`, `code_bug`, `scenario_error`; on `spec_ambiguity` (park) and ERROR the key stays so resume re-arbitrates. Loop re-publication overwrites staleness. (In-process only — see design FR-2 correction.) |
| E4 | Hostile evidence shapes | Non-dict evidence, or non-dict `failures[]` entries → ERROR with a clear message, never an unhandled crash |

Accepted risks:
- Shared-context stamping race: each sub-runner re-stamps `context.run_id`/`step_records`/`pipeline_runner`
  per step (`runner.py:318-320`), so logs inside the concurrent dual window may cross-attribute
  run_ids; the parent re-stamps at its next step and the state DB keys off the local `run.run_id` —
  cosmetic; the same pattern ships in `OrchestrateComponentsHandler` fan-out.
- A hung sub-pipeline (e.g. adapter without timeout) hangs the dual step (`ALL_COMPLETED` wait) —
  timeout ownership is adapter-level, as for every LLM handler.

## As built (2026-07-24)

- The arbiter's dead `spec_path.exists()` statement fell out with the extraction rewrite (planned
  for SF-02).
- The four non-python runners ignore `kind`, so `kind=""` is safe across all five languages
  (python's runner skips the marker on falsy kind, `runner.py:167`).
- 4 pre-existing arbiter test files migrated off the old feedback shape.
- Gap tests G-a/G-b/G-c added; full suite 5466 passed / 0 failures. Walkthrough:
  [sf01](INT-US-24_sf01_walkthrough.md).
