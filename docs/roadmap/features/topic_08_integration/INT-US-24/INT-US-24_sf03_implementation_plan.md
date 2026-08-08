# Implementation Plan: INT-US-24 [SF-03: CLI Journey + Verifiable Proof]

- **Feature ID**: INT-US-24
- **Sub-Feature**: SF-03 — CLI Journey + Verifiable Proof
- **Design Document**: docs/roadmap/features/topic_08_integration/INT-US-24/INT-US-24_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_08_integration/INT-US-24/INT-US-24_sf03_implementation_plan.md
- **Status**: APPROVED <!-- Phase 4 (Q1-Q4 all (a) + sweep additions A1-A5/E7/E8) and Phase 5 (R/B: stem-source pin, @trace preservation, double pop-contract, E1 counter, sequencing-test retitle) approved by user 2026-07-24 -->

## Scope (from design)

- **FR-5** — CLI journey: `sw run scenario_integration <spec>` with the standard display/exit-code
  contract (COMPLETED → 0; FAILED/retries-exhausted → non-zero with the arbiter's message;
  `spec_ambiguity` park → exit 0 + resume hint; INT-US-02 NFR-5/6 parity).
- **FR-7** — verifiable proof: e2e on the REAL CLI, six scenarios (happy · code_bug loop→fix→green ·
  scenario_error loop→regeneration · spec_ambiguity park · retries exhausted · 0-collected loud).
- Owed: `scenario_pipelines.md` dev-guide currency update; post-commit registry closure (US-24 🟢).
- DAL intake: RESOLVED (a) — proof asserts the CURRENT posture (host execution, isolation opt-in;
  escalation is `C-EXEC-07`/`INT-US-09-SF06`). No isolation-on e2e scenario here.

## Research Notes (Phase 0)

