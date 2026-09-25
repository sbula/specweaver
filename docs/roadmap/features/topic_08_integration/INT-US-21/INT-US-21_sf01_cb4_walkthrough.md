# INT-US-21 SF-01 CB-4 — Walkthrough: HITL Approve-on-Resume (FR-4)

**Commit boundary:** 4 of 4 (`5ebcc414`; CB-1 `f1de38f1`, CB-2 `c4c1a109`, CB-3 `6811a943`) ·
**Date:** 2026-07-25 · Plan: [sf01](INT-US-21_sf01_implementation_plan.md) (APPROVED 2026-07-25)

## Delivered

Resuming a reviewed gate-park **is** the approval. `GateEvaluator` parks HITL gates
unconditionally, and `resume()` used to only flip the status to RUNNING, so the gate re-parked
forever.

| File | Change |
|---|---|
| `core/flow/engine/approval.py` | **NEW** — `is_approvable_gate_park()` (pure predicate) + `try_approve_parked_step()` |
| `core/flow/engine/runner.py` | `resume()` passes `approve_parked=True`; approval branch at the top of the loop body; staleness bypass extracted |
| `core/flow/engine/runner_utils.py` | `execute_run` threads `approve_parked` |
| `core/flow/engine/staleness.py` | **NEW** — `try_staleness_bypass()` (Feature 3.32 SF-4), out of the loop |
| `docs/architecture/.../domain_flow_engine.md` | New "HITL Approve-on-Resume" section |
| `docs/user_guides/4_interactive_hitl_gates.md` | Approve-vs-re-execute table and "each park costs one resume" — Guide-2, pulled forward from SF-03 because the behaviour ships here |
| `tests/unit/core/flow/engine/test_approve_on_resume.py` | **NEW** — 15 tests |
| `tests/e2e/.../test_drafter_loop_e2e.py` | E6/E7 re-asserted; 3 fixture defects fixed |
| `tests/integration/.../test_pipeline_state_persistence.py` | Obsolete `gate = None` workaround removed |
| `tests/integration/.../test_rehydration_integration.py` | Observation points moved past the now-approved step |
| `tests/unit/interfaces/api/v1/test_pipelines.py` | REST approve→resume routing pinned (D7) |

- **Only `WAITING_FOR_INPUT` + stored `PASSED` + HITL gate + same step name approves.** Handler-park,
  failed gate-park, RESERVE-park (stored `PENDING`) and AUTO-gate park all re-execute — all four
  tested. The name check (`record.step_name == step_def.name`, with a warning) stops a step renamed
  between sessions from being skipped on another step's result — the same hazard CB-3's name-guard
  closes.
- **E6/E7 prove flow-through**: `status == "completed"` read from the persisted run plus a drained
  scripted verdict queue; they drive to terminal with a bounded loop, since the number of parks is a
  property of the pipeline (E7's spec pre-exists, so session 1 gate-parks; a reviewer rejection adds
  a loop_back park). This replaces D2's fixed "three sessions".
- Fixture defects fixed in E6/E7: `MANUAL_SPEC` had only `Purpose` (*"6 rules executed, 4 passed, 2
  failed"*) → now a Drafter-template-shaped spec, 6/6; `ReviewSpecHandler` prefers
  `context.llm_router.get_for_task(...)` over `context.llm` (`review.py:32-36`) and `sw run` /
  `sw resume` inject a real `ModelRouter`, so patching only `create_llm_adapter` made **live Gemini
  calls** (`Review LLM call failed: 429 RESOURCE_EXHAUSTED`, visible once runs reached `review_spec`)
  → the router now defers to the scripted adapter; the post-review stub now carries
  `verdict: "accepted"`, because `review_code`'s `condition: accepted` reads
  `result.output["verdict"]` — without it the run looped back to `generate_code` until `max_retries`.
- **Extractions**: `runner.py` hit the 600-line RED threshold for the third time in SF-01; now 584.
  Both moved concerns "complete the current step and advance without a handler". The staleness
  bypass went to `engine/staleness.py`, not `engine/runner_utils.py` — a module whose name promises
  nothing accretes anything — and owns its own logger. Behaviour-preserving: 43 existing
  `stale_nodes` references + full suite.

## Proof

| Suite | Result |
|---|---|
| Unit | **4957 passed**, 15 skipped |
| Integration | **523 passed**, 3 skipped, 15 deselected |
| E2E | **166 passed**, 1 skipped |
| **Grand total** | **5646 passed, 19 skipped** (CB-3: 5629; +17) |

`ruff` ✅ · `mypy` ✅ (306 files) · `C901` ✅ · file sizes ✅ **0 errors** · `tach` ✅ · roadmap sync ✅.
Phase 7.5 Red/Blue: 1 finding (the renamed-step approval), fixed.

SF-01 closes the four inherited engine gaps: the unrunnable pipeline (FR-1), the never-populated
`context.plan` (FR-2), plan state lost across sessions (FR-3), resume re-parking forever (FR-4).

## Findings still open

- The other eight concerns in `runner_utils.py` plus three other grab-bag modules → **`TECH-015`**,
  one module per commit.
- Five vacuous proofs found in SF-01 (exit-code-only assertions, `_AlwaysPassHandler`,
  `PIPELINES_DIR`, a fixture that could not pass its battery, live API calls in a "mocked" test):
  treat existing coverage as unverified until read.
