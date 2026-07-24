# Design: INT-US-24 — Behavioral Scenario Verification Base Integration Contract

- **Feature ID**: INT-US-24
- **Phase**: 8 (Integration)
- **Status**: APPROVED <!-- approved by user 2026-07-23 (Phase 6 HITL gate) -->
- **Design Doc**: docs/roadmap/features/topic_08_integration/INT-US-24/INT-US-24_design.md

## Feature Overview

INT-US-24 adds the base integration contract for Behavioral Scenario Verification to the flow stack.
It solves the "syntax-green but business-wrong" gap by making the already-built Scenario Testing
Pipeline (`B-FLOW-01`: contract extraction → parallel coding + scenario pipelines → JOIN → scenario
test execution → arbiter fault attribution) actually reachable and correct end-to-end on a real CLI
journey, executed through the QA Runner (`D-VAL-01`) under the shipped US-3 isolation policy. It
interacts with `core/flow` (handlers, gates, runner), `workflows/pipelines` YAML, and the `sw run`
surface, and does NOT touch the Error Attribution Arbiter *intelligence* (`B-INTL-07`, the
"Intelligent Resolution" add-on), feature decomposition orchestration (US-21 territory), or any new
engine capability. Key constraints: integration-only (glue + inherited-defect fixes, no new
capability code), bounded token cost via the existing retry gates, INT-US-02/03 contract structure
as precedent.

## Research Findings

### Codebase Patterns

**What B-FLOW-01 actually shipped (all present in current code):**

| Component | Location | State |
|-----------|----------|-------|
| `scenario_integration.yaml` (master: contract → dual → tests → arbiter, loop_back ×3, HITL ×4) | `workflows/pipelines/` | ✅ bundled, loadable by name via `sw run` |
| `scenario_validation.yaml` (generate_scenarios → convert_to_pytest) | `workflows/pipelines/` | ✅ |
| `GenerateContractHandler` (mechanical Protocol extraction → `contracts/{stem}_contract.{ext}`, sets `context.api_contract_paths`) | `core/flow/handlers/generation.py:505` | ✅ registered |
| `GenerateScenarioHandler` / `ConvertScenarioHandler` | `core/flow/handlers/scenario.py` | ✅ registered |
| `ArbitrateVerdictHandler` + `SCENARIO_VOCABULARY` opacity guard (NFR-8) | `core/flow/handlers/arbiter.py` | ✅ registered |
| `ArbitrateDualPipelineHandler` (fans out `new_feature.yaml` + `scenario_validation.yaml` concurrently) | `core/flow/handlers/dual_pipeline.py` | ⚠️ **dead code — never registered, never dispatched** |
| Language-agnostic scenario converters + stack-trace filters (py/ts/java/kotlin/rust) | `sandbox/language/core/*` | ✅ |
| `ValidateTestsHandler` → `QARunnerAtom` with INT-US-09/C-EXEC-06 `execution_root` binding | `core/flow/handlers/validation.py:359` | ✅ |
| S07 `## Scenarios` enforcement, C09 `@trace` tags | `assurance/validation/rules/` | ✅ |

**The integration gaps (verified in current source, 2026-07-23):**

1. **Dead dispatch** — `scenario_integration.yaml`'s `run_dual_pipelines` step is
   `orchestrate`+`components` with `params.mode: dual_pipeline`. The registry maps that pair to
   `OrchestrateComponentsHandler` (`decompose.py:88`), which ignores `mode`, demands
   `context.plan` (a DecompositionPlan) — and **nothing in `src/` ever sets `context.plan`** — so
   the step always fails with "No DecompositionPlan found in context." `ArbitrateDualPipelineHandler`
   is referenced only by its own unit tests. The dual-pipeline core of US-24 is unreachable.
2. **Arbiter starves on evidence — and runs even on green** — `ArbitrateVerdictHandler` reads
   `context.feedback["run_scenario_tests"]["output"]["results"]` (`arbiter.py:118`). Nothing writes
   that key (the `run_scenario_tests` gate is `on_fail: continue`, which just advances —
   `gates.py:89`), and even if it did, `ValidateTestsHandler` exports `failures[]`
   (`commons/qa.py:15` `TestFailure`: nodeid/message/stdout/stacktrace), not `results[]` with
   `status`/`message`. Worse: because the gate is `condition: completed` + `on_fail: continue`,
   the `arbitrate_verdict` step executes **even when all scenario tests pass** — asking the LLM to
   arbitrate an empty Failures block on every happy-path run.