1. **INHERITED DEFECT #6 — the converter emits STUB tests** (`workflows/scenarios/
   scenario_converter.py:97,129`): every generated test body is `...` — no import of the target,
   no call to `function_under_test`, no assertion of `expected_output` (the parametrize data at
   `:115-117` is decorative). Scenario tests therefore collect and pass UNCONDITIONALLY: the
   arbiter can never receive a genuine failure and the whole behavioral verification is vacuous —
   the same false-green class as SF-01's marker bug, one layer deeper. B-FLOW-01's own FR-4
   promised "executable pytest"; executable-but-assertion-free shipped. **FR-7's code_bug scenario
   is untestable without repairing this.** The `ScenarioDefinition` model already carries
   everything a mechanical body needs: `inputs` (kwargs), `expected_output` (Any), `category`
   (happy/error/boundary), and `ScenarioSet.spec_path` yields the stem for target resolution.
2. **Harness reuse (INT-US-02 SF-03, verbatim patterns)**: `ScriptedAdapter` dispatching on
   prompt content; `_mechanical_preset(project_dir)` (D-VAL-02 project-local mechanical-only
   battery); `monkeypatch state_db_path` + `SW_PROJECT` env; CLI invoked via the real Typer app.
   For SF-03 the adapter needs only TWO content branches (both in-contract):
   scenario-generation prompts (marker: `"Respond with a JSON object"` + `req_id` schema line,
   `scenario_generator.py:220-223`) and arbitration prompts (marker: `"arbitration agent"` /
   `"Verdict types"`, `arbiter.py:85-102`).
3. **US-3-boundary doubles (the AD-6 evolution)**: the coding sub-pipeline's internal quality
   loop (generate_code/tests → run_tests → validate_code → review) is US-2/US-3 proven territory
   and NOT what US-24's sentence proves. Instead of scripting ~6 extra LLM call shapes, the proof
   installs **class-level handler doubles at that boundary** (patch `.execute` on
   `GenerateCodeHandler`/`GenerateTestsHandler`/`ValidateCodeHandler`/`ReviewSpecHandler`/
   `ReviewCodeHandler`; `DraftSpecHandler` stays REAL — spec exists → skip, E6 precedent). The
   `GenerateCodeHandler` double is the proof's **scripted implementer**: round 1 writes a
   deterministic BUGGY-but-unit-green `src/{stem}.py`, round 2 (after consuming the arbiter's
   `generate_code` feedback) writes the FIXED one — directly dramatizing "unit-green but
   business-wrong, caught by independent scenario verification."
   `ValidateTestsHandler.execute` gets a **name-dispatched wrapper**: `run_tests` (coding
   sub-pipeline, kind unit) → stub PASS; `run_scenario_tests` → the REAL handler (real QA runner,
   real pytest subprocess on the generated scenario file). Everything scenario-side is REAL:
   contract extraction, ScenarioGenerator (scripted LLM), converter, QA execution, arbiter,
   gates, park/resume state.
4. **Import mechanics for real scenario-test bodies**: QA runner executes pytest with
   `cwd=project_path`; the generated test lives at `scenarios/generated/test_{stem}_scenarios.py`
   while the target is `src/{stem}.py` — packaging-free resolution required. Mechanical approach:
   the converter emits an `importlib.util.spec_from_file_location` loader anchored on
   `Path(__file__).resolve().parents[2] / "src" / "{stem}.py"` (stem derived from
   `ScenarioSet.spec_path`). No sys.path games, no namespace-package assumptions.
5. **Assertion semantics (mechanical v1)**: call `target(**inputs)`; `category == "error"` →
   `pytest.raises(Exception)` around the call; otherwise `assert result == expected_output` when
   `expected_output is not None`, else smoke-call (must not raise). Coarse but honest — richer
   semantics (exception types, matchers) are `B-INTL-07`/capability territory.
6. **Exit-code/park plumbing is generic and already proven**: runner parks any
   `WAITING_FOR_INPUT` (`runner.py:347`); the CLI's parked→exit-0+resume-hint and FAILED→non-zero
   paths shipped with INT-US-02 (E3/E4). SF-03 pins them on THIS pipeline, adds no CLI code.
7. **Language parity note**: the kotlin/rust/java/ts converters were not audited for the same
   stub pattern; python is the proof target. Recorded as a follow-up currency item (their stems
   route through `LanguageAtom` and are unprovable in this repo's e2e anyway).

## Open Questions (Phase 2/4 — HITL)

| Q | Question | Options | Proposal | Sev |
|---|----------|---------|----------|-----|
| Q1 | Converter repair in-scope? | (a) fix the python converter's emitted bodies in SF-03 (fix-inherited rule; FR-7 impossible without it) · (b) mint a capability story and block SF-03 | **(a)** — bounded pure-logic change; exact precedent: INT-US-02 SF-03 shipped 5 inherited fixes; SF-01 shipped the same false-green class | CRITICAL |
| Q2 | US-3-boundary doubles legitimate for the proof? | (a) class-level handler doubles per Research Note 3 (scripted implementer; scenario side ALL real) · (b) full-real coding pipeline with ~6 more scripted LLM shapes | **(a)** — mirrors INT-US-02's `_POST_REVIEW_STUBS` precedent (steps outside the contract get stubbed); (b) re-proves US-3 at high brittleness for zero US-24 signal | HIGH |
| Q3 | Assertion semantics v1 | (a) equality + `pytest.raises(Exception)` for error-category (Research Note 5) · (b) richer typed-exception matching now | **(a)** — mechanical, deterministic; (b) is engine capability, not integration | MED |
| Q4 | Battery presets | (a) reuse `_mechanical_preset` for spec battery; add a mechanical-only `validation_code_default` local preset (works since SF-01's defect-#4 fix) — moot for validate_code if Q2(a) stubs it, kept for the parent pipeline's real steps | **(a)** | LOW |

## Task Breakdown (TDD; single commit boundary CB-1)

- **T1 — converter repair (inherited defect #6)** (`workflows/scenarios/scenario_converter.py` +
  `test_scenario_converter.py` + converter-touching units): red first: generated single test
  imports the target via the file-anchored loader, calls with `inputs`, asserts
  `expected_output`; parametrized group consumes `inputs,expected` for real; error-category wraps
  in `pytest.raises`; None-expected smoke-calls; hostile inputs (non-identifier function name →
  loud ValueError, not code injection; repr-unsafe values; `pytest.param` ids via `repr()`;
  empty/garbage `ScenarioSet.spec_path` — the stem source for the loader anchor — → loud
  ValueError). R/B additions: `# @trace(FR-X)` tags MUST survive the repair (C09 traceability
  contract pin); existing converter pins that assert the old stub shape migrate (expected — the
  stub IS the defect; NFR-1 protects call-surfaces, not the defective emission). Then implement.
  Adversarial focus: the emitted file is CODE — every interpolated name/value goes through
  `repr()`/identifier validation so hostile LLM content cannot inject statements.
