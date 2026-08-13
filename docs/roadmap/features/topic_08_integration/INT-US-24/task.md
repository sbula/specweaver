# Task List — INT-US-24 SF-03: CLI Journey + Verifiable Proof (SF-01 `3fece855`, SF-02 `7e3cb13c`)

- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-24/INT-US-24_sf03_implementation_plan.md (APPROVED)
- **FRs**: FR-5 (CLI exit-code/park contract) + FR-7 (verifiable proof) + inherited defect #6 (stub converter)
- **Commit boundary**: single **CB-1** — closes INT-US-24 → **US-24 epic 🟢**.

## Tasks (SF-03)

- [x] **T1 — converter repair (inherited defect #6: stub bodies)**
  - Source: `src/specweaver/workflows/scenarios/scenario_converter.py`
  - Tests: `tests/unit/workflows/scenarios/test_scenario_converter.py` (extend + migrate stub pins)
  - Red: single test imports target via file-anchored `spec_from_file_location` (stem from the
    HANDLER-known value — additive `stem` param threaded from `ConvertScenarioHandler` through the
    LanguageAtom intent; LLM-authored `ScenarioSet.spec_path` is only a validated fallback, R/B
    RED-2), calls `target(**inputs)`, asserts `expected_output`; parametrized
    group consumes `inputs,expected` for real; error-category → `pytest.raises(Exception)`;
    expected None → smoke-call; `# @trace` tags preserved; hostile: non-identifier / dotted
    `function_under_test` → ValueError (no injection), `pytest.param` ids via `repr()`,
    empty/garbage `spec_path` → ValueError; existing stub-shape pins migrate (the stub IS the
    defect).
- [x] **T1b/A1 — converter-execution integration test**
  - Tests: `tests/integration/workflows/scenarios/test_converter_execution.py` (NEW)
  - Red: emitted file written to tmp project + REAL pytest (via QARunnerAtom) against real
    `src/{stem}.py`: green variant passes (both shapes: single + parametrized); red variant
    (wrong impl) FAILS with the expected failed-count; hyphenated (non-identifier) stem loads
    fine via the file-anchored loader.
- [x] **T2 — e2e harness**
  - Tests: `tests/e2e/capabilities/workflows/test_scenario_verification_e2e.py` (NEW; fixtures only
    in this task, proven red by a first skeletal scenario)
  - Pieces: S07-conformant spec fixture (`## Contract` python block + `## Scenarios` YAML;
    parametrized group + single-scenario function); `_mechanical_preset` (D-VAL-02 local
    battery); ScriptedAdapter branches (scenario-JSON queue on `"Respond with a JSON object"`,
    verdict-JSON queue on `"arbitration agent"`); scripted-implementer double for
    `GenerateCodeHandler.execute` (round 1 buggy / round 2 fixed; POPs `feedback["generate_code"]`
    per the real contract); pass-stubs for `GenerateTestsHandler`/`ValidateCodeHandler`/
    `ReviewSpecHandler`/`ReviewCodeHandler`; name-dispatched `ValidateTestsHandler.execute`
    wrapper (`run_tests`→stub PASS, `run_scenario_tests`→REAL); `state_db_path` monkeypatch +
    `SW_PROJECT`; DraftSpecHandler REAL (skip on existing spec).
- [x] **T3 — proof scenarios E1–E8** (each drives the REAL CLI; A4 artifact-inventory asserts in each)
  - E1 happy: COMPLETED, exit 0, arbitration-branch counter == 0, QA total > 0 in run record,
    artifact inventory exact (contract file, definitions YAML, generated test, src), no strays.
  - E2 code_bug: round-1 buggy impl FAILS real scenario tests → arbiter code_bug → loop →
    round-2 fixed → COMPLETED; popped coding feedback vocabulary-free.
  - E3 scenario_error: arbiter blames scenarios → ScenarioGenerator re-called WITH the
    Prior-Verdict block → green.
  - E4 spec_ambiguity: park — exit 0 + resume hint, PARKED row in state DB, evidence retained.
  - E5 retries exhausted: failing verdicts × max_retries=3 → non-zero exit, arbiter message
    surfaced.
  - E6 zero-collected: empty ScenarioSet → converter emits no tests → run_scenario_tests FAILED
    loud → non-zero (SF-01 guard chain end-to-end).
  - E7 (redesigned per R/B RED-1 — feedback is NOT persisted cross-session): park → resume →
    the arbiter re-executes with the evidence ABSENT → fails LOUD with the extended honest
    message (arbiter absent-evidence text gains: "or the run was resumed across sessions —
    scenario evidence is not persisted; re-run the pipeline"); non-zero exit. In-process
    retention stays pinned by SF-01 units; cross-session ambiguity resolution recorded as
    HITL-channel capability territory (C-FLOW-05 / B-INTL-07). Small source touch:
    `arbiter.py` absent-evidence message only.
  - E8 generator retry exhaustion: garbage scenario-JSON × max_retries → handler ValueError →
    gate abort → dual FAILED → non-zero, actionable message.
- [x] **T4 — docs + retitle**
  - `docs/dev_guides/scenario_pipelines.md`: CLI journey, evidence contract, scenario-kind
    semantics, REAL test bodies, host-posture facts (artifacts persist on failed runs;
    `scenarios/generated` collectable by bare user pytest — exclude until C-EXEC-07).
  - `tests/integration/core/flow/handlers/test_scenario_integration_e2e.py`: retitle/re-comment
    as the all-mocked sequencing pin it is.
  - Post-commit (after CB-1): registry closure — US-24 🟢, queue refresh.

## Inherited defects flushed during dev (fix-inherited rule)
- **#7 pytest summary parser false-green**: mixed "N failed, M passed" lines (pytest's real
  order) parsed as failed=0 → failing runs reported SUCCESS (failed-only lines parsed fine,
  which is how it survived US-3). Order-independent parser + optional " - msg" FAILED lines.
- **#8 dual fan-out vs HITL gates**: sub-pipelines reused new_feature.yaml VERBATIM incl. the
  INT-US-02 HITL draft gate → coding sub parked on every first pass. Fan-out now downgrades
  HITL gates to auto (autonomous by definition, FR-5b).
- **#9 LLMResponse contract**: ScenarioGenerator (`.strip()`) and the arbiter (`re.search`)
  consumed the raw adapter return — only ever tested against string mocks; could never work in
  production. Normalized via `.text` (reviewer.py precedent).
- **#10 `sw resume` never wired context.llm**: every resumed LLM step silently degraded to
  "LLM not configured" errors. Resume now mirrors the run path's guarded wiring — this is what
  lets E7's park heal through the loop.

## Adversarial matrix (4 buckets)
- Happy: T1 single+parametrized real bodies, A1 green, E1, E2-round2, E3, E7-post-resume.
- Boundary: E4 park + PARKED row, E6 empty set, T1 expected-None smoke, A1 hyphenated stem, @trace preservation.
- Graceful degradation: E5 exhaustion, E8 generator exhaustion, E4 evidence retention, A4 teardown inventories.
- Hostile: T1 injection pins (identifier validation, repr ids, garbage spec_path), A1 red variant, E2 business-wrong impl.

## Pre-Commit Gate (CB-1)
- [x] Phase 1 — architecture: converter repair pure-logic; parser fix in its runner home; resume wiring at the CLI composition root; additive interface params; tach ✅; no new boundaries
- [x] Phase 2 — test gap analysis: matrix presented; gaps G-a/G-b/G-c/G-d approved
- [x] Phase 3 — G-a (parametrized error group + underscore-stem reject), G-b (mixed None rows,
  emission + real execution), G-c (E7b: resume adapter-failure warns + degrades loud), G-d
  (stem-kwarg parity across all 5 language converters) — all green
- [x] Phase 4 — full suite re-run from scratch AFTER the size refactor: unit 4843 · integration 511 · e2e 166 = 5520 passed, 0 failures
- [x] Phase 5 — ruff ✅ · mypy ✅ (304 files) · C901 ✅ · tach ✅ · roadmap-sync ✅ · file-size: 2 RED
  introduced by SF-03 fixed by EXTRACTION (flow CLI `_wire_llm` dedup shared by run+resume; parser
  split to `python/pytest_output.py` with re-export) → 0 errors
- [x] Phase 6 — scenario_pipelines.md currency update (CLI journey, evidence contract, real bodies, host-posture facts); sequencing test retitled honestly; task.md + impl-plan records
- [x] Phase 7 — INT-US-24_sf03_walkthrough.md written
- [x] Phase 7.5 — emitted-test injection surface (NEW) mechanically guarded (identifier validation +
  repr, hostile pins); prompt-injection via LLM text = pre-existing E-VAL-03 class, unchanged;
  heal-through-loop cost bounded by max_retries; cross-session semantics corrected in design FR-2;
  no fix-required findings
- [x] Phase 8 — CB-1 committed `08cffe0d` (direct to main, 2026-07-24). **INT-US-24 COMPLETE → US-24 epic 🟢.**