3. **`kind: scenario` false green** — `kind` becomes a pytest **marker filter**
   (`python/runner.py:167-168`: `-m <kind>`), and the mechanical converter emits **no**
   `pytest.mark.scenario` marker (`workflows/scenarios/scenario_converter.py`). Result:
   `pytest -m scenario` deselects every generated test → 0 collected → `QARunnerAtom` returns
   SUCCESS ("All 0 tests passed") → the behavioral verification step silently proves nothing.
4. **`scenario_error` feedback inert** — the arbiter writes
   `context.feedback["generate_scenarios"]`, but `GenerateScenarioHandler` never reads
   `context.feedback`, so on loop-back the scenario agent regenerates blind (contrast:
   `GenerateCodeHandler` consumes `feedback["generate_code"]` via `_extract_prompt_feedback`, whose
   nested `findings.results[]` shape the arbiter's `code_bug` write already matches — the coding
   side of the loop is compatible today).
5. **No real proof** — `tests/integration/core/flow/handlers/test_scenario_integration_e2e.py`
   mocks **every** handler (`StepHandlerRegistry.get` patched); it proves YAML step sequencing
   only. No test runs the chain with the real handlers, converter, or QA runner; no CLI journey
   test exists.
6. **`max_retries_hitl` is a dead field** — `GateDefinition.max_retries_hitl` (`models.py:161`,
   set to 4 in `scenario_integration.yaml`) is consulted nowhere: `_handle_loop_back`
   (`gates.py:194-231`) fails the step and stops after `max_retries`. B-FLOW-01's "HITL
   escalation after 3 arbiter loop-backs" (its NFR-5) was never implemented. Precedent:
   INT-US-02 E4 shipped exactly these bounded-fail semantics (exhaustion → loud non-zero stop)
   for the review gate — the base contract adopts the same, see NFR-5/AD-7.

**Confirmed working (no change needed):** `sw run` loads bundled pipelines by name and enforces
spec-must-exist for `scenario_integration` (`parser.py`, `flow/interfaces/cli.py:278`); with the
spec present, `new_feature.yaml`'s `draft_spec` skips (INT-US-02 E6 semantics), so the coding
sub-pipeline runs autonomously; `apply_session_policy` + `execution_root` binding give scenario
test execution the same isolation posture as INT-US-03; `StepStatus`/`RunStatus` are `StrEnum`s, so
`dual_pipeline.py`'s `"completed"` comparisons are sound; the opacity vocabulary guard
(`_guard_coding_feedback`) is implemented and unit-tested.

**Boundary rules:** all glue lands in `core/flow` (archetype: orchestrator), which already
consumes `workflows.*`, `sandbox/qa_runner/core`, and `sandbox/language/core` (existing imports in
`scenario.py`/`arbiter.py`/`validation.py`); `tach check` passes on today's import set and this
design adds **no new cross-module imports**. `sandbox/language` runners stay untouched (AD-3).

### External Tools

| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| pytest | in pyproject | marker filter `-m`, parametrize (existing) | internal |
| ruamel.yaml | in pyproject | scenario YAML load/dump (existing) | internal |

No new external dependencies.

### Blueprint References

- `docs/dev_guides/scenario_pipelines.md` — the intended dual-pipeline/arbiter behavior this
  contract makes real (guide needs a currency update in SF-03 pre-commit).
- B-FLOW-01 design (`topic_03_flow_engine/B-FLOW-01/`) — correlated-hallucination rationale,
  NFR-8 total opacity.
