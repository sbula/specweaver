# Walkthrough: INT-US-21 SF-01 CB-4 — HITL Approve-on-Resume (FR-4)

- **Design**: `INT-US-21_design.md` (APPROVED 2026-07-25)
- **Plan**: `INT-US-21_sf01_implementation_plan.md` (APPROVED 2026-07-25)
- **Commit boundary**: 4 of 4 (CB-1 `f1de38f1`, CB-2 `c4c1a109`, CB-3 `6811a943`)
- **Date**: 2026-07-25

---

## What changed and why

The last of the four inherited engine gaps. `GateEvaluator` parks HITL gates unconditionally and
`resume()` only flipped the run status back to RUNNING — so the loop re-executed the step, the gate
re-parked, and the run could **never** advance. Resuming a reviewed gate-park now *is* the approval.

| File | Change |
|---|---|
| `core/flow/engine/approval.py` | **NEW** — `is_approvable_gate_park()` (pure predicate) + `try_approve_parked_step()` |
| `core/flow/engine/runner.py` | `resume()` passes `approve_parked=True`; approval branch at the top of the loop body; staleness bypass extracted |
| `core/flow/engine/runner_utils.py` | `execute_run` threads `approve_parked` |
| `core/flow/engine/staleness.py` | **NEW** — `try_staleness_bypass()` extracted out of the loop (and out of `runner_utils`) |
| `docs/architecture/.../domain_flow_engine.md` | New "HITL Approve-on-Resume" section |
| `docs/user_guides/4_interactive_hitl_gates.md` | **Approve-on-resume semantics for users** — pulled forward from SF-03 (see below) |
| `tests/unit/core/flow/engine/test_approve_on_resume.py` | **NEW** — 15 tests |
| `tests/e2e/.../test_int_us_02_drafter_e2e.py` | E6/E7 re-asserted honestly; 3 fixture defects fixed |
| `tests/integration/.../test_pipeline_state_persistence.py` | Obsolete `gate = None` workaround removed |
| `tests/integration/.../test_rehydration_integration.py` | Observation points moved past the now-approved step |
| `tests/unit/interfaces/api/v1/test_pipelines.py` | REST approve→resume routing pinned (D7) |

The negative cases carry most of the weight — approving the wrong park flavour would skip a step
that never ran. All four are tested: handler-park, failed gate-park, RESERVE-park (stored `PENDING`),
and AUTO-gate park all re-execute; only `WAITING_FOR_INPUT` + stored `PASSED` + HITL gate approves.

---

## Test results

| Suite | Result |
|---|---|
| Unit | **4957 passed**, 15 skipped |
| Integration | **523 passed**, 3 skipped, 15 deselected |
| E2E | **166 passed**, 1 skipped |
| **Grand total** | **5646 passed, 19 skipped** |

CB-3 baseline was 5629. Net **+17**.

## Quality gates

`ruff` ✅ · `mypy` ✅ (306 files) · `C901` ✅ · file sizes ✅ **0 errors** · `tach` ✅ · roadmap sync ✅.

---

## What re-asserting E6/E7 uncovered

D2 required E6/E7 to become honest proofs. Doing that surfaced **three pre-existing defects and one
of my own wrong assumptions** — all invisible before, because the run never got past `draft_spec`.

1. **The fixture spec could never pass the real battery.** `MANUAL_SPEC` carried only a `Purpose`
   section; the S-battery reported *"6 rules executed, 4 passed, 2 failed"* and the pipeline aborted.
   The test's stated purpose — *"resume → new chain validates+reviews it"* — was unachievable with
   its own fixture. Replaced with a spec of the shape the Drafter's template produces; now 6/6 pass.

2. **The tests were making live Gemini API calls.** `ReviewSpecHandler` prefers
   `context.llm_router.get_for_task(...)` over `context.llm` (`review.py:32-36`), and `sw run` /
   `sw resume` inject a real `ModelRouter`. Patching only `create_llm_adapter` left the router free
   to build a **real** adapter — observed directly as `Review LLM call failed: 429
   RESOURCE_EXHAUSTED`. An e2e test presented as fully mocked was hitting a paid API on every run;
   it only became visible once approve-on-resume let the run reach `review_spec`. Now patched to
   defer to the scripted adapter.

