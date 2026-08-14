# Implementation Plan: Integration-Contract Proof Audit [SF-04: The `sw implement` loop e2e]

- **Feature ID**: TECH-017
- **Sub-Feature**: SF-04 — The `sw implement` loop e2e
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-017/TECH-017_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-04
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-017/TECH-017_sf04_implementation_plan.md
- **Status**: DELIVERED 2026-08-14

## Scope

Write the proof that five claims already carry a verdict of `unproven` for want of it:
`INT-US-03` C1, C3, C4, C6 and `INT-US-24` C5. Closing them also closes the `FR-6` findings
against `D-INTL-01` and `D-VAL-05`.

The audit's other three sub-features assessed. **This one builds** — it is the only place `AD-2`'s
*"fixed in place, not filed"* requires writing rather than reading.

## What Phase 0 found

### Every existing "implement loop" test doubles the thing SF-04 must exercise

Three tests look like they cover this pipeline. None runs `D-INTL-01`:

| Test | What it doubles | What it therefore proves |
|---|---|---|
| `test_implement_loop_worktree_isolation_e2e.py` | generation, by a **bash script** | isolation, not the loop |
| `test_scenario_verification_e2e.py` | **`GenerateCodeHandler.execute`** itself | the verification loop, with the implementer scripted |
| `test_implement_pipeline.py` | nothing — it reads the **declared shape** | five steps in order and a loop-back gate exist |

So the shape SF-04 needs is the one nobody has used: **script the LLM adapter and let the real
`GenerateCodeHandler` run.** That is precisely the difference between *the pipeline is wired* and
*`D-INTL-01` pipes into `D-VAL-01` and `D-VAL-05`*, which is what the contract claims.

The pipeline under test:
`generate_code → generate_tests → lint_fix → run_tests (loop_target=generate_code) → validate_code`.

### The harness exists and one half of it is load-bearing

`ScriptedLLM` + `scripted_world` live in `test_feature_decomposition_e2e.py`. `scripted_world`
patches `create_llm_adapter` **and** forces `ModelRouter.get_for_task` to `None`, because otherwise
the router builds a real provider around the factory patch — its comment records that a live
provider was *"found for real in `INT-US-02`'s e2e"*. Any extraction must carry both patches or it
reintroduces a bug someone already paid for.

## Decisions taken at the Phase 4 gate

- **D-1 — the harness moves to `tests/scripted_llm.py` and is imported explicitly.** Same shape as
  `tests/rendering.py`. An import line makes *"this test doubles the LLM"* visible at the call site;
  a conftest fixture would hide it, which is how `INT-US-24`'s doubling went unnoticed until its
  docstring was read during CB-3.
- **D-2 — C4 is closed only by observing two generations, the second green.** Assert
  `generate_code` was reached **twice** and that `run_tests` failed then passed. Anything less proves
  the gate is *declared*, which `test_implement_pipeline.py` already covers.
- **D-3 — if driving real `ruff` and real `pytest` twice proves brittle, keep the real handler and
  drop assertions on generated-code quality**, not the other way round. Script minimal code both
  tools accept and assert the iteration and stage sequence. That still closes C4 and C6; C3 would
  then need a narrower test. Falling back to doubling the handler is explicitly rejected — it
  reproduces `test_scenario_verification_e2e` and leaves `D-INTL-01` unexercised, which is the whole
  point of this sub-feature.

## What this plan carries

| | Where it lands |
|---|---|
| `FR-1` claim extraction | **not applicable** — SF-03 CB-1 extracted the last contract; stated rather than omitted |
| `FR-2` per-claim verdict | CB-3, re-verdicting the five claims this proof closes |
| `FR-3` tier verdict | the new test is **e2e**; the claims are a user-visible journey |
| `FR-4` fix in place | the sub-feature *is* `FR-4` — write the missing test |
| `FR-5` escalate only decisions | *What is NOT filed* |
| `FR-6` capability findings | `D-INTL-01` and `D-VAL-05` rows close in CB-3 |
| `NFR-1` immutability | no contract re-worded; the verdicts change because the proof changed |
| `NFR-2` evidence | each re-verdict names the new test function |
| `NFR-3` no net ticket growth | *What is NOT filed* |
| `NFR-4` incremental | three boundaries, each committable |
| `AD-1` the matrix is a document | verdicts copied in by hand |
| `AD-2` fixed in place, not filed | the reason this sub-feature exists |
| `AD-3` `docs/analysis/` is the matrix's home | CB-3 lands there |
| `AD-4` worst-first | n/a — one journey, not a set of entries |

## Commit boundaries

### CB-1 — Extract the harness to `tests/scripted_llm.py`

Move `ScriptedLLM` and `scripted_world`, **carrying both patches**, and update
`test_feature_decomposition_e2e.py` to import them.

