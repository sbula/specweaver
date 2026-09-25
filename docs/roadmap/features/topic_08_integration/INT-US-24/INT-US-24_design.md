# INT-US-24 — Behavioral Scenario Verification: Base Integration Contract

**Status**: APPROVED — approved by user 2026-07-23 (Phase 6 HITL gate). **COMPLETE** — SF-01 `3fece855`, SF-02 `7e3cb13c`, SF-03 `08cffe0d` (2026-07-24);
US-24 epic 🟢. · **Phase**: 8 (Integration) · **Feature ID**: INT-US-24

| | |
|---|---|
| Integrates | `B-FLOW-01` (Scenario Testing Pipeline) · `D-VAL-01` (QA Runner) · US-3 Core isolation policy |
| Precedent | INT-US-02/03 contract structure |
| Touches | `core/flow` (handlers, gates, runner) · `workflows/pipelines` YAML · `sw run` |
| Not touched | Error Attribution Arbiter *intelligence* (`B-INTL-07`, "Intelligent Resolution" add-on) · feature decomposition orchestration (US-21) · any new engine capability |
| Follow-ups | `C-EXEC-07` / `INT-US-09-SF06` (DAL escalation for run journeys) · `INT-US-24-SF01` + `B-INTL-07` add-ons |

## What it does

Makes the shipped Scenario Testing Pipeline (`B-FLOW-01`: contract extraction → parallel coding +
scenario pipelines → JOIN → scenario test execution → arbiter fault attribution) reachable and
correct end-to-end on a real CLI journey, `sw run scenario_integration <spec>`, executed through the
QA Runner (`D-VAL-01`) under the shipped US-3 isolation policy.

It closes the "syntax-green but business-wrong" gap: generated code is checked against scenarios
derived independently of the implementation.

Constraints: integration only (glue + inherited-defect fixes, no new capability code); token cost
bounded by the existing retry gates.

## Why — what blocked the shipped pipeline

`B-FLOW-01` shipped every piece, but the chain did not run. Verified in source 2026-07-23 (line refs
in the [SF-01 plan](INT-US-24_sf01_implementation_plan.md)):

1. **Dead dispatch** — `run_dual_pipelines` (`orchestrate`+`components`, `params.mode:
   dual_pipeline`) routed to `OrchestrateComponentsHandler`, which ignores `mode` and demands
   `context.plan` — which nothing in `src/` sets — so it always failed with "No DecompositionPlan
   found in context." `ArbitrateDualPipelineHandler` was never registered, never dispatched.
2. **Arbiter starved of evidence, and ran even on green** — it read
   `context.feedback["run_scenario_tests"]["output"]["results"]`, which nothing writes;
   `ValidateTestsHandler` exports `failures[]` (`TestFailure`: nodeid/message/stdout/stacktrace),
   not `results[]`. With the gate `condition: completed` + `on_fail: continue`, `arbitrate_verdict`
   ran on every happy path, arbitrating an empty Failures block.
3. **`kind: scenario` false green** — `kind` becomes `pytest -m <kind>`; the converter emits no
   `pytest.mark.scenario` marker, so every test was deselected → "All 0 tests passed" → SUCCESS.
4. **`scenario_error` feedback inert** — the arbiter writes `context.feedback["generate_scenarios"]`;
   `GenerateScenarioHandler` never read it, so the scenario agent regenerated blind. (The coding
   side already worked: `GenerateCodeHandler` consumes `feedback["generate_code"]` via
   `_extract_prompt_feedback`, whose nested `findings.results[]` shape the arbiter's `code_bug`
   write matches.)
5. **No real proof** — `tests/integration/core/flow/handlers/test_scenario_integration_e2e.py`
   patched `StepHandlerRegistry.get` and mocked every handler; it proved YAML sequencing only. No
   CLI journey test existed.
6. **`max_retries_hitl` is a dead field** — `GateDefinition.max_retries_hitl` (set to 4 in
   `scenario_integration.yaml`) is consulted nowhere; `_handle_loop_back` fails and stops after
   `max_retries`. B-FLOW-01's "HITL escalation after 3 arbiter loop-backs" (its NFR-5) was never
   built. Not fixed here — see AD-7.

