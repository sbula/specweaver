# Task List — INT-US-24 SF-02: Close the Feedback Loop (SF-01 record: `3fece855` + walkthrough)

- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-24/INT-US-24_sf02_implementation_plan.md (APPROVED)
- **FRs**: FR-4 (feedback-aware scenario regeneration) + FR-6 (opacity through the integrated loop)
- **Commit boundary**: single **CB-1** — tasks T1–T3, then pre-commit gate + HITL commit stop.

## Tasks (SF-02)

- [x] **T1 — ScenarioGenerator feedback param**
  - Source: `src/specweaver/workflows/scenarios/scenario_generator.py`
  - Tests: `tests/unit/workflows/scenarios/test_scenario_generator.py`
  - Red: (a) `feedback="..."` → prompt contains a labeled prior-verdict block with the text,
    placed before the output-schema instructions; (b) omitted/None → prompt byte-identical to
    today's; (c) feedback block persists in the retry prompt after an invalid first LLM response
    (built-once prompt); (d) hostile feedback text (fences/braces/fake headings) lands verbatim
    as text, prompt assembly does not break.
- [x] **T2 — handler consumption (pop-once + call-site guard)**
  - Source: `src/specweaver/core/flow/handlers/scenario.py` (GenerateScenarioHandler only)
  - Tests: `tests/unit/core/flow/handlers/test_scenario_handlers.py`
  - Red: (a) arbiter-shaped `feedback["generate_scenarios"]` → `generate_scenarios` called with
    the extracted `"[FR-x] message"` text, key POPPED, INFO log emitted (NFR-4); (b) no feedback →
    `feedback=None`, `context.feedback` untouched (byte-identical); (c) unrelated feedback keys
    (`scenario_test_failures`, `generate_code`) survive; (d) malformed findings value (non-dict)
    → treated as no-feedback + WARNING, no crash — via a CALL-SITE guard (`_extract_prompt_feedback`
    itself stays untouched for its three coding-side consumers).
- [x] **T3 — seam-chain pins (FR-6 opacity + FR-4 chain + YAML contract)**
  - Tests: `tests/integration/core/flow/handlers/test_scenario_integration_dispatch.py` (extend)
  - Red: (a) FR-6: real `ArbitrateVerdictHandler` with a LEAKY `code_bug` LLM verdict → guard
    rewrites → real `GenerateCodeHandler` (Generator + assemblers mocked, patch set mirroring
    `test_build_base_prompt_profiles`) → captured `validation_findings` kwarg contains the guarded
    text and NO `SCENARIO_VOCABULARY` term; (b) FR-4: real arbiter `scenario_error` → real
    `GenerateScenarioHandler` (ScenarioGenerator mocked) → feedback kwarg carries the behavioral
    delta, `generate_scenarios` key popped; (c) YAML step-name contract: `new_feature.yaml` names
    a step `generate_code` AND `scenario_validation.yaml` names a step `generate_scenarios`
    (the fixed keys the arbiter writes — a silent rename would strand verdict feedback).

## Adversarial matrix (4 buckets)
- Happy: T1a, T2a, T3a, T3b.
- Boundary: T1c (retry persistence), T2c (unrelated-keys survival), T3c (step-name contract).
- Graceful degradation: T2d (malformed findings → no-feedback + warning).
- Hostile: T1d (hostile feedback text); T3a's leaky vocabulary is the hostile input on the arbiter side.

## Pre-Commit Gate (CB-1)
- [x] Phase 1 — architecture: 2 source files (workflows/scenarios additive kwarg; core/flow handler same-package import); tach ✅; no new boundaries
- [x] Phase 2 — test gap analysis: matrix presented; gaps G-a/G-b approved
- [x] Phase 3 — G-a (empty-string feedback == None) + G-b (dictator-shaped feedback tolerated, remarks knowingly dropped, key consumed) — green
- [x] Phase 4 — full suite re-run from scratch: unit 4815 · integration 507 · e2e 157 = 5479 passed, 0 failures
- [x] Phase 5 — ruff ✅ · mypy ✅ (303 files) · C901 ✅ · file-size 0 errors · tach ✅ · roadmap-sync ✅
- [x] Phase 6 — task.md record + impl-plan handoff; dev-guide currency update remains SF-03 (per design)
- [x] Phase 7 — INT-US-24_sf02_walkthrough.md written
- [x] Phase 7.5 — no fix-required findings (prompt-injection = E-VAL-03 class, unchanged; consume-on-malformed safe via per-round re-publication; guard except observable)
- [ ] Phase 8 — commit boundary (HITL hard stop)
