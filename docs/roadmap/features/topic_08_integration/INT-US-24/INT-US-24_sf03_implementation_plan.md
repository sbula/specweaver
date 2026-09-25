# INT-US-24 SF-03 — CLI Journey + Verifiable Proof

**Status**: APPROVED — Phase 4 (Q1-Q4 all (a) + sweep additions A1-A5/E7/E8) and Phase 5 (R/B:
stem-source pin, @trace preservation, double pop-contract, E1 counter, sequencing-test retitle)
approved by user 2026-07-24. Committed `08cffe0d` 2026-07-24. · **FRs owned**: FR-5, FR-7 (+
inherited defect #6) · **Depends on**: SF-02 · Design: [INT-US-24_design.md](INT-US-24_design.md)
§Sub-features → SF-03

## Goal

- **FR-5** — `sw run scenario_integration <spec>` with the standard display/exit-code contract:
  COMPLETED → 0; FAILED/retries-exhausted → non-zero with the arbiter's message; `spec_ambiguity`
  park → exit 0 + resume hint (INT-US-02 NFR-5/6 parity).
- **FR-7** — e2e on the REAL CLI: happy · code_bug loop→fix→green · scenario_error
  loop→regeneration · spec_ambiguity park · retries exhausted · 0-collected loud.
- `scenario_pipelines.md` dev-guide currency update; post-commit registry closure (US-24 🟢).
- DAL intake RESOLVED (a): the proof asserts the current posture (host execution, isolation
  opt-in; escalation is `C-EXEC-07`/`INT-US-09-SF06`). No isolation-on e2e scenario here.

## Where it plugs in

| Fact | Where |
|---|---|
| **Inherited defect #6 — the converter emits STUB tests**: every body is `...` — no import of the target, no call to `function_under_test`, no assertion of `expected_output` (the parametrize data at `:115-117` is decorative). Scenario tests collect and pass unconditionally, so the arbiter can never see a real failure (B-FLOW-01 FR-4 promised "executable pytest"). FR-7's code_bug scenario is untestable without the repair. `ScenarioDefinition` already carries `inputs` (kwargs), `expected_output` (Any), `category` (happy/error/boundary); `ScenarioSet.spec_path` yields the stem. | `workflows/scenarios/scenario_converter.py:97,129` |
| Harness to reuse (INT-US-02 SF-03): `ScriptedAdapter` dispatching on prompt content; `_mechanical_preset(project_dir)` (D-VAL-02 project-local mechanical-only battery); `monkeypatch state_db_path` + `SW_PROJECT` env; CLI via the real Typer app. | INT-US-02 e2e |
| Adapter needs two branches: scenario-generation prompts (marker `"Respond with a JSON object"` + `req_id` schema line) and arbitration prompts (marker `"arbitration agent"` / `"Verdict types"`). | `scenario_generator.py:220-223`; `arbiter.py:85-102` |
| QA runs pytest with `cwd=project_path`; the generated test is at `scenarios/generated/test_{stem}_scenarios.py`, the target at `src/{stem}.py` — needs packaging-free import. | QA runner |
| Exit-code/park plumbing is generic and proven: the runner parks any `WAITING_FOR_INPUT`; the CLI's parked→exit-0+resume-hint and FAILED→non-zero paths shipped with INT-US-02 (E3/E4). SF-03 pins them on this pipeline, adds no CLI code. | `runner.py:347` |
| The kotlin/rust/java/ts converters were not audited for the stub pattern; python is the proof target (the others route through `LanguageAtom`, unprovable in this repo's e2e). Follow-up currency item. | `sandbox/language/core/*` |

**US-3-boundary doubles** (Q2; evolves design AD-6): the coding sub-pipeline's internal loop
(generate_code/tests → run_tests → validate_code → review) is US-2/US-3 territory, not what US-24
proves. Class-level doubles patch `.execute` on `GenerateCodeHandler`/`GenerateTestsHandler`/
`ValidateCodeHandler`/`ReviewSpecHandler`/`ReviewCodeHandler`; `DraftSpecHandler` stays REAL (spec
exists → skip, E6 precedent). The `GenerateCodeHandler` double is the **scripted implementer**:
round 1 writes a BUGGY-but-unit-green `src/{stem}.py`, round 2 (after consuming the arbiter's
`generate_code` feedback) the FIXED one (`GenerateCodeHandler.execute` patched). `ValidateTestsHandler.execute` gets a name-dispatched
wrapper: `run_tests` (coding sub-pipeline, kind unit) → stub PASS; `run_scenario_tests` → the REAL
handler (real QA runner, real pytest subprocess). Everything scenario-side is real: contract
extraction, ScenarioGenerator (scripted LLM), converter, QA execution, arbiter, gates, park/resume
state.

Boundaries: the converter stays pure logic (`workflows/scenarios`, no I/O — the emitted TEXT gains
an importlib loader); its language-facade alias
(`sandbox/language/core/python/scenario_converter.py`) delegates, untouched. The e2e file uses
public surfaces only, CLI invoked like INT-US-02's e2e. No engine/CLI/source changes outside T1
planned; `tach` unaffected.

## Changes

TDD, red first. Single commit boundary CB-1.

1. **T1 — converter repair (defect #6)** · `src/specweaver/workflows/scenarios/scenario_converter.py`
   + `tests/unit/workflows/scenarios/test_scenario_converter.py` (+ converter-touching units)
   — emitted tests import the target via a file-anchored loader:
   `importlib.util.spec_from_file_location` on
   `Path(__file__).resolve().parents[2] / "src" / "{stem}.py"` — no sys.path games, no
   namespace-package assumptions. The stem comes from the HANDLER-known value (additive `stem`
   param threaded from `ConvertScenarioHandler` through the LanguageAtom intent); the LLM-authored
   `ScenarioSet.spec_path` is only a validated fallback (R/B RED-2). Assertion semantics
   (mechanical v1, Q3): call `target(**inputs)`; `category == "error"` → `pytest.raises(Exception)`
   around the call; else `assert result == expected_output` when `expected_output is not None`, else
   smoke-call. Parametrized groups consume `inputs,expected` for real. Every interpolated
   name/value goes through `repr()`/identifier validation — the emitted file is CODE and hostile
   LLM content must not inject statements. `# @trace(FR-X)` tags survive (C09). Existing
   stub-shape pins migrate (the stub IS the defect; NFR-1 protects call surfaces, not defective
   emission).
2. **T1b/A1 — converter-execution integration** · `tests/integration/workflows/scenarios/test_converter_execution.py`
   (NEW) — the emitted file runs under REAL pytest (via QARunnerAtom) against a real
   `src/{stem}.py`, isolating "generated tests execute and can fail" from the CLI.
3. **T2 — e2e harness** · `tests/e2e/capabilities/workflows/test_scenario_verification_e2e.py`
   (NEW) — S07-conformant spec fixture (`## Contract` python block + `## Scenarios` YAML, with a
   parametrized group of ≥2 scenarios on one function AND a single-scenario function, so both
   emitted shapes execute); `_mechanical_preset`; ScriptedAdapter (scenario-JSON queue on
   `"Respond with a JSON object"`, verdict-JSON queue on `"arbitration agent"`); the scripted
   implementer (POPs `feedback["generate_code"]` per the real contract); pass-stubs; the
   ValidateTests wrapper; `state_db_path` monkeypatch + `SW_PROJECT`; mechanical-only
   `validation_code_default` local preset (Q4).
4. **T3 — proof scenarios E1–E8** — see Tests; each drives the REAL CLI with A4 inventory asserts.
5. **T4 — docs + retitle** — `docs/dev_guides/scenario_pipelines.md` (CLI journey, evidence
   contract, scenario-kind semantics, REAL test bodies, A4's host-posture facts); the all-mocked
   `tests/integration/core/flow/handlers/test_scenario_integration_e2e.py` retitled/re-commented as
   the sequencing pin it is; post-commit registry flips (US-24 🟢, queue refresh) after CB-1.

Commit: `feat(review): scenario CLI journey + verifiable proof closes INT-US-24 (SF-03) + converter repair`.
Direct to main.

## Tests

| # | Scenario | Asserts |
|---|---|---|
| E1 | happy | COMPLETED, exit 0, the adapter's ARBITRATION branch counter == 0 (scenario-prompt calls excluded), QA export total > 0 in the run record; optionally re-run the CLI on the same project (idempotent overwrite) if runtime stays reasonable |
| E2 | code_bug loop | round-1 buggy impl FAILS real scenario tests → arbiter code_bug → loop → round-2 fixed → green; the implementer double POPs `feedback["generate_code"]` (R/B: without the pop, consume semantics drift and the vocabulary assert reads stale state); popped text vocabulary-free |
| E3 | scenario_error loop | arbiter blames scenarios → ScenarioGenerator re-called WITH the Prior-Verdict block → green |
| E4 | spec_ambiguity | park: exit 0 + resume hint, PARKED row in the (tmp-scoped) state DB |
| E5 | retries exhausted | failing verdicts × loop_back max_retries=3 → non-zero exit, arbiter message surfaced |
| E6 | zero-collected | empty ScenarioSet → converter emits no tests → `run_scenario_tests` FAILED loud → non-zero (SF-01 guard chain end-to-end) |
| E7 | park → `sw run --resume` | heal through the loop (see As built) → COMPLETED |
| E8 | generator exhaustion | garbage scenario-JSON × max_retries → handler ValueError → gate abort → sub-pipeline FAILED → dual FAILED → run FAILED, non-zero, actionable message (INT-US-02 E5 analog) |

| Tier | Case |
|---|---|
| T1 units | real bodies (single + parametrized), `pytest.raises` for error category, None-expected smoke-call; hostile: non-identifier or dotted `function_under_test` ("Class.method") → loud ValueError (v1 = plain identifiers only), repr-unsafe values, `pytest.param(..., id=...)` via `repr()` (a quote in a scenario name must not break the file), empty/garbage `spec_path` → ValueError; `@trace` preserved |
| A1 integration | green variant passes (both shapes); red variant (wrong impl) FAILS with the expected failed-count; hyphenated (non-identifier) stem loads via the file-anchored loader |
| A4 (every e2e) | EXACT droppings — `contracts/{stem}_contract.py`, `scenarios/definitions/*.yaml`, `scenarios/generated/test_*.py`, round-2 `src/{stem}.py` — and NO strays; all runs in tmp projects (state DB monkeypatched, isolation off, no worktrees or orphaned branches; `.pytest_cache` in tmp) |

Documented, not tested: resume resumes AT the parked step — spec edits between park and resume do
NOT reflow draft/validate (same as INT-US-02's resume semantics).

Adversarial matrix: happy = E1/E2-round2/E3-round2/E7-post-resume; boundary = E6, E4 park +
PARKED row, A1 both shapes, T1 None-expected/parametrize group; graceful degradation = E5, E8, A4
teardown inventories; hostile = T1/A5 injection-safety pins (emitted-code escaping incl. param
ids), E2's business-wrong impl, A1 red variant.

## Decisions (audit)

| Q | Question | Options | Chosen | Sev |
|---|----------|---------|----------|-----|
| Q1 | Converter repair in scope? | (a) fix the python converter's emitted bodies in SF-03 (fix-inherited rule; FR-7 impossible without it) · (b) mint a capability story and block SF-03 | **(a)** — bounded pure-logic change; precedent: INT-US-02 SF-03 shipped 5 inherited fixes; SF-01 shipped the same false-green class | CRITICAL |
| Q2 | US-3-boundary doubles legitimate for the proof? | (a) class-level handler doubles (scripted implementer; scenario side ALL real) · (b) full-real coding pipeline with ~6 more scripted LLM shapes | **(a)** — mirrors INT-US-02's `_POST_REVIEW_STUBS` precedent (steps outside the contract get stubbed); (b) re-proves US-3 at high brittleness for zero US-24 signal | HIGH |
| Q3 | Assertion semantics v1 | (a) equality + `pytest.raises(Exception)` for error-category · (b) richer typed-exception matching now | **(a)** — mechanical, deterministic; (b) is engine capability (`B-INTL-07`), not integration | MED |
| Q4 | Battery presets | (a) reuse `_mechanical_preset` for spec battery; add a mechanical-only `validation_code_default` local preset (works since SF-01's defect-#4 fix) — moot for validate_code under Q2(a), kept for the parent pipeline's real steps | **(a)** | LOW |

Host-posture facts (A4, documented in the dev guide): scenario artifacts persist in the user's repo
on failed/aborted runs (verification byproducts; worktree containment is `C-EXEC-07`), and
`scenarios/generated/test_*.py` is collectable by a user's bare `pytest` at repo root — teams should
exclude it in their pytest config until C-EXEC-07 contains it.

## As built (2026-07-24)

- **E7 is heal-through-the-loop.** `context.feedback` is not persisted, so on a cross-session
  resume the arbiter re-executes with the evidence ABSENT and fails with an honest message (the
  absent-evidence text names both causes — a wiring defect "or the run was resumed across sessions
  — scenario evidence is not persisted; re-run the pipeline"); that failure trips loop_back, which
  re-runs the round (fresh impl, fresh pytest, fresh evidence) → COMPLETED. Replaces the planned
  "evidence retained across park → re-arbitrate" (R/B RED-1: retention holds in-process only, still
  pinned by SF-01 units). Needed defect #10. Design FR-2 carries the correction; cross-session
  ambiguity resolution is `C-FLOW-05`/`B-INTL-07` territory.
- Five inherited defects fixed (#6 stub converter bodies, #7 pytest-parser mixed-summary false
  green, #8 dual-fan-out HITL deadlock, #9 LLMResponse contract in generator+arbiter, #10 resume
  never wired `context.llm`) — see the [walkthrough](INT-US-24_sf03_walkthrough.md).
- Two file-size REDs fixed by extraction: `_wire_llm` (flow CLI, shared by run + resume) and
  `python/pytest_output.py` (parser split, with re-export).
- Gap tests: G-a (parametrized error group + underscore-stem reject), G-b (mixed None rows,
  emission + real execution), G-c (E7b: resume adapter failure warns + degrades loud), G-d
  (stem-kwarg parity across all 5 language converters).
