# Walkthrough — INT-US-24 SF-03: CLI Journey + Verifiable Proof

- **Commit boundary**: single **CB-1** (direct to `main`). Impl plan APPROVED 2026-07-24
  (Q1–Q4 all (a); the user's five-axis sweep added A1–A5/E7/E8; R/B corrections folded).
- **Closes INT-US-24 → US-24 epic 🟢** (SF-01 `3fece855`, SF-02 `7e3cb13c`, SF-03 this CB).

## What changed and why

The FR-7 proof: `tests/e2e/capabilities/workflows/test_int_us_24_scenario_e2e.py` drives
`sw run scenario_integration` on the REAL CLI — real contract extraction, real dual fan-out,
real ScenarioGenerator (scripted LLM JSON), real converter emitting REAL test bodies, real
pytest subprocesses executing them, real arbiter judging real QA evidence, real gates/park
state. The coding sub-pipeline's internal quality loop (US-2/US-3 proven) is doubled at the
boundary; its `GenerateCodeHandler` double is the *scripted implementer* writing
deterministically **buggy-then-fixed** source — dramatizing the exact US-24 sentence:
unit-green but business-wrong, caught only by independent scenario verification.

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

Plus **A1** (integration): the emitted test file executes under real pytest against a real
`src/{stem}.py` — green variant, RED variant (business-wrong impl genuinely fails with the
expected count), mixed None-expected rows, hyphenated-stem loader.

## The proof earned its keep — 5 MORE inherited defects found & fixed

6. **The converter emitted STUB tests** *(found at plan Phase 0)* — every body was `...`: no
   import, no call, no assertion; scenario verification was vacuously green by construction.
   Repaired: file-anchored importlib loader (stem chosen by the HANDLER, never LLM data —
   threaded through the `LanguageAtom` intent and an additive `stem` param on the converter
   interface), `target(**inputs)` calls, equality asserts, `pytest.raises` for error-category,
   `(function, category)`-keyed groups, `repr()`/identifier-validation everywhere (LLM content
   cannot inject statements), `# @trace` preserved.
7. **The pytest summary parser false-greened mixed outcomes** *(found by A1's red variant)* —
   pytest orders "2 failed, 1 passed in 0.03s" failed-FIRST; the passed-first regex parsed it
   as failed=0 → failing runs reported SUCCESS in D-VAL-01's core. (Failed-only lines parsed
   fine — that's how it survived the US-3 loop.) Now order-independent; `FAILED node` lines
   without the " - msg" suffix are captured too. Extracted to `python/pytest_output.py`.
8. **The dual fan-out deadlocked on INT-US-02's HITL gate** *(found by E1's first contact)* —
   sub-pipelines reused `new_feature.yaml` verbatim incl. the HITL draft gate → the coding sub
   parked on every first pass. The fan-out (autonomous by definition, FR-5b) now downgrades
   HITL gates to auto.
9. **`ScenarioGenerator` and the arbiter consumed raw adapter returns** — `.strip()`/`re.search`
   on an `LLMResponse` object; both were only ever tested against string mocks and could never
   work against a real adapter. Normalized via `.text` (reviewer.py precedent).
10. **`sw resume` never wired `context.llm`** — every resumed LLM-dependent step silently
    degraded to "LLM not configured" errors. Resume now shares the run path's guarded wiring
    (`_wire_llm`, one helper for both) — this is what lets E7's park heal through the loop.

## Design corrections discovered en route

- **Cross-session evidence retention is a myth**: `context.feedback` is not persisted, so the
  SF-02-era claim "retained on park so resume can re-arbitrate" holds only in-process. The
  honest cross-session semantics — proven by E7 — are *heal-through-the-loop*: the resumed
  arbiter fails honestly (message names both causes), the loop_back re-runs the round, evidence
  re-publishes naturally. Design FR-2 carries the correction marker; richer cross-session
  ambiguity resolution is `C-FLOW-05`/`B-INTL-07` territory.
- **DAL intake resolved (a)**: current posture documented; escalation delegated to `C-EXEC-07`
  / `INT-US-09-SF06` (minted `37cf5fb9` from the user's "would a PO be happy?" question).

## Tests

E1–E8 + E7b e2e (9 scenarios) · A1 integration ×4 · converter units (real bodies, injection
guards, stem contract, parametrized error groups, mixed None rows, trace preservation) ·
parser-ordering units ×6 · dual HITL-downgrade unit · LLMResponse-contract units ×2 ·
stem-parity pin across all 5 language converters · migrated pins (atom call shape).

**Full suite (pre-commit Phase 4, re-run from scratch after the size refactor):** unit 4843 ·
integration 511 · e2e 166 — **5520 passed, 0 failures.**
**Quality:** ruff ✅ · mypy ✅ (304 files) · C901 ✅ · file-size 0 errors (2 RED fixed by
extraction: `_wire_llm` dedup in the flow CLI; `pytest_output.py` split) · tach ✅ ·
roadmap-sync ✅.

## Red/Blue (Phase 7.5) — see task.md record

Prompt-injection via LLM text into arbitration/generation prompts remains the pre-existing
`E-VAL-03` class (unchanged posture, flagged at every SF). The emitted-test injection surface
is NEW and is mechanically guarded (identifier validation + `repr()`), pinned by hostile units.
Host-posture facts documented in `scenario_pipelines.md` (artifact droppings on failed runs;
`scenarios/generated` collectable by a user's bare pytest — exclude until `C-EXEC-07`).