3. **The post-review stub could not satisfy `review_code`.** That gate uses `condition: accepted`,
   which reads `result.output["verdict"]`; the stub returned a bare `PASSED`, so it looped back to
   `generate_code` and exhausted `max_retries`. Fixed by having the stub carry
   `verdict: "accepted"`.

4. **My own session-count claim was wrong — twice.** The plan (D2) said E6 and E7 would each become
   *three*-session journeys. In reality E7's spec pre-exists, so session 1 parks at the *gate*, not
   a handler park; and a reviewer rejection adds a loop_back that parks again. I corrected it to
   "two" and was still wrong. The tests now **drive to terminal with a bounded loop** and assert the
   terminal status rather than a hard-coded count — the number of parks is a property of the
   pipeline, not something a test should encode.

E6/E7 now assert **`status == "completed"` read from the persisted run**, plus a drained scripted
verdict queue. `exit_code == 0` was never proof: PARKED and COMPLETED both exit 0, which is exactly
why they were vacuously green.

> This is the **fourth and fifth** vacuous-proof instance in this feature, after INT-US-02's exit-code
> assertions, `_AlwaysPassHandler` overwriting the registry, and `PIPELINES_DIR` pointing at a path
> that made two tests silently skip. SF-03 should treat existing coverage as unverified until read.

---

## Red/Blue (Phase 7.5) — 1 finding, fixed

**A renamed step could be approved on another step's result.** The predicate checked record status,
result status and gate type — but not identity. A pipeline YAML edited between sessions keeps the
same index and gate, so a *different* step could be skipped entirely on the strength of the old
step's stored result. This is the same hazard CB-3's rehydration name-guard closes, and it surfaced
because a CB-3 integration test started failing for the "wrong" reason. `is_approvable_gate_park`
now requires `record.step_name == step_def.name`, with a warning and a unit test.

---

## Two extractions forced by the file-size gate

`runner.py` hit the 600-line RED threshold for the **third time in this sub-feature**. Rather than
shave lines again, two loop short-circuits moved out — both are "complete the current step and
advance without executing a handler", so they are cohesive as a concept:

1. `try_approve_parked_step` → **`engine/approval.py`**, with the AD-2 decision table as a pure,
   exhaustively-testable predicate alongside it.
2. `try_staleness_bypass` (Feature 3.32 SF-4) → **`engine/staleness.py`** (see the correction below).

`runner.py` is now 584 lines. Both extractions are behaviour-preserving, verified by the 43 existing
`stale_nodes` references and the full suite.

**Correction after review.** `try_staleness_bypass` initially went into `engine/runner_utils.py`,
which the user rightly called out: a module whose name promises nothing accretes anything, and I
had reached for it precisely *because* it had no contract to violate. Relocated to
**`engine/staleness.py`**, named for Feature 3.32 SF-4's incremental-bypass concern, and it no
longer takes a `logger` parameter — a module that owns a concern owns its logger. The remaining
eight concerns in `runner_utils.py` (plus three other grab-bag modules found by survey) are filed
as **`TECH-015`**, to be landed one module per commit rather than bundled into a feature commit.

---

## Documentation pulled forward from SF-03

The design assigned the `4_interactive_hitl_gates.md` update to SF-03's Guide-2. But the behaviour
**ships in this commit**, and the guide said only *"boot it back up logically where it failed"* — a
user reading it after this commit would be misinformed about what `sw resume` now does to a review
gate. It is updated here with the approve-vs-re-execute table and the "each park costs one resume"
consequence. SF-03's Guide-2 is reduced to the `feature_decomposition` journey specifics.

---

## SF-01 complete

All four FRs delivered. The four inherited engine gaps from the design's Research Findings are
closed: the unrunnable pipeline (FR-1), the never-populated `context.plan` (FR-2), plan state lost
across sessions (FR-3), and resume re-parking forever (FR-4).

**Still out of scope, by design:** artifact persistence and stub specs (SF-02, FR-5/6/7), the seam
pins (SF-02, FR-9), and the CLI journey + verifiable proof (SF-03, FR-8/10). `sw run
feature_decomposition greeter` still does not resolve a bare module name — SF-03/FR-8 owns that and
must import `FEATURE_SPEC_SUFFIX` rather than re-hardcode it. US-21 remains 🟡.