- **T2 — e2e harness** (`tests/e2e/capabilities/workflows/test_scenario_verification_e2e.py`, NEW):
  fixtures per Research Notes 2–3: spec fixture (S07-conformant `## Contract` python block +
  `## Scenarios` YAML), `_mechanical_preset`, ScriptedAdapter (scenario-JSON + verdict-JSON
  branches), the scripted implementer double (buggy→fixed rounds), the name-dispatched
  ValidateTests wrapper, state-DB/SW_PROJECT wiring.
- **T3 — the six scenarios (FR-5 + FR-7)**, each driving the REAL CLI:
  E1 happy (COMPLETED, exit 0, the adapter's ARBITRATION branch counter == 0 (scenario-prompt
  calls excluded from the assert), scenario tests genuinely executed — assert the QA export
  total > 0 in the run record);
  E2 code_bug loop (round-1 buggy impl FAILS real scenario tests → arbiter code_bug → loop →
  round-2 fixed impl → green; the scripted-implementer double POPs `feedback["generate_code"]`
  exactly like the real handler's contract — R/B: without the pop, consume-semantics drift and
  the vocabulary assert reads stale state; assert the popped text was vocabulary-free);
  E3 scenario_error loop (arbiter blames scenarios → ScenarioGenerator re-called WITH the delta
  block → green);
  E4 spec_ambiguity (park: exit 0 + resume hint, run PARKED in state DB, evidence retained);
  E5 retries exhausted (arbiter keeps failing verdicts → loop_back max_retries=3 exhausts →
  non-zero exit, arbiter message surfaced);
  E6 zero-collected (scenario generation yields an empty ScenarioSet → converter emits no tests →
  run_scenario_tests FAILED loud → non-zero; the SF-01 guard chain end-to-end).
- **T4 — docs + closure**: `scenario_pipelines.md` currency update (CLI journey, evidence
  contract, scenario-kind semantics, REAL test bodies, A4's two host-posture facts); the
  misnamed all-mocked `test_scenario_integration_e2e.py` re-titled/re-commented as the
  sequencing pin it is (design ROI item — the real proof supersedes its claim); post-commit
  registry flips (US-24 🟢, queue refresh) — after CB-1, per governance.

### Sweep additions (user gate challenge 2026-07-24: integration/e2e/corners/unusual/teardown)

- **A1 — integration tier for the converter repair** (NEW
  `tests/integration/workflows/scenarios/test_converter_execution.py`): the emitted test file is
  written to a tmp project and REAL pytest runs it against a real `src/{stem}.py` — green variant
  (correct impl passes) AND red variant (wrong impl fails with the expected assertion) — isolating
  the "generated tests actually execute and can actually fail" seam from the CLI so e2e debugging
  never has to bisect through the whole chain. Covers both emitted shapes (single + parametrized).
- **A2 — E7 (unusual workflow): ambiguity park → `sw run --resume` → re-arbitration → COMPLETED.**
  Proves SF-01's consume-on-verdict retention END-TO-END across sessions (the exact reason the
  evidence is retained on park); scripted adapter's post-resume verdict routes `scenario_error` →
  regeneration → green. Mirrors the INT-US-02 E6/E7 journeys the user demanded there.