SF-03 found five more inherited defects (#6–#10: stub converter bodies, pytest-parser mixed-summary
false green, dual fan-out HITL deadlock, `LLMResponse` contract, `sw resume` never wiring
`context.llm`) — see the [SF-03 walkthrough](INT-US-24_sf03_walkthrough.md).

Already correct, no change: `sw run` loads bundled pipelines by name and enforces spec-must-exist
for `scenario_integration` (`parser.py`, `flow/interfaces/cli.py:278`); with the spec present,
`new_feature.yaml`'s `draft_spec` skips (INT-US-02 E6), so the coding sub-pipeline runs
autonomously; `apply_session_policy` + `execution_root` give scenario test execution the INT-US-03
isolation posture; `StepStatus`/`RunStatus` are `StrEnum`s, so `dual_pipeline.py`'s `"completed"`
comparisons are sound; the opacity guard (`_guard_coding_feedback`) is implemented and unit-tested.

## Architecture

What `B-FLOW-01` shipped, and where it lives:

| Component | Location | State at intake |
|-----------|----------|-------|
| `scenario_integration.yaml` (master: contract → dual → tests → arbiter, loop_back ×3, HITL ×4) | `workflows/pipelines/` | bundled, loadable by name via `sw run` |
| `scenario_validation.yaml` (generate_scenarios → convert_to_pytest) | `workflows/pipelines/` | ✅ |
| `GenerateContractHandler` (mechanical Protocol extraction → `contracts/{stem}_contract.{ext}`, sets `context.api_contract_paths`) | `core/flow/handlers/generation.py` | registered |
| `GenerateScenarioHandler` / `ConvertScenarioHandler` | `core/flow/handlers/scenario.py` | registered |
| `ArbitrateVerdictHandler` + `SCENARIO_VOCABULARY` opacity guard (NFR-8) | `core/flow/handlers/arbiter.py` | registered |
| `ArbitrateDualPipelineHandler` (fans out `new_feature.yaml` + `scenario_validation.yaml` concurrently) | `core/flow/handlers/dual_pipeline.py` | dead code → wired in SF-01 |
| Language-agnostic scenario converters + stack-trace filters (py/ts/java/kotlin/rust) | `sandbox/language/core/*` | ✅ |
| `ValidateTestsHandler` → `QARunnerAtom` with INT-US-09/C-EXEC-06 `execution_root` binding | `core/flow/handlers/validation.py` | ✅ |
| S07 `## Scenarios` enforcement, C09 `@trace` tags | `assurance/validation/rules/` | ✅ |

**Boundaries:** all glue lands in `core/flow` (archetype: orchestrator), which already consumes
`workflows.*`, `sandbox/qa_runner/core` and `sandbox/language/core` (existing imports in
`scenario.py`/`arbiter.py`/`validation.py`). `tach check` passes; **no new cross-module imports**.
`sandbox/language` runners stay untouched (AD-3).

Dependencies: pytest (marker filter `-m`, parametrize) and ruamel.yaml (scenario YAML), both
existing, in pyproject. No new external dependencies.

References:
- `docs/dev_guides/scenario_pipelines.md` — the dual-pipeline/arbiter behavior this contract makes
  real (currency update delivered in SF-03).
- B-FLOW-01 design (`topic_03_flow_engine/B-FLOW-01/`) — correlated-hallucination rationale, NFR-8
  total opacity.