No new coverage: this is a refactor whose proof is that `INT-US-21`'s 24 e2e scenarios still pass
unchanged. Run them in isolation as well as in the suite — SF-02 and SF-03 both found width-flakes
that only appear that way.

Done when: `tests/scripted_llm.py` exists, the decomposition e2e imports it, and its 24 tests pass
at COLUMNS 60/80/200.

### CB-2 — The e2e: real handler, scripted LLM, observed loop

Steps:
1. Script the LLM to emit **buggy** code + tests on the first `generate_code`, and **fixed** code on
   the second.
2. Drive the real CLI: `sw implement <spec>`.
3. Assert, per D-2: `generate_code` reached twice; `run_tests` failed then passed; the run completes.
4. Assert `validate_code` ran (C3) and that generation fed QA (C6) — the `D-INTL-01` → `D-VAL-01` /
   `D-VAL-05` pipe.
5. Keep isolation **off**. Worktree-bounded QA is already proven by
   `test_implement_loop_worktree_isolation_e2e.py`; mixing it in here would make a brittle test
   brittler for no new claim.

**Done when the test kills a mutant, not when it passes** (implementation-plan skill). The expected
mutant: remove `loop_target="generate_code"` from the `run_tests` gate. A test that still passes
without the loop-back is not proving C4, whatever it asserts. Record the mutant and its result.

### CB-3 — Re-verdict and close the capability findings

Update `INT-US-03` C1/C3/C4/C6 and `INT-US-24` C5 in the matrix, naming the new test function
(`NFR-2`). Close the `FR-6` rows for `D-INTL-01` and `D-VAL-05`, or narrow them to what remains.

Done when: no claim in the matrix is `unproven` for a reason this sub-feature was scoped to fix,
and the `FR-6` table states which rows closed.

## What is NOT filed (FR-5, NFR-3)

If D-3's fallback is taken, the residue — C3's *"runs C01–C08"* proven only narrowly — is recorded as
a verdict with its reason, not as a ticket. A ticket is filed only if the loop turns out to be
**unbuildable as specified**, which would be a scope decision and the user's call.

The audit has filed zero tickets across three sub-features. SF-04 holds that bar.

## Risks

| # | Risk | Mitigation |
|---|---|---|
| R-1 | The scripted LLM must emit code real `ruff` lints and real `pytest` runs, twice | D-3's fallback, decided in advance so it is not improvised under pressure |
| R-2 | The extraction drops `ModelRouter.get_for_task` → `None` and a live provider is built | CB-1's done-when is the decomposition e2e passing unchanged; that suite is what caught it originally |
| R-3 | The e2e passes without the loop ever looping | CB-2's done-when is a killed mutant on `loop_target`, not a green run |
| R-4 | A long real-`pytest`-in-`pytest` e2e is slow or flaky under `-n auto` | Measure its runtime at CB-2 and state it. If it exceeds ~30s, mark it `e2e` and consider excluding it from the default tier rather than letting it rot |
| R-5 | Scope creep into proving isolation as well | D-3 and CB-2 step 5: isolation stays off, and the existing e2e keeps that claim |

## Outcome, 2026-08-14

Delivered across three boundaries. **Four claims closed, not five** — `INT-US-24` C5 was narrowed
instead, because its own e2e still doubles `GenerateCodeHandler` and SF-04's test proves a different
contract's journey. Both `FR-6` rows (`D-INTL-01`, `D-VAL-05`) closed. Final: 51 / 9 / 4.

**D-3's fallback was not needed** — real `ruff` and real `pytest` drove twice without trouble, and
the file runs in ~6s, well inside R-4's 30s threshold, so it stays in the default tier.

**R-3 was the risk that paid off.** Its mitigation — *done when a mutant dies, not when it passes* —
is what turned this from three green tests into the audit's most productive boundary. C4 initially
got a split verdict because `lint_fix` merely ran in the flow without being asserted on; rather than
record that residue, a fourth test now feeds the loop a correct-but-lint-dirty draft, and deleting
the `lint_fix` step kills it. (`max_reflections: 3 → 0` survives, correctly: auto-fix is ruff's phase
one, not an LLM reflection.)

**Two live defects surfaced, and the ordering between them is the lesson.** `pytest -m unit`
deselected every generated test — so every `sw implement` run collected nothing and rendered `0
passed, 0 failed` as a tick — and zero-collected was reported as success. The guard for the second
was written first, broke nine tests, and was reverted: with collection broken everywhere, failing
loud on an empty run failed every run. Converting a false green into a universal red is not a fix.
Collection was fixed in `f4435e75`, then the guard landed clean in `faab6dcb`.

Four of those nine tests had been reaching their assertions *through* the false green and now say
what they mean. The telemetry one got stronger: it proves the flush is owed on a **failed** run,
because it happens in `PipelineRunner._finalize`'s `finally`.
