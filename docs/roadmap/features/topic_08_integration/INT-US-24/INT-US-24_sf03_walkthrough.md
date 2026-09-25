# INT-US-24 SF-03 — Walkthrough

**Commit boundary:** single **CB-1** `08cffe0d` (direct to `main`, 2026-07-24) · **Plan:**
[sf03](INT-US-24_sf03_implementation_plan.md), APPROVED 2026-07-24 (Q1–Q4 all (a); the user's
five-axis sweep added A1–A5/E7/E8; R/B corrections folded) · **Closes INT-US-24 → US-24 epic 🟢**
(SF-01 `3fece855`, SF-02 `7e3cb13c`, SF-03 this CB)

## Delivered

The FR-7 proof: `tests/e2e/capabilities/workflows/test_scenario_verification_e2e.py` drives
`sw run scenario_integration` on the REAL CLI — real contract extraction, dual fan-out,
ScenarioGenerator (scripted LLM JSON), converter emitting real test bodies, pytest subprocesses,
arbiter judging real QA evidence, gates and park state. The coding sub-pipeline's internal loop
(US-2/US-3 proven) is doubled at the boundary; its `GenerateCodeHandler` double is the *scripted
implementer* writing **buggy-then-fixed** source — unit-green but business-wrong, caught only by
independent scenario verification.

| # | Scenario | Proves |
|---|----------|--------|
| E1 | happy | COMPLETED, exit 0, ZERO arbitration LLM calls, QA total>0 (tests genuinely ran), exact artifact inventory, no strays |
| E2 | code_bug loop | round-1 buggy impl FAILS real pytest → arbiter → loop → round-2 fixed → green; popped coding feedback free of ALL `SCENARIO_VOCABULARY` terms |
| E3 | scenario_error loop | wrong expectations fail → arbiter blames scenarios → regeneration WITH the Prior-Verdict block → green |
| E4 | spec_ambiguity | park: exit 0 + resume hint + PARKED row in the state DB |
| E5 | retries exhausted | bounded stop (arb ×4), non-zero, arbiter message persisted on the run record |
| E6 | zero-collected | empty ScenarioSet → loud failure, zero LLM spend (SF-01 guard chain end-to-end) |
| E7 | park → resume **heals through the loop** | evidence is NOT persisted → honest arbiter error trips loop_back → fresh verification round (fresh impl, fresh pytest, fresh evidence) → COMPLETED. Required fixing defect #10 |
| E7b | resume without LLM | adapter build fails at resume → WARNING + graceful loud degradation (defect #10's guarded branch) |
| E8 | generator exhaustion | garbage JSON ×3 → loud pipeline failure |

Plus **A1** (integration, `tests/integration/workflows/scenarios/test_converter_execution.py`):
the emitted test file executes under real pytest against a real `src/{stem}.py` — green variant,
RED variant (business-wrong impl fails with the expected count), mixed None-expected rows,
hyphenated-stem loader.

Inherited defects fixed (fix-inherited rule):

| # | Was | Now |
|---|---|---|
| 6 | The converter emitted STUB tests — every body `...`: no import, no call, no assertion; scenario verification vacuously green *(found at plan research)* | File-anchored importlib loader (stem chosen by the HANDLER, never LLM data — threaded through the `LanguageAtom` intent and an additive `stem` param on the converter interface), `target(**inputs)` calls, equality asserts, `pytest.raises` for error-category, `(function, category)`-keyed groups, `repr()`/identifier-validation everywhere (LLM content cannot inject statements), `# @trace` preserved |
| 7 | The pytest summary parser false-greened mixed outcomes: pytest orders "2 failed, 1 passed in 0.03s" failed-FIRST; the passed-first regex read failed=0 → failing runs SUCCESS in D-VAL-01's core. Failed-only lines parsed fine, which is how it survived the US-3 loop *(found by A1's red variant)* | Order-independent; `FAILED node` lines without the " - msg" suffix captured too. Extracted to `python/pytest_output.py` |
| 8 | The dual fan-out reused `new_feature.yaml` verbatim incl. INT-US-02's HITL draft gate → the coding sub parked on every first pass *(found by E1's first contact)* | The fan-out (autonomous by definition, FR-5b) downgrades HITL gates to auto |
| 9 | `ScenarioGenerator` (`.strip()`) and the arbiter (`re.search`) consumed the raw `LLMResponse` adapter return — tested only against string mocks, could never work against a real adapter | Normalized via `.text` (reviewer.py precedent) |
| 10 | `sw resume` never wired `context.llm` — every resumed LLM step degraded to "LLM not configured" errors | Resume shares the run path's guarded wiring (`_wire_llm`, one helper for both) — what lets E7's park heal through the loop |

Design corrections:
- Cross-session evidence retention does not exist: `context.feedback` is not persisted, so "retained
  on park so resume can re-arbitrate" holds only in-process. The cross-session semantics, proven by
  E7, are heal-through-the-loop: the resumed arbiter fails honestly (message names both causes), the
  loop_back re-runs the round, evidence re-publishes. Design FR-2 carries the correction; richer
  cross-session ambiguity resolution is `C-FLOW-05`/`B-INTL-07` territory.
- DAL intake resolved (a): current posture documented; escalation delegated to `C-EXEC-07` /
  `INT-US-09-SF06` (minted `37cf5fb9` from the user's "would a PO be happy?" question).

Docs: `scenario_pipelines.md` currency update (CLI journey, evidence contract, real bodies,
host-posture facts); the sequencing test retitled honestly.

## Proof

| Test | Cases |
|---|---|
| e2e | E1–E8 + E7b (9 scenarios) |
| A1 integration | ×4 |
| Converter units | real bodies, injection guards, stem contract, parametrized error groups, mixed None rows, trace preservation |
| Other units | parser-ordering ×6 · dual HITL-downgrade · LLMResponse contract ×2 · stem-parity pin across all 5 language converters · migrated pins (atom call shape) |

| Check | Result |
|---|---|
| Unit / integration / e2e (re-run from scratch after the size refactor) | 4843 · 511 · 166 — **5520 passed, 0 failures** |
| ruff · mypy (304 files) · C901 · tach · roadmap-sync | ✅ |
| file-size | 0 errors (2 RED fixed by extraction: `_wire_llm` dedup in the flow CLI; `pytest_output.py` split) |

## Findings still open

- Prompt injection via LLM text into arbitration/generation prompts: pre-existing `E-VAL-03` class,
  unchanged posture, flagged at every SF.
- The emitted-test injection surface is NEW and mechanically guarded (identifier validation +
  `repr()`), pinned by hostile units.
- Host posture (documented in `scenario_pipelines.md`): artifact droppings persist on failed runs;
  `scenarios/generated` is collectable by a user's bare pytest — exclude until `C-EXEC-07`.
- Heal-through-the-loop cost is bounded by max_retries. No fix-required findings.
- kotlin/rust/java/ts converters not audited for the stub pattern (plan follow-up).