- External (Track B, 2026): independent test derivation and contract-first acceptance criteria are
  the prevailing direction for verifying LLM-generated code —
  [CodeSpecBench](https://arxiv.org/html/2604.12268v1),
  [SANER 2026 spec-driven codegen study](https://arxiv.org/html/2601.03878v1),
  [TiCoder](https://www.seas.upenn.edu/~asnaik/assets/papers/tse24_ticoder.pdf),
  [LLM testing overview](https://www.accelq.com/blog/llm-in-software-testing/),
  [2026 workflow playbook](https://baeseokjae.github.io/posts/llm-coding-workflow-best-practices-2026/).
  B-FLOW-01 already embodies these; the gap was integration.

## Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Dispatch `mode: dual_pipeline` by delegation **inside** `OrchestrateComponentsHandler` (which instantiates the registered `ArbitrateDualPipelineHandler`), not via new `StepAction`/`StepTarget` enum values | Matches the shipped YAML and B-FLOW-01's intent (`params.mode` was always the discriminator); avoids touching the engine's enum/`VALID_STEP_COMBINATIONS` model for glue. Rejected: a new `orchestrate+dual` combo — engine-model change + YAML migration for zero behavioral gain | No |
| AD-2 | Failure evidence published handler-side under the reserved neutral key `scenario_test_failures`, ALWAYS for scenario-kind runs (pass or fail), consumed pop-once by the arbiter | `ConvertScenarioHandler` already publishes `scenario_test_path` through `context.feedback` (precedent); a neutral key survives step renames and cannot collide with step-name feedback pops; always-publish + ERROR-on-absent makes a broken evidence wire loud instead of a silent pass; a gate-level change to CONTINUE semantics would alter every pipeline using it | No |
| AD-3 | The `kind`→marker fix lives in `ValidateTestsHandler` (flow layer), not in the language runners | Atom/runner semantics ("kind = marker") stay stable for agent-facing tools; only the flow-level scenario category opts out. The 0-collected guard is also flow-level: `QARunnerAtom`'s "0 tests = success" is intentional for its pristine-targets path | No |
| AD-4 | Scenario regeneration reuses the `_extract_prompt_feedback` pop-once contract keyed `generate_scenarios` | The arbiter already writes that key with the compatible nested `findings.results[]` shape; mirrors the INT-US-02 SF-01 (drafter) and US-3 (generation) feedback patterns | No |
| AD-5 | Base-contract surface is `sw run scenario_integration` only | The MVS is US-3 Core + B-FLOW-01 + D-VAL-01. Decomposition-driven orchestration (`context.plan` is never populated anywhere) is **INT-US-21 territory**; arbiter intelligence upgrades are the `B-INTL-07` add-on. Neither is pulled into the base (INT-contract-vs-sub-story rule) | No |
| AD-6 | Proof harness reuses the INT-US-02 SF-03 pattern: scripted LLM adapter + real everything else; the SF-02 provider seam is NOT needed (spec pre-exists, `draft_spec` skips — E6 precedent). The adapter script must cover the coding sub-pipeline's repeat calls on loop-back (re-review of the unchanged spec, regenerated code/tests) | Deterministic, real-surface proof with no interactive channel to fake. As built, the coding sub-pipeline is doubled at the US-3 boundary instead (SF-03 Q2) | No |
| AD-7 | Retry-exhaustion semantics = loud FAILED stop (non-zero exit), NOT HITL escalation | `max_retries_hitl` is a dead engine field (gap 6); INT-US-02 E4 shipped and the user accepted exactly these bounded-fail semantics. HITL-escalation-on-exhaustion is `B-INTL-07`/add-on scope (an engine gate change, not integration glue). The `spec_ambiguity` HITL path is unaffected — `WAITING_FOR_INPUT` parks generically (`runner.py:347`). B-FLOW-01's finished docs are NOT edited (immutability); the divergence is recorded here | No |
| DAL | `sw run` keeps `dal_auto_escalate=False` (INT-US-03 AD-8 — `flow/interfaces/cli.py:326`), so unlike `sw implement` it never DAL-escalates into worktree isolation. Raised by user 2026-07-24, RESOLVED 2026-07-24 to **(a)**: keep AD-8, document the posture; escalation for run journeys is the newly minted `C-EXEC-07` (US-9 add-on, integration `INT-US-09-SF06`) | The flip is not integration glue: `_derive_allowed_paths` is implement-shaped, so escalation today would silently drop scenario artifacts (`contracts/`, `scenarios/**`) at the reconcile gate, and the dual fan-out has never run inside one session worktree. `C-EXEC-07`'s proof includes a real `scenario_integration` run. SF-03's proof asserts the current posture (opt-in isolation honored via `execution_root`, NFR-3) | No |

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Dual-pipeline dispatch | `OrchestrateComponentsHandler` | On `step.params.mode == "dual_pipeline"`, delegate to `ArbitrateDualPipelineHandler` (register its export); all other invocations keep byte-identical decomposition-plan behavior | `run_dual_pipelines` actually fans out `new_feature.yaml` + `scenario_validation.yaml` concurrently and JOINs on both results |
| FR-2 | Arbiter evidence contract *(refined during SF-01 planning, 2026-07-23)* | `ValidateTestsHandler` + `ArbitrateVerdictHandler` | For `kind: "scenario"` runs, ALWAYS publish the QA export (`passed`/`failed`/`errors`/`total`/`failures[]` — `TestFailure` nodeid/message/stacktrace) under the reserved key `context.feedback["scenario_test_failures"]`. The arbiter consumes it **on verdict** (popped on `no_failures`/`code_bug`/`scenario_error`; retained on `spec_ambiguity` park and on ERROR for IN-PROCESS re-arbitration/retry — *SF-03 planning correction (2026-07-24): `context.feedback` is not persisted, so a CROSS-SESSION resume re-arbitrates with the key absent and fails loud with an honest message; cross-session ambiguity resolution is C-FLOW-05/B-INTL-07 territory*): `total > 0 and failed == 0 and errors == 0` → StepResult PASSED **without any LLM call**; `total == 0`/missing counts → FAILED ("no scenario tests executed"); key absent → ERROR ("scenario evidence missing — wiring defect"); hostile/non-dict shapes → ERROR; failures present → arbitrate with the real (stack-trace-filtered) evidence | Happy path completes with zero arbitration cost; collection errors (`errors > 0`) and zero-collected runs can never arbitrate-pass; park→resume re-arbitrates; a broken evidence wire fails LOUD instead of green |
| FR-3 | Scenario false-green fix | `ValidateTestsHandler` | For `kind: "scenario"` ONLY: do NOT pass a pytest marker filter (the generated-file target path is the discriminator), and treat a run that collects 0 tests as FAILED (guard is scenario-kind-scoped — the atom's intentional "pristine targets = success" path for incremental unit runs is untouched) | A scenario verification step can never pass by deselecting/collecting nothing; behavior for `kind` unit/integration/e2e unchanged |
| FR-4 | Feedback-aware scenario regeneration | `GenerateScenarioHandler` | Consume `context.feedback["generate_scenarios"]` pop-once via the `_extract_prompt_feedback` contract and inject the arbiter's `scenario_error` findings into the regeneration prompt; without feedback, byte-identical | The scenario agent regenerates against the behavioral delta instead of blind; feedback is consumed exactly once (INT-US-02 SF-01 precedent) |
| FR-5 | CLI journey | `sw run scenario_integration <spec>` | Execute the full chain (contract → dual pipelines → scenario tests → arbiter loop) with the standard display and exit-code contract | COMPLETED → exit 0; FAILED/retries-exhausted → non-zero with the arbiter's message surfaced; `spec_ambiguity` HITL park → exit 0 + resume hint (INT-US-02 NFR-5/6 parity) |
| FR-6 | Opacity through the integrated loop | flow engine + vocabulary guard | On a `code_bug` loop-back, the coding pipeline's regeneration prompt contains no scenario vocabulary (guard `SCENARIO_VOCABULARY` applied on the real path) | Pinned by an e2e assertion on the actual prompt sent to the scripted adapter — NFR-8 holds in integration, not just in the guard's unit tests |
| FR-7 | Verifiable proof | e2e suite | Drive the REAL CLI (`sw run scenario_integration`) with a scripted LLM adapter and real contract extraction, converter, QA runner, gates, and state: happy path; `code_bug` loop → fix → green; `scenario_error` loop → regeneration with feedback; `spec_ambiguity` → park; retries exhausted → bounded non-zero stop; 0-collected → loud failure | The US-24 sentence ("proves the generated code solves the business scenario, not just syntax tests") is demonstrated end-to-end; supersedes the all-mocked sequencing test as the contract proof |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Backward compatibility | Zero behavior change for `mode != dual_pipeline`, `kind != scenario`, and absent feedback keys; full existing suite stays green (5437+ tests at design time) |
| NFR-2 | Bounded cost | No new LLM call sites; the happy path performs **zero** arbitration LLM calls (FR-2 short-circuit); loop bounded by the existing `max_retries: 3` gate in `scenario_integration.yaml` (token-burn breakers remain `B-FLOW-05`, queue Candidate 5) |
| NFR-3 | Isolation posture | Scenario test execution (LLM-derived tests over LLM-generated code) keeps the INT-US-03/C-EXEC-06 wiring: `execution_root` binding in `ValidateTestsHandler._get_atom` untouched and asserted in the proof when session isolation is on |
| NFR-4 | Observability | Dual fan-out start/JOIN result, arbiter verdict + spec clause, and the false-green guard each emit `logger.info`/`warning` (extends B-FLOW-01 NFR-3) |
| NFR-5 | Graceful degradation | A parked/failed sub-pipeline yields a FAILED dual step with the sub-pipeline's error message (no hangs — `ALL_COMPLETED` wait); LLM verdict JSON that fails to parse yields an ERROR StepResult (existing behavior, kept); arbiter-loop exhaustion → loud FAILED stop + non-zero exit (INT-US-02 E4 parity — `max_retries_hitl` is engine-dead, see AD-7) |

## Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Arbiter's naive JSON extraction (`re.search(r"\{.*\}")`) misparses a chatty LLM response | Medium | Loop aborts with ERROR | Existing behavior kept (NFR-5); hardening belongs to `B-INTL-07`; scripted adapter in proof emits clean JSON |
| Shared `RunContext` mutated by both concurrent sub-pipelines | Low (single event loop, no awaits inside dict writes) | Cross-talk in `feedback` | Documented; keys are disjoint by construction (`draft_spec`/`generate_code` vs `generate_scenarios`/`scenario_test_path`) |
| Sub-pipeline park (HITL inside `new_feature.yaml`) surfaces as dual-step failure, not a resumable park | Medium | UX: rerun instead of resume | Documented limitation (spec pre-exists so `draft_spec` skips; remaining park sources are retries-exhausted paths that are terminal anyway) |
| Loop-back reruns BOTH sub-pipelines (coding pipeline re-runs its own unit-test/review loops) | Certain | Token cost per arbiter round | Bounded by gate retries (NFR-2); finer-grained loop targets are add-on scope |
| Prompt injection via LLM/test text into arbitration and regeneration prompts | — | — | Pre-existing class, not widened; `E-VAL-03` scope (queue Candidate 4) |

Open: `GateDefinition.max_retries_hitl` stays a dead field — engine change, out of integration
scope; recorded for `B-INTL-07` intake or a TECH story.

## Sub-features

| SF | Does | FRs | Depends on | Plan |
|----|------|-----|-----------|------|
| SF-01 | Make the chain executable: dual-mode dispatch reaches `ArbitrateDualPipelineHandler` (`StepHandler` conformance + `__all__` export); always-published evidence key + arbiter extraction with pass/absent short-circuits; scenario-kind marker/0-collected fix; pins incl. "arbiter makes NO LLM call on green" and "absent evidence → ERROR". | FR-1, FR-2, FR-3 | — | [sf01](INT-US-24_sf01_implementation_plan.md) |
| SF-02 | Close the feedback loop: `generate_scenarios` becomes feedback-aware (pop-once); NFR-8 opacity pinned on the real integrated loop-back path; arbiter dead-code cleanup. | FR-4, FR-6 | SF-01 | [sf02](INT-US-24_sf02_implementation_plan.md) |
| SF-03 | CLI journey + proof: `sw run scenario_integration <spec>` exit-code/display/park contract, proven by the e2e suite on the real CLI (`tests/e2e/capabilities/workflows/test_scenario_verification_e2e.py`, spec fixture with `## Contract` + `## Scenarios`, S07-conformant); `scenario_pipelines.md` update; the all-mocked `test_scenario_integration_e2e.py` retitled as the sequencing pin it is; registry closure (US-24 🟢). | FR-5, FR-7 | SF-02 | [sf03](INT-US-24_sf03_implementation_plan.md) |

Strictly linear — no parallel sessions.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Make the Chain Executable | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Close the Feedback Loop | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | CLI Journey + Verifiable Proof | SF-02 | ✅ | ✅ | ✅ | ✅ | ✅ |

Closed 2026-07-24: registry flipped, queue refreshed (US-21 → Candidate 1, C-EXEC-07 enters at
rank 5).