- External (Track B, 2026): independent test derivation and contract-first acceptance criteria are
  the prevailing direction for verifying LLM-generated code — e.g. spec-driven generation studies
  ([CodeSpecBench](https://arxiv.org/html/2604.12268v1),
  [SANER 2026 spec-driven codegen study](https://arxiv.org/html/2601.03878v1)), TDD-interactive
  generation ([TiCoder](https://www.seas.upenn.edu/~asnaik/assets/papers/tse24_ticoder.pdf)), and
  practitioner guidance on separating test derivation from implementation
  ([LLM testing overview](https://www.accelq.com/blog/llm-in-software-testing/),
  [2026 workflow playbook](https://baeseokjae.github.io/posts/llm-coding-workflow-best-practices-2026/)).
  B-FLOW-01's architecture already embodies these; the gap is purely integration.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Dual-pipeline dispatch | `OrchestrateComponentsHandler` | On `step.params.mode == "dual_pipeline"`, delegate to `ArbitrateDualPipelineHandler` (register its export); all other invocations keep byte-identical decomposition-plan behavior | `run_dual_pipelines` actually fans out `new_feature.yaml` + `scenario_validation.yaml` concurrently and JOINs on both results |
| FR-2 | Arbiter evidence contract *(refined during SF-01 planning, 2026-07-23)* | `ValidateTestsHandler` + `ArbitrateVerdictHandler` | For `kind: "scenario"` runs, ALWAYS publish the QA export (`passed`/`failed`/`errors`/`total`/`failures[]` — `TestFailure` nodeid/message/stacktrace) under the reserved key `context.feedback["scenario_test_failures"]`. The arbiter consumes it **on verdict** (popped on `no_failures`/`code_bug`/`scenario_error`; retained on `spec_ambiguity` park and on ERROR so `sw run --resume` can re-arbitrate): `total > 0 and failed == 0 and errors == 0` → StepResult PASSED **without any LLM call**; `total == 0`/missing counts → FAILED ("no scenario tests executed"); key absent → ERROR ("scenario evidence missing — wiring defect"); hostile/non-dict shapes → ERROR; failures present → arbitrate with the real (stack-trace-filtered) evidence | Happy path completes with zero arbitration cost; collection errors (`errors > 0`) and zero-collected runs can never arbitrate-pass; park→resume re-arbitrates; a broken evidence wire fails LOUD instead of green |
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

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| — | — | — | ✅ | Integration-only; no new dependencies |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Dispatch `mode: dual_pipeline` by delegation **inside** `OrchestrateComponentsHandler` (which instantiates the registered `ArbitrateDualPipelineHandler`), not via new `StepAction`/`StepTarget` enum values | Matches the shipped YAML and B-FLOW-01's original intent (`params.mode` was always the discriminator); avoids touching the engine's enum/`VALID_STEP_COMBINATIONS` model for pure glue. Alternative (new `orchestrate+dual` combo) rejected: engine-model change + YAML migration for zero behavioral gain | No |
| AD-2 | Failure evidence published handler-side under the reserved neutral key `scenario_test_failures`, ALWAYS for scenario-kind runs (pass or fail), consumed pop-once by the arbiter | `ConvertScenarioHandler` already publishes `scenario_test_path` through `context.feedback` (precedent); a neutral key survives step renames and cannot collide with step-name feedback pops; always-publish + ERROR-on-absent makes a broken evidence wire loud instead of a silent pass; a gate-level change to CONTINUE semantics would alter every pipeline using it | No |
| AD-3 | The `kind`→marker fix lives in `ValidateTestsHandler` (flow layer), not in the language runners | Atom/runner semantics ("kind = marker") stay stable for agent-facing tools; only the flow-level scenario category opts out. The 0-collected guard is also flow-level: `QARunnerAtom`'s "0 tests = success" is intentional for its pristine-targets path | No |
| AD-4 | Scenario regeneration reuses the `_extract_prompt_feedback` pop-once contract keyed `generate_scenarios` | The arbiter already writes that exact key with the compatible nested `findings.results[]` shape; mirrors the proven INT-US-02 SF-01 (drafter) and US-3 (generation) feedback patterns | No |
| AD-5 | Base-contract surface is `sw run scenario_integration` only | The MVS is US-3 Core + B-FLOW-01 + D-VAL-01. Decomposition-driven orchestration (`context.plan` is never populated anywhere — a verified gap) is **INT-US-21 territory**; arbiter intelligence upgrades are the `B-INTL-07` add-on. Neither is pulled into the base (INT-contract-vs-sub-story rule) | No |
| AD-6 | Proof harness reuses the INT-US-02 SF-03 pattern: scripted LLM adapter + real everything else; the SF-02 provider seam is NOT needed (spec pre-exists, `draft_spec` skips — E6 precedent). The adapter script must cover the coding sub-pipeline's repeat calls on loop-back (re-review of the unchanged spec, regenerated code/tests) | Deterministic, real-surface proof with no interactive channel to fake | No |
| AD-7 | Retry-exhaustion semantics = loud FAILED stop (non-zero exit), NOT HITL escalation | `max_retries_hitl` is a dead engine field (gap 6); INT-US-02 E4 shipped and the user accepted exactly these bounded-fail semantics. HITL-escalation-on-exhaustion is `B-INTL-07`/add-on scope (an engine gate change, not integration glue). The `spec_ambiguity` HITL path is unaffected — `WAITING_FOR_INPUT` parks generically (`runner.py:347`). B-FLOW-01's finished docs are NOT edited (immutability); the divergence is recorded here | No |

## ROI Analysis

### Investment Cost
| Item | Effort | Risk |
|------|--------|------|
| SF-01 dispatch + evidence + false-green (3 handler-local changes + pins) | S–M | Low — additive, flag-guarded by mode/kind |
| SF-02 feedback-aware regeneration + opacity pin | S | Low — mirrors 3 shipped feedback integrations |
| SF-03 CLI proof e2e suite (6 scenarios) + registry closure | M | Medium — e2e determinism engineering (scripted adapter scripts both pipelines' calls) |

### Returns
| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| US-24 epic | Closes with this single contract (all capability deps ✅) | Epic 🟢 |
| US-3 loop | Behavioral verification becomes a real, invocable complement to the syntax-level QA loop | High |
| INT-US-21 (Candidate 2) | The `context.plan` gap and orchestration findings recorded here de-risk its design intake | Medium |
| `B-INTL-07` add-on | Lands on a working arbiter loop instead of dead wiring | Medium |

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Arbiter's naive JSON extraction (`re.search(r"\{.*\}")`) misparses a chatty LLM response | Medium | Loop aborts with ERROR | Existing behavior kept (NFR-5); hardening belongs to `B-INTL-07`; scripted adapter in proof emits clean JSON |
| Shared `RunContext` mutated by both concurrent sub-pipelines | Low (single event loop, no awaits inside dict writes) | Cross-talk in `feedback` | Documented; keys are disjoint by construction (`draft_spec`/`generate_code` vs `generate_scenarios`/`scenario_test_path`) |
| Sub-pipeline park (HITL inside `new_feature.yaml`) surfaces as dual-step failure, not a resumable park | Medium | UX: rerun instead of resume | Documented limitation of the base contract (spec pre-exists so `draft_spec` skips; remaining park sources are retries-exhausted paths that are terminal anyway) |
| Loop-back reruns BOTH sub-pipelines (coding pipeline re-runs its own unit-test/review loops) | Certain | Token cost per arbiter round | Bounded by gate retries (NFR-2); finer-grained loop targets are add-on scope |

### Refactoring Opportunities
| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|-----------------|---------------|---------------------------|--------|
| `arbiter.py:133-134` | Dead statement `if context.spec_path.exists(): pass` | Removed in SF-02 (fix-inherited) | XS |
| `test_scenario_integration_e2e.py` | All-mocked test named "e2e" — proves sequencing only | Kept as a sequencing unit-pin but renamed/re-marked honestly in SF-03; the real proof supersedes its claim | XS |
| `handlers/registry.py` `__all__` | `ArbitrateDualPipelineHandler` unexported | Exported when registered (SF-01) | XS |
| `GateDefinition.max_retries_hitl` | Dead field — consulted nowhere in the engine | NOT fixed here (engine change, out of integration scope); recorded for `B-INTL-07` intake or a TECH story | — |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| `scenario_pipelines.md` currency update | Add the CLI journey, the arbiter evidence contract (QA `failures[]`), and the scenario-kind semantics | ⬜ To be updated during SF-03 pre-commit |

## Sub-Feature Breakdown

### SF-01: Make the Chain Executable (dispatch + evidence + false-green)
- **Scope**: The `scenario_integration` pipeline runs end-to-end with real handlers: dual-mode
  dispatch reaches `ArbitrateDualPipelineHandler`, the arbiter receives real QA failure evidence,
  and a scenario test step can never false-green on 0 collected tests.
- **FRs**: [FR-1, FR-2, FR-3]
- **Inputs**: shipped B-FLOW-01 handlers/YAML; QA export contract (`failures[]`); current registry.
- **Outputs**: dispatch delegation in `OrchestrateComponentsHandler` (+ `ArbitrateDualPipelineHandler`
  gains `StepHandler` conformance and an `__all__` export); always-published evidence key +
  corrected arbiter extraction with pass/absent short-circuits; scenario-kind marker/0-collected
  fix; unit + integration pins (incl. "arbiter makes NO LLM call on green" and "absent evidence →
  ERROR").
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-24/INT-US-24_sf01_implementation_plan.md

### SF-02: Close the Feedback Loop (scenario regeneration + opacity)
- **Scope**: Both arbiter verdict branches produce a *consuming* party: `generate_scenarios`
  becomes feedback-aware (pop-once), and NFR-8 opacity is pinned on the real integrated loop-back
  path; arbiter dead-code cleanup.
- **FRs**: [FR-4, FR-6]
- **Inputs**: SF-01 (running chain); arbiter feedback writes; `_extract_prompt_feedback` contract.
- **Outputs**: feedback-aware `GenerateScenarioHandler`; opacity integration pins; cleaned arbiter.
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-24/INT-US-24_sf02_implementation_plan.md

### SF-03: CLI Journey + Verifiable Proof
- **Scope**: `sw run scenario_integration <spec>` delivers the exit-code/display/park contract,
  proven by the 6-scenario e2e suite on the real CLI; registry closure (US-24 🟢).
- **Intake decision (DAL, raised by user 2026-07-24 — RESOLVED 2026-07-24)**: the scenario chain
  executes LLM-derived tests over LLM-generated code, but `sw run` deliberately leaves
  `dal_auto_escalate=False` (INT-US-03 AD-8 — `flow/interfaces/cli.py:326`), so unlike
  `sw implement` it never DAL-escalates into worktree isolation. **Resolution: (a) — the base
  contract keeps AD-8 and documents the posture; DAL escalation for run journeys is delivered by
  the newly minted `C-EXEC-07` (US-9 add-on, integration `INT-US-09-SF06`)**, because the flip is
  NOT integration glue: `_derive_allowed_paths` is implement-shaped, so escalation today would
  silently drop scenario artifacts (`contracts/`, `scenarios/**`) at the reconcile gate, and the
  dual fan-out has never run inside one session worktree. `C-EXEC-07`'s proof includes a real
  `scenario_integration` run. SF-03's proof asserts the CURRENT posture (opt-in isolation honored
  via `execution_root`, NFR-3).
- **FRs**: [FR-5, FR-7]
- **Inputs**: SF-01 + SF-02; INT-US-02 SF-03 harness pattern (scripted adapter); spec fixture with
  `## Contract` + `## Scenarios` sections (S07-conformant).
- **Outputs**: `tests/e2e/capabilities/workflows/test_int_us_24_scenario_e2e.py`; guide update;
  registry/roadmap flips.
- **Depends on**: SF-02
- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-24/INT-US-24_sf03_implementation_plan.md

## Execution Order

1. SF-01 (no deps — start immediately)
2. SF-02 (depends on SF-01)
3. SF-03 (depends on SF-02)

Strictly linear — no parallel sessions.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Make the Chain Executable | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Close the Feedback Loop | SF-01 | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
| SF-03 | CLI Journey + Verifiable Proof | SF-02 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: **SF-01 COMMITTED `3fece855`** (2026-07-24, direct to main) — the
scenario_integration chain is executable end-to-end (dual dispatch + arbiter evidence contract +
false-green fix); full suite 5466 passed / 0 failures. As-built: arbiter dead code removed
(was SF-02 scope); non-python runners verified kind-agnostic.
**Next step**: Implementation plan for **SF-02 — Close the Feedback Loop** (FR-4 feedback-aware
scenario regeneration + FR-6 opacity pins) via the implementation-plan skill.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and
resume from there using the appropriate skill.