- **A3 — E8 (graceful failure): ScenarioGenerator retry exhaustion** — adapter returns garbage for
  all scenario-prompt attempts → handler ValueError → gate abort → sub-pipeline FAILED → dual step
  FAILED → run FAILED, non-zero exit, actionable message. The INT-US-02 E5 (provider crash) analog.
- **A4 — teardown & artifact-inventory asserts (every e2e scenario)**: assert the EXACT droppings
  (`contracts/{stem}_contract.py`, `scenarios/definitions/*.yaml`, `scenarios/generated/test_*.py`,
  round-2 `src/{stem}.py` content) and NO strays; E4 additionally asserts the PARKED row exists in
  the (tmp-scoped) state DB; all runs stay inside tmp projects (state DB monkeypatched, no
  worktrees — isolation off, no orphaned branches; `.pytest_cache` lands in tmp). **Documented
  host-posture facts (T4 dev-guide):** scenario artifacts persist in the user's repo on failed/
  aborted runs (verification byproducts; worktree containment is `C-EXEC-07`), and
  `scenarios/generated/test_*.py` is collectable by a user's bare `pytest` at repo root — teams
  should exclude it in their pytest config until C-EXEC-07 contains it.
- **A5 — T1 hostile/corner extensions**: `pytest.param(..., id=...)` emission uses `repr()` (a
  quote in a scenario name must not break the emitted file); dotted `function_under_test`
  ("Class.method") → loud ValueError (v1 = plain identifiers only, documented); the E1 fixture
  contains BOTH a parametrized group (≥2 scenarios, one function) and a single-scenario function
  so both emitted shapes execute for real; file-anchored `spec_from_file_location` tolerates
  non-identifier stems (hyphenated specs) — pinned in A1.
- **Documented, not tested**: resume resumes AT the parked step — spec edits between park and
  resume do NOT reflow draft/validate (same class as INT-US-02's documented resume semantics).
  E1 optionally re-runs the CLI a second time on the same project (idempotent overwrite of
  scenario artifacts) if runtime stays reasonable.

**Adversarial matrix:** happy = E1/E2-round2/E3-round2/E7-post-resume; boundary = E6 (empty set),
E4 park semantics + PARKED row, A1 both shapes, T1 None-expected/parametrize-group; graceful
degradation = E5 exhaustion, E8 generator exhaustion, E4 evidence retention, A4 teardown
inventories; hostile = T1/A5 injection-safety pins (emitted-code escaping incl. param ids), E2's
business-wrong impl, A1 red variant.

**Commit boundary CB-1** (single): all tasks + full suite + pre-commit →
`feat(review): scenario CLI journey + verifiable proof closes INT-US-24 (SF-03) + converter repair`.
Direct to main.

## Architecture Verification (Phase 3)

- Converter repair: pure-logic module (`workflows/scenarios`, no I/O added — emitted TEXT gains
  an importlib loader, the converter itself stays side-effect-free); its language-facade alias
  (`sandbox/language/core/python/scenario_converter.py`) is untouched (delegates).
- e2e file: tests tier, no src imports beyond public surfaces; CLI invoked like INT-US-02's e2e.
- No engine/CLI/source changes outside T1; `tach` unaffected.

## Session Handoff

**Current status**: DEV COMPLETE (2026-07-24) — T1-T4 + gap tests G-a/G-b/G-c/G-d green; the
proof (E1-E8 + E7b + A1) runs the REAL CLI end to end; full suite 5520 passed / 0 failures.
As-built deltas: FIVE more inherited defects flushed (#6 stub converter bodies, #7 pytest-parser
mixed-summary false-green, #8 dual-fan-out HITL deadlock, #9 LLMResponse contract in
generator+arbiter, #10 resume never wired context.llm); E7 redesigned to the TRUE cross-session
semantics (heal-through-the-loop; design FR-2 corrected); 2 file-size REDs fixed by extraction
(`_wire_llm`, `pytest_output.py`).
**Next step**: Phase 8 commit boundary CB-1 (HITL) → post-commit registry closure (US-24 🟢).
